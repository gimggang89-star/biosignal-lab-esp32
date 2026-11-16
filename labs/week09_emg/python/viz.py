# viz.py — EMG 실시간 보기 · 기록 (BioAmp EXG Pill + ESP32, 1000 Hz, 115200 baud, 펌웨어 emg_chain.ino)
# 사용법 (pip install numpy scipy matplotlib pyserial)
#  python viz.py live   COM5 emg                         : 실시간 — 위에서부터 원신호 x · 필터 후 · RMS(100 ms)+임계 · 상태. 창에서 c = 기저선 다시 학습
#  python viz.py live   COM5 emg --spec --win 8          : 오른쪽에 순간 스펙트럼, 보이는 시간 8초
#  python viz.py record COM5 emg 20 내기록.csv           : 20초 기록 → 내기록.csv (t_s,x,filt,mav,rms,st) + 내기록_e.csv (#B #E #W #S 줄)
#  python viz.py record COM5 emg 30 e3.csv --cue e3_labels.csv : 레이블 시각에 맞춰 할 일(이완 · 수축 · 노력 %)을 화면에 띄운다
#  python viz.py record COM5 emg 20 r.csv --mode R       : R 모드(원신호만) 텍스트 기록 t_s,x   (--mode F 면 t_s,filt)
#  python viz.py record COM5 emg2 25 e6.csv              : 2채널 (펌웨어 NCH 2). 열 뒤에 x2,filt2,mav2,rms2,st2
#  python viz.py live   내기록.bin emg  /  내기록.csv emg : 저장한 파일 재생 (--raw 로 받은 바이트를 저장할 수 있다)
#  옵션: --raw 파일.bin  --no-reset (보드 리셋 안 함)  --save 그림.png --until 10 (창 없이 그 시각 화면을 그림으로)
# 필터와 판정(st)은 펌웨어 값이다. mav · rms 는 파이썬이 받은 filt 로 펌웨어와 같은 방법(최근 100 표본)으로 다시 계산한다
import sys, os, time, threading, argparse
import numpy as np

FS = 1000
RMS_N = 100
DESC = {"rest": "이완 (힘 빼기)", "contract": "수축! (주먹 쥐고 팔 굽히기)", "flex": "굽힘 (이두에 힘)", "ext": "폄 (삼두에 힘, 팔 펴서 누르기)"}

def describe(label):
    if label.startswith("f") and label[1:].isdigit(): return f"노력 {label[1:]} % 로 쥐기"
    return DESC.get(label, label)

def envelope(f, n=RMS_N):
    """펌웨어와 같은 이동 MAV · RMS (최근 n 표본, 시작은 0 으로 채움)"""
    f = np.asarray(f, float); i = np.arange(len(f)); lo = np.maximum(i + 1 - n, 0)
    ca = np.concatenate([[0.0], np.cumsum(np.abs(f))]); cs = np.concatenate([[0.0], np.cumsum(f * f)])
    return (ca[i + 1] - ca[lo]) / n, np.sqrt(np.maximum(cs[i + 1] - cs[lo], 0) / n)

