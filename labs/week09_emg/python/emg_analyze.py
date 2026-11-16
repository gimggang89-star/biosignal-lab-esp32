# emg_analyze.py — viz.py 로 기록한 EMG 를 숫자와 그림으로 본다 (그림은 <파일이름>_<명령>.png 로 저장)
# 사용법 (pip install numpy scipy matplotlib)
#  python emg_analyze.py time    내기록.csv --auto               : 구간별 x 중앙값 · filt 범위 · MAV · RMS, SNR  (실험 1 · 2)
#  python emg_analyze.py time    내기록.csv --labels 레이블.csv   : 레이블 구간으로  (또는 --seg "rest:0-3,contract:3-6")
#  python emg_analyze.py spec    내기록.csv --labels 레이블.csv   : 구간별 스펙트럼, 평균 · 중앙주파수(MNF · MDF)  [--signal raw]
#  python emg_analyze.py force   e3.csv --labels e3_labels.csv    : 노력 단계(f10 f25 ...)별 RMS, 잡음 보정, 직선 · R²  (실험 3)
#  python emg_analyze.py detect  e4.csv --labels e4_labels.csv    : 임계 배수 k · 히스테리시스 비교, 놓침 · 오검출 · 지연  (실험 4)  [--k 3,5,8]
#  python emg_analyze.py fatigue e5.csv --labels e5_labels.csv    : 1초 창 · 0.5초 간격 MDF · RMS 추세, 기울기 · R²  (실험 5)
#  python emg_analyze.py bipolar e6.csv --labels e6_labels.csv    : 2채널 굽힘 · 폄 RMS, CCI, 상관 r  (실험 6)
# 레이블 CSV: 첫 줄 label,start_s,end_s  아래로 한 줄에 한 구간 (시각은 기록 t_s, 0 = 기록 시작 = 보드 #START)
# 숫자는 연습용이며 진단이 아니다. 보드 이득을 모르므로 단위는 ADC count 이다
import sys, os, argparse, warnings
import numpy as np
warnings.filterwarnings("ignore")
FS, RMS_N = 1000, 100
BASE = (0.5, 3.0)                                   # 기저선 학습 구간 (펌웨어와 같다)

def plt_():
    import matplotlib; matplotlib.use("Agg") if os.environ.get("MPLBACKEND", "").lower() == "agg" else None
    import logging, matplotlib.pyplot as plt
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)   # 글꼴 못 찾음 메시지 숨김
    plt.rcParams["font.family"] = ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt

def save(fig, path, tag):
    out = os.path.splitext(path)[0] + "_" + tag + ".png"
    fig.tight_layout(); fig.savefig(out, dpi=110); print(f"그림 저장: {out}")
    try:
        import matplotlib.pyplot as plt
        if os.environ.get("MPLBACKEND", "").lower() != "agg": plt.show()
    except Exception: pass

def envelope(f, n=RMS_N):
    f = np.asarray(f, float); i = np.arange(len(f)); lo = np.maximum(i + 1 - n, 0)
    ca = np.concatenate([[0.0], np.cumsum(np.abs(f))]); cs = np.concatenate([[0.0], np.cumsum(f * f)])
    return (ca[i + 1] - ca[lo]) / n, np.sqrt(np.maximum(cs[i + 1] - cs[lo], 0) / n)

def load(path, ch=1):
    """기록 CSV (t_s,x,filt,mav,rms,st[,x2,...]) 또는 R · F 텍스트 캡처 → dict"""
    if not os.path.exists(path): sys.exit(f"{path} 가 없다")
    head = open(path, encoding="utf-8-sig").readline()
    sfx = "" if ch == 1 else str(ch)
    if "t_s" in head or "filt" in head or head.strip().startswith("x"):
        d = np.genfromtxt(path, delimiter=",", names=True, encoding="utf-8-sig"); names = d.dtype.names
        out = {"t": d["t_s"] if "t_s" in names else np.arange(len(d)) / FS, "src": "board"}
        if "filt" + sfx in names: out["f"] = d["filt" + sfx].astype(float)
        if "x" + sfx in names: out["x"] = d["x" + sfx].astype(float)
        if "st" + sfx in names: out["st"] = d["st" + sfx].astype(int)
        if "f" not in out:                           # R 모드 기록: x 만 있다 → 파이썬 참고 체인으로 filt 계산
            out["f"] = py_chain(out["x"]); out["src"] = "python"
    else:                                            # 터미널 캡처 (한 줄에 숫자 하나, '12:00:01.234 -> 2057' 허용)
        vals = []
        for ln in open(path, encoding="utf-8", errors="ignore"):
            s = ln.split("->")[-1].strip()
            try: vals.append(float(s))
            except ValueError: pass
        v = np.array(vals); out = {"t": np.arange(len(v)) / FS, "src": "python"}
        if np.median(v) > 500: out["x"] = v; out["f"] = py_chain(v)
        else: out["f"] = v
    out["mav"], out["rms"] = envelope(out["f"])
    if "st" not in out: out["st"] = rule_states(out["rms"])
    if out["src"] == "python": print("※ 텍스트 기록: filt · RMS · 상태는 파이썬 참고 구현이 계산한 값이다 (펌웨어 판정 아님)")
    return out