class Decoder:
    """B 모드 바이트 → 표본. 헤더(최상위 비트 1) + 7 bit 데이터 바이트, 프레임 사이에 '#...\\n' 텍스트 줄"""
    def __init__(self):
        self.started = False; self.nch, self.fbits, self.g = 1, 4, 4
        self.state = "idle"; self.hdr = 0; self.buf = []; self.line = bytearray(); self.pre = bytearray()
        self.prev = None; self.lost = 0; self.restarts = 0; self.info = ""
        self.st, self.x, self.f = [], [], []          # 표본마다: 상태 [st1, st2], x [x1, x2], filt [f1, f2]
        self.base = 0                                # live 에서 앞쪽을 버린 표본 수 (n() = base + 남은 표본)
        self.lines = []                              # (표본 번호, 텍스트)
    def _start(self, s):
        if self.started: self.restarts += 1
        kv = dict(p.split("=", 1) for p in s.split()[1:] if "=" in p)
        self.nch = int(kv.get("nch", 1)); self.fbits = int(kv.get("fbits", 4 if self.nch == 1 else 0))
        self.g = -(-self.nch * (24 + self.fbits) // 7); self.started = True; self.info = s
        self.st, self.x, self.f, self.lines = [], [], [], []; self.base = 0; self.prev = None; self.lost = 0; self.state = "idle"
    def _frame(self):
        v = 0
        for b in self.buf: v = (v << 7) | b
        v >>= self.g * 7 - self.nch * (24 + self.fbits)
        xs, fs = [], []
        for _ in range(self.nch):
            fb = 12 + self.fbits; q = v & ((1 << fb) - 1); v >>= fb
            if q >= 1 << (fb - 1): q -= 1 << fb
            xs.append(v & 0xFFF); fs.append(q / (1 << self.fbits)); v >>= 12
        xs.reverse(); fs.reverse()
        h = self.hdr; c = h & 7
        if self.prev is not None and c != (self.prev + 1) & 7: self.lost += (c - self.prev - 1) & 7
        self.prev = c
        self.st.append([(h >> 5) & 3, (h >> 3) & 3][:self.nch]); self.x.append(xs); self.f.append(fs)
    def feed(self, data):
        for b in data:
            if not self.started:                     # #START 전: 부트 로그 · 텍스트 모드 줄은 버린다
                if b == 10:
                    s = self.pre.decode("ascii", "ignore").strip(); self.pre = bytearray()
                    if s.startswith("#START"): self._start(s)
                elif b < 128: self.pre.append(b)
                continue
            if self.state == "frame":
                if b & 0x80: self.lost += 1; self.hdr = b; self.buf = []; continue
                self.buf.append(b)
                if len(self.buf) == self.g: self._frame(); self.state = "idle"
            elif self.state == "text":
                if b & 0x80: self.hdr = b; self.buf = []; self.state = "frame"; continue
                if b == 10:
                    s = self.line.decode("ascii", "ignore").strip(); self.state = "idle"
                    if s.startswith("#START"): self._start(s)
                    elif s: self.lines.append((self.n(), s))
                else: self.line.append(b)
            else:
                if b & 0x80: self.hdr = b; self.buf = []; self.state = "frame"
                elif b == 35: self.line = bytearray(b"#"); self.state = "text"
    def n(self): return self.base + len(self.st)
    def trim(self, keep):
        d = len(self.st) - keep
        if d > 0: del self.st[:d]; del self.x[:d]; del self.f[:d]; self.base += d

class SerialReader(threading.Thread):
    """포트를 계속 비우는 백그라운드 스레드 (그래프를 그리느라 멈춰도 수신 버퍼가 넘치지 않게)"""
    def __init__(self, port, cmd, reset=True, raw=None):
        super().__init__(daemon=True)
        import serial
        try: self.ser = serial.Serial(port, 115200, timeout=0.05)
        except Exception as e:
            sys.exit(f"[실패] 포트 {port} 를 열 수 없다: {e}\n → Arduino 시리얼 모니터/플로터를 닫았는지, 포트 번호가 맞는지 확인")
        if reset:
            try: self.ser.setDTR(False); self.ser.setRTS(True); time.sleep(0.1); self.ser.setRTS(False)
            except Exception: pass
            time.sleep(1.5)
        self.ser.reset_input_buffer(); self.ser.write(cmd.encode())
        self.lock = threading.Lock(); self.chunks = []; self.alive = True; self.raw = open(raw, "wb") if raw else None
    def run(self):
        while self.alive:
            try: d = self.ser.read(self.ser.in_waiting or 1)
            except Exception: break
            if d:
                with self.lock: self.chunks.append(d)
                if self.raw: self.raw.write(d)
    def take(self):
        with self.lock: d = b"".join(self.chunks); self.chunks = []
        return d
    def send(self, s):
        try: self.ser.write(s.encode())
        except Exception: pass
    def close(self, last=None):
        if last: self.send(last); time.sleep(0.05)
        self.alive = False; self.join(0.5)
        try: self.ser.close()
        except Exception: pass
        if self.raw: self.raw.close()

class Tee:
    """화면에 찍으면서 txt 에도 모은다"""
    def __init__(self): self.buf = []; self.out = sys.stdout
    def write(self, s): self.out.write(s); self.buf.append(s)
    def flush(self): self.out.flush()
    def save(self, path):
        sys.stdout = self.out
        with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f: f.write("".join(self.buf))
        print(f"(이 내용은 {path} 에도 저장됨)")

def is_file(src): return os.path.splitext(src)[1].lower() in (".bin", ".csv", ".txt", ".log")

def load_labels(path):
    out = []
    for ln in open(path, encoding="utf-8-sig").read().splitlines()[1:]:
        p = [v.strip() for v in ln.split(",")]
        if len(p) >= 3 and p[0]: out.append((p[0], float(p[1]), float(p[2])))
    return out

def parse_hash(lines):
    """#B · #E · #W 줄 정리 → dict"""
    info = {"B": {}, "E": [], "W": [], "S": []}
    for i, s in lines:
        p = s.split(" ")[0].split(",")
        try:
            if p[0] == "#B": info["B"][int(p[7]) if len(p) > 7 else 1] = dict(n=int(p[1]), mu=float(p[2]), sd=float(p[3]), on=float(p[4]), off=float(p[5]), mav_mu=float(p[6]))
            elif p[0] == "#E": info["E"].append((int(p[1]), int(p[2]), int(p[3]) if len(p) > 3 else 1))
            elif p[0] == "#W": info["W"].append((int(p[1]), p[2], p[3], int(p[4]) if len(p) > 4 else 1))
            elif p[0] == "#S": info["S"].append(s)
        except (ValueError, IndexError): pass
    return info

# ------------------------------------------------------------ 기록
def record(a):
    need = int(a.secs * FS); base = a.out[:-4] if a.out.lower().endswith(".csv") else a.out
    cues = load_labels(a.cue) if a.cue else []
    if a.mode in ("R", "F"): return record_text(a, need, base, cues)
    dec = Decoder()
    if is_file(a.src):
        if a.src.lower().endswith(".csv"): sys.exit("csv 는 이미 기록된 파일이다 (재생은 live)")
        dec.feed(open(a.src, "rb").read())
        if not dec.started: sys.exit("#START 줄이 없는 파일이다")
    else:
        rd = SerialReader(a.src, "B", not a.no_reset, a.raw); rd.start(); t0 = time.time()
        print("보드 연결 중 ... (B 모드로 바꾸고 #START 를 기다린다)")
        while not dec.started and time.time() - t0 < 8:
            dec.feed(rd.take()); time.sleep(0.02)
        if not dec.started:
            rd.close(); sys.exit("[실패] 보드에서 #START 를 못 받았다 → ① emg_chain 스케치가 올라갔는지 ② 시리얼 모니터 · 플로터를 닫았는지 ③ 포트 번호")
        if a.kind == "emg2" and dec.nch != 2: print("[주의] emg2 인데 펌웨어가 1채널이다 (NCH 2 로 업로드했는지)")
        print(f"기록 시작: {a.secs:g}초 ({dec.info})")
        if not cues: print("  처음 3초는 힘을 빼고 가만히 (기저선 학습)")
        ci, warned, last_prog, t1 = 0, -1, -1, time.time()
        while dec.n() < need and time.time() - t1 < a.secs + 15:
            dec.feed(rd.take())
            if dec.restarts:
                print("[주의] 보드가 다시 시작됐다 (리셋 · 다른 프로그램) → 처음부터 다시 기록한다"); dec.restarts = 0; ci = 0; warned = -1
            t = dec.n() / FS
            while ci < len(cues) and t >= cues[ci][1]:
                lab, s0, s1 = cues[ci]
                print(f"  [{s0:5.1f}초] ▶ {describe(lab):<28s} ({s1 - s0:.1f}초 동안)", flush=True); ci += 1
            if ci < len(cues) and warned != ci and t >= cues[ci][1] - 1.0:   # 1초 전에 미리 알려 준다
                print(f"            ... 1초 뒤: {describe(cues[ci][0])}", flush=True); warned = ci
            if int(t) // 5 != last_prog and not cues:
                last_prog = int(t) // 5; print(f"  ... {t:4.0f}초", flush=True)
            time.sleep(0.02)
        rd.close(last="P")                           # 끝나면 P 모드로 돌려 둔다 (플로터를 바로 쓸 수 있게)
    if dec.n() < need: print(f"[주의] {a.secs:g}초를 다 받지 못했다 ({dec.n() / FS:.1f}초). 연결 · 포트를 확인하고 다시")
    t = Tee(); sys.stdout = t
    try: save_record(dec, base, need, a.kind)
    finally: t.save(base + "_기록요약.txt")

def save_record(dec, base, need, kind):
    k = min(need, dec.n()); nch = dec.nch
    X = np.array(dec.x[:k], float); F = np.array(dec.f[:k], float); S = np.array(dec.st[:k], int)
    cols, data = ["t_s"], [np.arange(k) / FS]
    for c in range(nch):
        mav, rms = envelope(F[:, c]); sfx = "" if c == 0 else str(c + 1)
        cols += [f"x{sfx}", f"filt{sfx}", f"mav{sfx}", f"rms{sfx}", f"st{sfx}"]; data += [X[:, c], F[:, c], mav, rms, S[:, c]]
    fmt = ["%.3f"] + ["%d", "%.4f", "%.3f", "%.3f", "%d"] * nch
    np.savetxt(base + ".csv", np.column_stack(data), delimiter=",", header=",".join(cols), comments="", fmt=fmt)
    with open(base + "_e.csv", "w", encoding="utf-8") as fo:
        fo.write("t_s,line\n")
        for i, s in dec.lines:
            if i <= k: fo.write(f"{i / FS:.3f},{s}\n")
    info = parse_hash([l for l in dec.lines if l[0] <= k])
    print(f"저장: {base}.csv ({k}표본 = {k / FS:.1f}초, {nch}채널) + {base}_e.csv (진단 줄 {len(info['E']) + len(info['W']) + len(info['B'])}개)")
    if dec.lost: print(f"[주의] 프레임 손실 약 {dec.lost}개 (포트를 두 프로그램이 열었거나 USB 가 불안정)")
    for c in range(nch):
        sfx = "" if nch == 1 else f" (채널 {c + 1})"
        b = info["B"].get(c + 1); x = X[:, c]
        print(f"원신호 x{sfx}: 중앙값 {np.median(x):.0f} (이상적 2048 근처), 범위 {x.min():.0f}~{x.max():.0f}")
        sat = [w for w in info["W"] if w[1] == "SAT" and w[3] == c + 1]
        if sat: print(f"[경고] ADC 포화 {len(sat)}번{sfx} → 힘을 줄이거나 전극 · 이득 확인 (값이 0 이나 4095 에 붙음)")
        if any(w[1] == "BIAS" and w[3] == c + 1 for w in info["W"]): print(f"[경고] 바이어스 이상{sfx} (중심이 2048 에서 멀다) → 전원 · 배선 · 보드 판 확인")
        if not b: print(f"[주의] 기저선(#B) 줄이 없다{sfx} — 기록이 3초보다 짧거나 시작이 끊겼다"); continue
        on = int((S[:, c] == 2).sum()); ne = sum(1 for e in info["E"] if e[1] == 1 and e[2] == c + 1)
        print(f"펌웨어 기저선{sfx}: RMS 평균 {b['mu']:.2f} · 표준편차 {b['sd']:.2f} → ON 임계 {b['on']:.2f} / OFF 임계 {b['off']:.2f},  MAV 평균 {b['mav_mu']:.2f}")
        print(f"펌웨어 수축 판정{sfx}: 수축 시작 {ne}번, 수축(st=2) {on / FS:.1f}초")
        if b["mav_mu"] == 0: print("  → 빈칸 ① (정류) 이 비어 있다: MAV 가 0")
        if b["mu"] == 0: print("  → 빈칸 ② (RMS 제곱 합) 가 비어 있다: RMS 가 0")
        elif ne == 0:
            rms = envelope(F[:, c])[1]
            if (rms[3000:] > b["on"]).sum() > 200: print("  → 수축했는데 판정이 안 바뀐다: 빈칸 ③ 을 확인 (빈칸이면 정상: 실험 4 에서 채운다)")
            else: print("  → 수축이 기저선 임계를 넘지 않았다 (힘을 더 주거나, 처음 3초에 힘을 빼고 다시)")

def record_text(a, need, base, cues):
    """R · F 텍스트 모드 기록 (한 줄에 숫자 1개, 2채널은 2개)"""
    if is_file(a.src): lines = open(a.src, encoding="utf-8", errors="ignore").read().splitlines()
    else:
        rd = SerialReader(a.src, a.mode, not a.no_reset, a.raw); rd.start(); buf, lines, t1, ci = "", [], time.time(), 0
        print(f"{a.mode} 모드 기록 시작: {a.secs:g}초")
        while len(lines) < need and time.time() - t1 < a.secs + 15:
            buf += rd.take().decode("ascii", "ignore"); parts = buf.split("\n"); buf = parts.pop()
            lines += [p.strip() for p in parts if p.strip() and ":" not in p and not p.startswith("#")]
            t = len(lines) / FS
            while ci < len(cues) and t >= cues[ci][1]:
                print(f"  [{cues[ci][1]:5.1f}초] ▶ {describe(cues[ci][0])}", flush=True); ci += 1
            time.sleep(0.02)
        rd.close(last="P")
    vals = []
    for s in lines:
        s = s.split("->")[-1].strip()
        try: vals.append([int(v) for v in s.split(",")])
        except ValueError: pass
    vals = [v for v in vals if len(v) == len(vals[0])][:need] if vals else []
    if not vals: sys.exit("받은 숫자가 없다 → 스케치 · 포트 확인")
    V = np.array(vals); nch = V.shape[1]; step = 1 if nch == 1 else 2
    name = "x" if a.mode == "R" else "filt"
    cols = ["t_s"] + [name + ("" if c == 0 else str(c + 1)) for c in range(nch)]
    np.savetxt(base + ".csv", np.column_stack([np.arange(len(V)) * step / FS, V]), delimiter=",", header=",".join(cols), comments="", fmt=["%.3f"] + ["%d"] * nch)
    print(f"저장: {base}.csv ({len(V)}줄, {a.mode} 모드, 시각은 줄 번호로 계산)")

# ------------------------------------------------------------ 실시간
def live(a):
    import matplotlib
    if a.save: matplotlib.use("Agg")
    import logging, matplotlib.pyplot as plt
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
    plt.rcParams["font.family"] = ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    dec = Decoder(); rd = None; pre = None; t_start = time.time()
    if is_file(a.src):
        if a.src.lower().endswith(".csv"):
            d = np.genfromtxt(a.src, delimiter=",", names=True); nch = 2 if "x2" in d.dtype.names else 1
            pre = dict(x=np.column_stack([d["x" + s] for s in ([""] if nch == 1 else ["", "2"])]),
                       f=np.column_stack([d["filt" + s] for s in ([""] if nch == 1 else ["", "2"])]),
                       st=np.column_stack([d["st" + s] for s in ([""] if nch == 1 else ["", "2"])]).astype(int), nch=nch, lines=[])
            ev = a.src[:-4] + "_e.csv"
            if os.path.exists(ev):
                for ln in open(ev, encoding="utf-8").read().splitlines()[1:]:
                    t, s = ln.split(",", 1); pre["lines"].append((int(float(t) * FS), s))
        else:
            dec.feed(open(a.src, "rb").read())
            pre = dict(x=np.array(dec.x, float), f=np.array(dec.f, float), st=np.array(dec.st, int), nch=dec.nch, lines=dec.lines)
    else:
        rd = SerialReader(a.src, "B", not a.no_reset, a.raw); rd.start()
        t0 = time.time()
        while not dec.started and time.time() - t0 < 8: dec.feed(rd.take()); time.sleep(0.02)
        if not dec.started: rd.close(); sys.exit("[실패] #START 를 못 받았다 → 스케치 업로드, 시리얼 모니터 닫기, 포트 번호 확인")
    nch = pre["nch"] if pre else dec.nch
    W = int(a.win * FS); ncol = 2 if a.spec else 1
    fig = plt.figure(figsize=(12 if a.spec else 10, 2.0 * (3 + nch) + 0.6))
    gs = fig.add_gridspec(3 * nch + 1, ncol, width_ratios=[3, 1.2] if a.spec else [1])
    axes, lines = [], {}
    names = []
    for c in range(nch):
        sfx = "" if nch == 1 else f" (ch{c + 1})"
        names += [(c, "x", "원신호 x" + sfx), (c, "f", "필터 후" + sfx), (c, "r", "RMS · 임계" + sfx)]
    for i, (c, k, ttl) in enumerate(names):
        ax = fig.add_subplot(gs[i, 0], sharex=axes[0] if axes else None); ax.set_ylabel(ttl, fontsize=8); ax.grid(alpha=.3); axes.append(ax)
        lines[(c, k)], = ax.plot([], [], lw=0.6, color="tab:red" if k == "r" else None)
        if k == "r":
            lines[(c, "on")], = ax.plot([], [], "k--", lw=0.8); lines[(c, "off")], = ax.plot([], [], ":", color="gray", lw=0.8)
    axs = fig.add_subplot(gs[3 * nch, 0], sharex=axes[0]); axs.set_ylabel("상태", fontsize=8); axs.set_ylim(-0.2, 2.2); axs.set_yticks([0, 1, 2]); axs.set_yticklabels(["보정", "이완", "수축"], fontsize=7); axs.grid(alpha=.3)
    for c in range(nch): lines[(c, "s")], = axs.plot([], [], lw=1.2, label=f"ch{c + 1}")
    axs.set_xlabel("시간 (초)")
    if a.spec:
        axp = fig.add_subplot(gs[:, 1]); axp.set_title("순간 스펙트럼 (최근 256 ms)", fontsize=9); axp.set_xlabel("Hz"); axp.set_xlim(0, 500); axp.axvline(60, color="gray", ls=":"); axp.grid(alpha=.3)
        lines["sp"], = axp.plot([], [], lw=0.8)
    title = fig.suptitle("", fontsize=10)

    def snapshot(upto):
        """보이는 구간(최근 win 초 + RMS 창)만 꺼낸다 → (시작 번호 lo, 끝 k, x, filt, 상태, 진단 줄)"""
        if pre is not None:
            k = min(upto, len(pre["st"])); lo = max(0, k - W - RMS_N)
            return lo, k, pre["x"][lo:k], pre["f"][lo:k], pre["st"][lo:k], [l for l in pre["lines"] if l[0] <= k]
        k = dec.n(); m = min(len(dec.st), W + RMS_N); lo = k - m
        out = (lo, k, np.array(dec.x[-m:], float).reshape(-1, nch), np.array(dec.f[-m:], float).reshape(-1, nch), np.array(dec.st[-m:], int).reshape(-1, nch), dec.lines)
        dec.trim(2 * (W + RMS_N))                    # 오래된 표본은 버린다 (메모리)
        return out

    def update(_=None):
        if rd is not None: dec.feed(rd.take()); upto = dec.n()
        else: upto = int((time.time() - t_start) * FS) if not a.save else int((a.until or 1e9) * FS)
        lo, k, X, F, S, L = snapshot(upto)
        if k - lo < 2: return
        t = np.arange(lo, k) / FS; seg = slice(RMS_N if k - lo > W else 0, None)
        info = parse_hash(L); step = 2 if nch == 1 else 3
        for c in range(nch):
            x, f = X[:, c], F[:, c]; rms = envelope(f)[1]
            lines[(c, "x")].set_data(t[seg][::step], x[seg][::step]); lines[(c, "f")].set_data(t[seg][::step], f[seg][::step]); lines[(c, "r")].set_data(t[seg], rms[seg])
            b = info["B"].get(c + 1)
            if b:
                lines[(c, "on")].set_data([t[0], t[-1]], [b["on"]] * 2); lines[(c, "off")].set_data([t[0], t[-1]], [b["off"]] * 2)
            lines[(c, "s")].set_data(t[seg], S[:, c][seg])
            for kk, arr in (("x", x[seg]), ("f", f[seg]), ("r", rms[seg])):
                ax = axes[[i for i, nm in enumerate(names) if nm[0] == c and nm[1] == kk][0]]
                lo_v, hi_v = float(np.min(arr)), float(np.max(arr)); pad = max((hi_v - lo_v) * 0.1, 1.0)
                if kk == "r" and b: hi_v = max(hi_v, b["on"] * 1.2)
                ax.set_ylim(lo_v - pad, hi_v + pad)
        axes[0].set_xlim(max(t[-1] - a.win, 0), max(t[-1], a.win))
        if a.spec and len(F) >= 256:
            seg256 = F[-256:, 0] * np.hanning(256); P = np.abs(np.fft.rfft(seg256)) ** 2; fr = np.fft.rfftfreq(256, 1 / FS)
            lines["sp"].set_data(fr, 10 * np.log10(P + 1e-9)); lines["sp"].axes.set_ylim(10 * np.log10(P.max() + 1e-9) - 60, 10 * np.log10(P.max() + 1e-9) + 5)
        warn = []
        if any(w[1] == "SAT" and w[0] > k - 2000 for w in info["W"]): warn.append("[경고] ADC 포화")
        if any(w[1] == "BIAS" for w in info["W"]): warn.append("[경고] 바이어스")
        ne = sum(1 for e in info["E"] if e[1] == 1)
        cal = "기저선 학습 중 (힘 빼기)" if (S[-1] == 0).any() else f"수축 시작 {ne}번"
        loss = f"  손실 {dec.lost}" if rd is not None and dec.lost else ""
        title.set_text(f"{t[-1]:.1f}초  ·  {cal}  ·  c = 기저선 다시 학습{loss}   " + " ".join(warn))

    if a.save:
        if rd is not None:                           # 보드에서: until 초(없으면 win 초)만큼 받은 뒤 그 화면을 저장
            need, t0 = int((a.until or a.win) * FS), time.time()
            while dec.n() < need and time.time() - t0 < need / FS + 10: dec.feed(rd.take()); time.sleep(0.02)
        update(); fig.tight_layout(); fig.savefig(a.save, dpi=110); print(f"그림 저장: {a.save}")
        if rd is not None: rd.close(last="P")
        return
    def on_key(e):
        if e.key == "c" and rd is not None: rd.send("c"); print("기저선 다시 학습 (2.5초 동안 힘 빼기)")
    fig.canvas.mpl_connect("key_press_event", on_key)
    from matplotlib.animation import FuncAnimation
    ani = FuncAnimation(fig, update, interval=50, cache_frame_data=False)
    fig.tight_layout(); plt.show()
    if rd is not None: rd.close(last="P")

def main():
    if len(sys.argv) < 4:
        print(open(__file__, encoding="utf-8").read().split("import sys")[0]); return
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["live", "record"]); ap.add_argument("src"); ap.add_argument("kind", choices=["emg", "emg2"])
    ap.add_argument("secs", nargs="?", type=float); ap.add_argument("out", nargs="?")
    ap.add_argument("--mode", default="B", choices=["B", "R", "F"]); ap.add_argument("--cue"); ap.add_argument("--raw")
    ap.add_argument("--no-reset", action="store_true"); ap.add_argument("--spec", action="store_true"); ap.add_argument("--win", type=float, default=5.0)
    ap.add_argument("--save"); ap.add_argument("--until", type=float)
    a = ap.parse_args()
    if a.cmd == "record":
        if a.secs is None or not a.out: sys.exit("record 는 시간(초)과 저장 파일 이름이 필요하다: python viz.py record COM5 emg 20 내기록.csv")
        record(a)
    else: live(a)

if __name__ == "__main__": main()