def py_chain(x):
    """펌웨어와 같은 체인의 파이썬 판: DC 제거(시정수 1 s) → HPF 20 Hz → 노치 60 Hz"""
    from scipy import signal
    x = np.asarray(x, float); dc = np.empty_like(x); d = x[0]
    for i, v in enumerate(x): d += (v - d) * 0.001; dc[i] = d
    sos = signal.butter(2, 20, "highpass", fs=FS, output="sos"); b, a = signal.iirnotch(60, 30, fs=FS)
    return signal.lfilter(b, a, signal.sosfilt(sos, x - dc))

def baseline(rms):
    m = rms[int(BASE[0] * FS):int(BASE[1] * FS)]
    mu, sd = float(m.mean()), float(m.std()); return mu, max(sd, 0.2 * mu)

def rule_states(rms, k_on=5.0, k_off=3.0, min_on=50, min_off=100, single=False):
    """펌웨어와 같은 규칙: 기저선 mu+k·sd, 히스테리시스, 최소 지속 (single=True 면 ON = OFF)"""
    mu, sd = baseline(rms); on_t = mu + k_on * sd; off_t = on_t if single else mu + k_off * sd
    st = np.zeros(len(rms), int); on, cnt = 0, 0
    for i in range(int(BASE[1] * FS), len(rms)):
        above = rms[i] > (off_t if on else on_t)
        if above != on:
            cnt += 1
            if cnt >= (min_off if on else min_on): on, cnt = int(above), 0
        else: cnt = 0
        st[i] = 2 if on else 1
    return st

def runs(mask):
    """True 구간들 → [(시작, 끝)] (표본 번호)"""
    m = np.concatenate([[0], mask.astype(int), [0]]); d = np.diff(m)
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))

def get_segs(a, d):
    if a.labels: return [(l, s, e) for l, s, e in [tuple(r) for r in load_labels(a.labels)]]
    if a.seg:
        out = []
        for p in a.seg.split(","):
            l, r = p.split(":"); s, e = r.split("-"); out.append((l.strip(), float(s), float(e)))
        return out
    if True:                                         # --auto (레이블이 없으면 자동): 보드 판정(st)에서 수축 구간, 사이를 이완 구간으로
        st = d["st"]
        if not (st == 2).any():
            print("※ 보드 판정에 수축이 없다 → 같은 규칙(mu+5sd / mu+3sd, 50/100 ms)을 rms 에 적용해 나눈다"); st = rule_states(d["rms"])
        on = runs(st == 2); segs = []; prev = int(BASE[1] * FS); k = 0
        for s, e in on:
            if s - prev > 300: segs.append(("rest", prev / FS, s / FS))
            k += 1; segs.append((f"contract{k}", s / FS, e / FS)); prev = e
        if len(st) - prev > 300: segs.append(("rest", prev / FS, len(st) / FS))
        return segs

def load_labels(path):
    out = []
    for ln in open(path, encoding="utf-8-sig").read().splitlines()[1:]:
        p = [v.strip() for v in ln.split(",")]
        if len(p) >= 3 and p[0]: out.append((p[0], float(p[1]), float(p[2])))
    if not out: sys.exit(f"{path} 에 구간이 없다 (첫 줄 label,start_s,end_s)")
    return out

def idx(s, e, n, trim=0.0):
    a, b = int((s + trim) * FS), int((e - trim) * FS); return max(a, 0), min(max(b, a + 1), n)

def is_contract(l): return l.startswith("contract") or l.startswith("flex") or l.startswith("ext") or (l.startswith("f") and l[1:].isdigit())

# ------------------------------------------------------------ time
def cmd_time(a):
    d = load(a.file); segs = get_segs(a, d); n = len(d["f"])
    print(f"{'구간':<11s}{'시각(초)':>13s}{'x 중앙값':>9s}{'filt 범위(5~95%)':>19s}{'MAV':>9s}{'RMS':>9s}{'MAV/RMS':>9s}")
    rest, con = [], []
    for l, s, e in segs:
        i0, i1 = idx(s, e, n, 0.2 if e - s > 1 else 0)
        f = d["f"][i0:i1]; mav, rms = d["mav"][i0:i1].mean(), d["rms"][i0:i1].mean()
        xm = f"{np.median(d['x'][i0:i1]):.0f}" if "x" in d else "-"
        lo, hi = np.percentile(f, [5, 95])
        print(f"{l:<11s}{s:6.1f}~{e:5.1f}{xm:>9s}{f'{lo:.1f} ~ {hi:.1f}':>19s}{mav:9.2f}{rms:9.2f}{mav / rms if rms else 0:9.2f}")
        (con if is_contract(l) else rest).append((mav, rms, hi - lo))
    if rest and con:
        rr = np.mean([r[1] for r in rest]); cr = np.mean([c[1] for c in con])
        print(f"\n이완 RMS {rr:.2f} · 수축 RMS {cr:.2f} → 수축/이완 {cr / rr:.1f}배,  SNR = 20·log10({cr:.1f}/{rr:.2f}) = {20 * np.log10(cr / rr):.1f} dB")
        print(f"이완 MAV {np.mean([r[0] for r in rest]):.2f} · 수축 MAV {np.mean([c[0] for c in con]):.2f},  수축 filt 범위는 이완의 {np.mean([c[2] for c in con]) / np.mean([r[2] for r in rest]):.1f}배")
    plt = plt_(); fig, ax = plt.subplots(2, 1, sharex=True, figsize=(10, 5))
    ax[0].plot(d["t"], d["f"], lw=0.4); ax[0].set_ylabel("filt"); ax[1].plot(d["t"], d["rms"], "r", lw=0.8); ax[1].set_ylabel("RMS (100 ms)")
    for l, s, e in segs:
        for x in ax: x.axvspan(s, e, color="tab:orange" if is_contract(l) else "tab:blue", alpha=0.12)
    ax[1].set_xlabel("시간 (초)"); [x.grid(alpha=.3) for x in ax]; ax[0].set_title("주황 = 수축 구간, 파랑 = 이완 구간")
    save(fig, a.file, "time")

# ------------------------------------------------------------ spec
def mdf_mnf(f, nper=256):
    from scipy import signal
    fr, P = signal.welch(f, fs=FS, nperseg=min(nper, len(f)))
    k = (fr >= 20) & (fr <= 450); fr, P = fr[k], P[k]
    c = np.cumsum(P); mdf = fr[np.searchsorted(c, c[-1] / 2)]; mnf = float((fr * P).sum() / P.sum())
    return fr, P, float(mdf), mnf

def cmd_spec(a):
    d = load(a.file); segs = get_segs(a, d); n = len(d["f"])
    if a.signal == "raw":
        if "x" not in d: sys.exit("원신호 x 열이 없다")
        sig = d["x"] - np.mean(d["x"]); print("※ --signal raw: DC 만 뺀 원신호의 스펙트럼 (60 Hz · 느린 움직임이 그대로 보인다)")
    else: sig = d["f"]
    plt = plt_(); fig, ax = plt.subplots(figsize=(8, 4))
    print(f"{'구간':<11s}{'시각(초)':>13s}{'MNF(Hz)':>9s}{'MDF(Hz)':>9s}{'최대(Hz)':>9s}{'60Hz 비율':>10s}")
    for l, s, e in segs:
        i0, i1 = idx(s, e, n, 0.2 if e - s > 1 else 0)
        if i1 - i0 < 256: continue
        fr, P, mdf, mnf = mdf_mnf(sig[i0:i1])
        r60 = P[(fr > 57) & (fr < 63)].sum() / P.sum() * 100
        print(f"{l:<11s}{s:6.1f}~{e:5.1f}{mnf:9.1f}{mdf:9.1f}{fr[np.argmax(P)]:9.1f}{r60:9.1f}%")
        ax.semilogy(fr, P, lw=1, label=f"{l} {s:.0f}~{e:.0f}s (MDF {mdf:.0f})")
    ax.axvline(60, color="gray", ls=":"); ax.set_xlabel("주파수 (Hz)"); ax.set_ylabel("PSD"); ax.legend(fontsize=7); ax.grid(alpha=.3)
    save(fig, a.file, "spec_raw" if a.signal == "raw" else "spec")

# ------------------------------------------------------------ force
def cmd_force(a):
    d = load(a.file); segs = get_segs(a, d); n = len(d["f"])
    rest = [d["rms"][slice(*idx(s, e, n, 0.3))].mean() for l, s, e in segs if l.startswith("rest") and e - s >= 1]
    r0 = float(np.mean(rest)) if rest else 0.0
    lv = [(int(l[1:]), *idx(s, e, n, 0.5)) for l, s, e in segs if l.startswith("f") and l[1:].isdigit()]
    if len(lv) < 2: sys.exit("레이블에 f10, f25 처럼 노력 단계가 2개 이상 필요하다")
    eff = np.array([v[0] for v in lv], float); R = np.array([d["rms"][i0:i1].mean() for _, i0, i1 in lv])
    C = np.sqrt(np.maximum(R ** 2 - r0 ** 2, 0)); mx = C.max()
    print(f"이완 RMS (잡음) = {r0:.2f}")
    print(f"{'노력(%)':>7s}{'RMS':>9s}{'잡음보정':>10s}{'최대 대비':>10s}")
    for e_, r_, c_ in zip(eff, R, C): print(f"{e_:7.0f}{r_:9.2f}{c_:10.2f}{c_ / mx * 100:9.0f}%")
    p = np.polyfit(eff, C, 1); pred = np.polyval(p, eff); r2 = 1 - ((C - pred) ** 2).sum() / ((C - C.mean()) ** 2).sum()
    print(f"\n직선: 잡음보정 RMS = {p[0]:.2f} × 노력 {p[1]:+.1f},  R² = {r2:.3f}")
    print(f"→ 노력 40 % 예측 RMS = {np.polyval(p, 40):.1f}  (직선이 아니면 R² 가 낮다. EMG 는 힘이 아니라 근활성도)")
    plt = plt_(); fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot(eff, C, "o", ms=7); xx = np.linspace(0, 100, 50); ax[0].plot(xx, np.polyval(p, xx), "r--", label=f"직선 R²={r2:.3f}")
    ax[0].set_xlabel("노력 단계 (%)"); ax[0].set_ylabel("잡음 보정 RMS (count)"); ax[0].legend(); ax[0].grid(alpha=.3)
    ax[1].bar(eff, C / mx * 100, width=8); ax[1].set_xlabel("노력 단계 (%)"); ax[1].set_ylabel("최대 대비 RMS (%)"); ax[1].grid(alpha=.3)
    save(fig, a.file, "force")

# ------------------------------------------------------------ detect
def score(st, segs, n):
    on = runs(st == 2); con = [idx(s, e, n) for l, s, e in segs if is_contract(l)]
    hit = [any(a0 < c1 and a1 > c0 for a0, a1 in on) for c0, c1 in con]
    false = sum(1 for a0, a1 in on if not any(a0 < c1 and a1 > c0 for c0, c1 in con))
    delay = [min([a0 for a0, a1 in on if c0 - 200 <= a0 < c1] or [np.nan]) - c0 for c0, c1 in con]
    trans = int((np.diff(st[int(BASE[1] * FS):]) != 0).sum())
    dl = np.nanmean(delay) if not np.all(np.isnan(delay)) else np.nan
    return trans, len(con) - sum(hit), false, dl

def cmd_detect(a):
    d = load(a.file); segs = get_segs(a, d); n = len(d["f"]); rms = d["rms"]; mu, sd = baseline(rms)
    ks = [float(k) for k in a.k.split(",")]
    print(f"기저선 (0.5~3.0초 RMS): 평균 mu {mu:.2f}, 표준편차 sd {sd:.2f} (하한 0.2·mu 적용)")
    print(f"진짜 수축 {sum(1 for l, s, e in segs if is_contract(l))}번 → 전환은 2배가 맞다\n")
    print(f"{'방법':<20s}{'ON 임계':>9s}{'OFF 임계':>9s}{'전환':>6s}{'놓침':>6s}{'오검출':>7s}{'시작 지연(ms)':>14s}")
    rows = []
    for k in ks:
        rows.append((f"k={k:g} 히스테리시스", k, 0.6 * k, False))
        if k == ks[0]: rows.append((f"k={k:g} 단일 임계", k, k, True))
    res = []
    for name, kon, koff, single in rows:
        st = rule_states(rms, kon, koff, single=single); t, m, f, dl = score(st, segs, n); res.append((name, st))
        print(f"{name:<20s}{mu + kon * sd:9.2f}{mu + koff * sd:9.2f}{t:6d}{m:6d}{f:7d}{dl:14.0f}")
    if d["src"] == "board":
        t, m, f, dl = score(d["st"], segs, n); print(f"{'펌웨어 (k=5/3)':<20s}{'-':>9s}{'-':>9s}{t:6d}{m:6d}{f:7d}{dl:14.0f}")
    plt = plt_(); fig, ax = plt.subplots(2, 1, sharex=True, figsize=(10, 5.5))
    ax[0].plot(d["t"], rms, "r", lw=0.8, label="RMS")
    for j, k in enumerate(ks): ax[0].axhline(mu + k * sd, ls="--", lw=0.9, color=f"C{j + 1}", label=f"ON k={k:g}")
    for l, s, e in segs:
        if is_contract(l): ax[0].axvspan(s, e, color="tab:green", alpha=0.12)
    ax[0].legend(fontsize=7); ax[0].set_ylabel("RMS"); ax[0].set_title("초록 = 실제 수축 (레이블)")
    ax[1].plot(d["t"], d["st"], lw=1.2, label="펌웨어 판정" if d["src"] == "board" else "규칙 판정"); ax[1].set_yticks([0, 1, 2]); ax[1].set_yticklabels(["보정", "이완", "수축"])
    ax[1].set_xlabel("시간 (초)"); [x.grid(alpha=.3) for x in ax]; ax[1].legend(fontsize=7)
    save(fig, a.file, "detect")

# ------------------------------------------------------------ fatigue
def cmd_fatigue(a):
    d = load(a.file); segs = get_segs(a, d); n = len(d["f"])
    con = [(l, s, e) for l, s, e in segs if is_contract(l)]
    if not con: sys.exit("수축(contract) 구간이 레이블에 없다")
    l, s, e = max(con, key=lambda v: v[2] - v[1]); s1, e1 = s + 1.0, e - 1.0       # 양끝 1초는 뺀다
    T, M, R = [], [], []
    w = s1
    while w + 1.0 <= e1:
        i0, i1 = int(w * FS), int((w + 1.0) * FS); _, _, mdf, _ = mdf_mnf(d["f"][i0:i1])
        T.append(w + 0.5); M.append(mdf); R.append(np.sqrt(np.mean(d["f"][i0:i1] ** 2))); w += 0.5
    T, M, R = map(np.array, (T, M, R))
    if len(T) < 5: sys.exit("수축 구간이 너무 짧다 (최소 4초 이상)")
    p = np.polyfit(T, M, 1); r2 = 1 - ((M - np.polyval(p, T)) ** 2).sum() / ((M - M.mean()) ** 2).sum()
    pr = np.polyfit(T, R, 1)
    first, last = M[T < T[0] + 10].mean(), M[T > T[-1] - 10].mean()
    rf, rl = R[T < T[0] + 10].mean(), R[T > T[-1] - 10].mean()
    print(f"수축 구간 {s:.1f}~{e:.1f}초 (양끝 1초 제외), 창 1초 · 간격 0.5초 → {len(T)}개")
    print(f"MDF 처음 10초 평균 {first:.1f} Hz → 마지막 10초 {last:.1f} Hz  ({(last - first) / first * 100:+.1f} %)")
    print(f"MDF 기울기 {p[0] * 60:+.1f} Hz/분,  R² = {r2:.2f}")
    print(f"RMS 처음 10초 {rf:.1f} → 마지막 10초 {rl:.1f}  ({(rl - rf) / rf * 100:+.1f} %),  기울기 {pr[0] * 60:+.1f}/분")
    print("→ 기울기가 음수이고 R² 가 충분히 크면 피로 경향. 양수이거나 R² 가 작으면 '피로 경향 없음' 일 수 있다 (진단 아님)")
    plt = plt_(); fig, ax = plt.subplots(2, 1, sharex=True, figsize=(9, 5.5))
    ax[0].plot(T, M, "o", ms=3); ax[0].plot(T, np.polyval(p, T), "r--", label=f"{p[0] * 60:+.1f} Hz/분, R²={r2:.2f}"); ax[0].set_ylabel("MDF (Hz)"); ax[0].legend()
    ax[1].plot(T, R, "o", ms=3, color="tab:orange"); ax[1].plot(T, np.polyval(pr, T), "k--"); ax[1].set_ylabel("RMS (1초 창)"); ax[1].set_xlabel("시간 (초)")
    [x.grid(alpha=.3) for x in ax]; save(fig, a.file, "fatigue")

# ------------------------------------------------------------ bipolar
def cmd_bipolar(a):
    d1 = load(a.file, 1)
    head = open(a.file, encoding="utf-8-sig").readline()
    if "filt2" not in head: sys.exit("2채널 기록이 아니다 (viz.py record ... emg2 로 기록, 펌웨어 NCH 2)")
    d2 = load(a.file, 2); segs = get_segs(a, d1); n = len(d1["f"])
    print(f"{'구간':<8s}{'ch1(이두) RMS':>14s}{'ch2(삼두) RMS':>14s}{'약한쪽/강한쪽':>14s}")
    for typ in ("rest", "flex", "ext"):
        sel = [idx(s, e, n, 0.3) for l, s, e in segs if l.startswith(typ)]
        if not sel: continue
        r1 = np.mean([d1["rms"][i0:i1].mean() for i0, i1 in sel]); r2 = np.mean([d2["rms"][i0:i1].mean() for i0, i1 in sel])
        print(f"{typ:<8s}{r1:14.2f}{r2:14.2f}{min(r1, r2) / max(r1, r2):14.2f}")
    k0 = int(BASE[1] * FS); e1 = d1["rms"][k0:]; e2 = d2["rms"][k0:]
    e1n, e2n = e1 / e1.max(), e2 / e2.max()
    cci = 2 * np.minimum(e1n, e2n).sum() / (e1n + e2n).sum(); r = np.corrcoef(e1, e2)[0, 1]
    print(f"\nCCI (0 = 번갈아, 1 = 항상 같이) = {cci:.2f},  상관 r = {r:+.2f} (음수 = 번갈아)")
    plt = plt_(); fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(d1["t"], d1["rms"], label="ch1 이두"); ax.plot(d2["t"], d2["rms"], label="ch2 삼두")
    for l, s, e in segs:
        if l.startswith("flex"): ax.axvspan(s, e, color="tab:blue", alpha=0.1)
        if l.startswith("ext"): ax.axvspan(s, e, color="tab:orange", alpha=0.1)
    ax.set_xlabel("시간 (초)"); ax.set_ylabel("RMS"); ax.legend(); ax.grid(alpha=.3); ax.set_title("파랑 띠 = 굽힘, 주황 띠 = 폄")
    save(fig, a.file, "bipolar")

class Tee:
    """화면에 찍으면서 txt 에도 모은다"""
    def __init__(self): self.buf = []; self.out = sys.stdout
    def write(self, s): self.out.write(s); self.buf.append(s)
    def flush(self): self.out.flush()
    def save(self, path):
        sys.stdout = self.out
        with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f: f.write("".join(self.buf))
        print(f"(이 내용은 {path} 에도 저장됨)")

def main():
    if len(sys.argv) < 3:
        print(open(__file__, encoding="utf-8").read().split("import sys")[0]); return
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["time", "spec", "force", "detect", "fatigue", "bipolar"]); ap.add_argument("file")
    ap.add_argument("--labels"); ap.add_argument("--seg"); ap.add_argument("--auto", action="store_true")
    ap.add_argument("--signal", default="filt", choices=["filt", "raw"]); ap.add_argument("--k", default="3,5,8")
    a = ap.parse_args()
    t = Tee(); sys.stdout = t
    try: {"time": cmd_time, "spec": cmd_spec, "force": cmd_force, "detect": cmd_detect, "fatigue": cmd_fatigue, "bipolar": cmd_bipolar}[a.cmd](a)
    finally: t.save(os.path.splitext(a.file)[0] + "_" + (a.cmd if not (a.cmd == "spec" and a.signal == "raw") else "spec_raw") + ".txt")

if __name__ == "__main__": main()
