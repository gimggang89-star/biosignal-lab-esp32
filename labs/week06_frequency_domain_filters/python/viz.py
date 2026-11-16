# 사용법 (pip install numpy matplotlib scipy pyserial)
#  python viz.py live   COM5 hpf            : 시리얼에서 읽어 실시간 그래프 (raw | hpf | notch | fir | chain), 창 닫으면 종료
#  python viz.py record COM5 hpf 30 run.csv : 30초 기록해 run.csv 로 저장
#  python viz.py report run.csv hpf [주입Hz [fc | Q | 탭수]]: 그래프(run.png) 저장 + 숫자 출력.  주입Hz 는 스케치의 INJECT_HZ 값, 마지막 값은 hpf 의 fc(기본 0.5) / notch 의 Q(기본 30) / fir 의 탭 수(기본 51)
#  (live 와 report 는 포트 대신 csv 파일을 줘도 된다: 재생 / 분석)
import sys, time, warnings
import numpy as np
warnings.filterwarnings("ignore")

FS = 250
COLS = {"raw": ["x"], "hpf": ["x", "hpf"], "notch": ["x", "notch"], "fir": ["x", "fir"], "chain": ["x", "hpf", "notch", "fir"]}
TITLE = {"x": "x (입력)", "hpf": "HPF 후", "notch": "Notch 후", "fir": "FIR 후"}

def font():
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Malgun Gothic", "AppleGothic", "NanumGothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt

def read_rows(ser, partial, ncol):
    partial += ser.read(ser.in_waiting or 1).decode(errors="ignore")
    lines = partial.split("\n"); partial = lines.pop()
    rows = []
    for ln in lines:
        p = ln.strip().split(",")
        if len(p) == ncol:
            try: rows.append([float(v) for v in p])
            except ValueError: pass
    return rows, partial

# ---------------- 분석 함수 ----------------
def spec(v):
    """Hann 창 진폭 스펙트럼 (낮은 주파수의 큰 성분이 다른 대역으로 새는 것을 막는다)"""
    v = v - v.mean(); w = np.hanning(len(v))
    return np.abs(np.fft.rfft(v * w)) * 2 / w.sum(), np.fft.rfftfreq(len(v), 1 / FS)

def band_mean(v, lo, hi):
    A, fr = spec(v); return A[(fr >= lo) & (fr <= hi)].mean()

def peak_at(v, f, tol=0.3):
    A, fr = spec(v); m = (fr >= f - tol) & (fr <= f + tol); return A[m].max()

def detrend(v, win=FS):
    k = np.ones(win) / win
    return v - np.convolve(v, k, mode="same")

def delay_ms(a, b):
    """a 에서 b 까지의 지연. 느린 기저선이 상관을 흐트러뜨리므로 1초 이동평균을 뺀 뒤 계산"""
    a, b = detrend(a), detrend(b)
    cc = np.correlate(b - b.mean(), a - a.mean(), "full"); lag = np.argmax(cc) - (len(a) - 1)
    return lag, lag * 1000 / FS

def settle_times(y, ref, fracs=(0.5, 0.1, 0.05)):
    base = np.abs(np.convolve(y, np.ones(25) / 25, mode="same"))[:-13]       # 끝 13샘플은 이동평균이 불완전해서 제외
    out = []
    for f in fracs:
        idx = np.where(base > f * ref)[0]; out.append((idx[-1] + 1) / FS if len(idx) else 0.0)
    return out

def env_at(v, f):
    n = np.arange(len(v)); lo = np.exp(-2j * np.pi * f * n / FS)
    k = np.ones(25) / 25
    return 2 * np.abs(np.convolve(v * lo, k, mode="same"))[:-13]

def report(path, kind, inj, fc=0.5):
    q = fc if (kind == 'notch' and fc != 0.5) else 30.0      # notch 에서는 5번째 값이 Q (안 주면 30)
    taps = int(fc) if kind in ('fir',) and fc != 0.5 else 51    # fir 에서는 5번째 값이 탭 수
    import pandas as pd
    df = pd.read_csv(path); cols = COLS[kind]; df.columns = cols
    seg = df.iloc[int(3 * FS):int(13 * FS)] if len(df) >= 13 * FS else df.iloc[int(min(3 * FS, len(df) // 4)):]
    plt = font()
    t = np.arange(len(df)) / FS
    fig, ax = plt.subplots(len(cols), 1, sharex=True, figsize=(11, 2.2 * len(cols) + 0.6))
    ax = np.atleast_1d(ax)
    for a, c in zip(ax, cols):
        a.plot(t, df[c].values, lw=0.8); a.set_ylabel(TITLE[c]); a.grid(alpha=0.3)
    ax[-1].set_xlabel("시간 (초)"); fig.tight_layout()
    png = path.rsplit(".", 1)[0] + ".png"; fig.savefig(png, dpi=120)
    print(f"그래프 저장: {png}   (구간 {seg.index[0]/FS:.0f}~{seg.index[-1]/FS:.0f}초 기준, 처음 3초는 제외)")
    x = seg["x"].values
    if kind in ("hpf", "chain"):
        y = seg["hpf"].values
        a0, a1 = band_mean(x, 0.1, 0.5), band_mean(y, 0.1, 0.5)
        print(f"[HPF] 0.1~0.5Hz 평균 크기  x {a0:.3f} → hpf {a1:.3f}  (비 {a1/max(a0,1e-9):.2f})")
        if abs(df['x'].values[0]) > 300:                       # START_RESET=false 로 기록한 경우
            s = settle_times(df["hpf"].values, abs(df["x"].values[0]))
            from scipy import signal
            b_, a_ = signal.butter(2, fc, btype="high", fs=FS)
            yt = signal.lfilter(b_, a_, np.full(int(60 * FS), 2000.0))
            th = [(np.where(np.abs(yt) > f * 2000)[0][-1] + 1) / FS for f in (0.5, 0.1, 0.05)]
            print(f"[HPF] 정착시간 50%/10%/5% 이하: {s[0]:.2f} / {s[1]:.2f} / {s[2]:.2f}초  (fc {fc}Hz 이론 {th[0]:.2f} / {th[1]:.2f} / {th[2]:.2f})")
    if kind in ("notch", "chain"):
        y = seg["notch"].values
        a0, a1 = peak_at(x, 60), peak_at(y, 60)
        print(f"[Notch] 60Hz 크기  x {a0:.3f} → notch {a1:.3f}  ({20*np.log10(max(a1,1e-9)/max(a0,1e-9)):.1f}dB)")
        if inj and abs(inj - 60) < 0.05:
            e_in = env_at(df["x"].values, 60); e_out = env_at(df["notch"].values, 60)
            ref = np.median(e_in[2 * FS:4 * FS]); r = e_out / ref
            r = r[:2 * FS]                                    # 처음 2초만 본다 (뒤쪽 R파 성분이 섞이지 않게)
            s = [(np.where(r > f)[0][-1] + 1) / FS if len(np.where(r > f)[0]) else 0 for f in (0.5, 0.05)]
            from scipy import signal
            qq = q if kind == "notch" else 30.0
            b_, a_ = signal.iirnotch(60, qq, fs=FS)
            yt = signal.lfilter(b_, a_, np.sin(2 * np.pi * 60 * np.arange(5000) / FS))
            envt = np.array([np.abs(yt[i:i + 25]).max() for i in range(4900)])
            th = [(np.where(envt > f)[0][-1] + 1) / FS for f in (0.5, 0.05)]
            print(f"[Notch] 60Hz 정착 50%/5% 이하: {s[0]:.2f} / {s[1]:.2f}초  (Q {qq:g} 이론 {th[0]:.2f} / {th[1]:.2f}, 이 도구는 0.05~0.1초 크게 나옴. INJECT_AMP 800 으로 측정)")
    if kind in ("fir", "chain"):
        src = "notch" if kind == "chain" else "x"
        a_, b_ = seg[src].values, seg["fir"].values
        lag, ms = delay_ms(a_, b_)
        th_lag = (taps - 1) // 2
        print(f"[FIR] 지연 {src} → fir: {lag}샘플 = {ms:.0f}ms  (이론 {th_lag}샘플 = {th_lag*1000//FS}ms)")
        a0, a1 = band_mean(a_, 70, 120), band_mean(b_, 70, 120)
        print(f"[FIR] 70~120Hz 평균 크기  {src} {a0:.4f} → fir {a1:.4f}  ({20*np.log10(max(a1,1e-9)/max(a0,1e-9)):.1f}dB, 70Hz 이론 이득은 −54dB. 대역 평균은 더 작게 나올 수 있음)")
    if inj:
        print(f"[주입 {inj}Hz] 단계별 이득 (x 기준):", end=" ")
        ax_ = peak_at(x, inj, 0.3)
        print("  ".join(f"{c} {peak_at(seg[c].values, inj, 0.3)/max(ax_,1e-9):.3f}" for c in cols[1:]))

# ---------------- 실행부 ----------------
def main():
    if len(sys.argv) < 4:
        print(open(__file__, encoding="utf-8").read().split("import sys")[0]); return
    mode, src, kind = sys.argv[1], sys.argv[2], sys.argv[3]
    ncol = len(COLS[kind])
    if mode == "report":
        report(src, kind, float(sys.argv[4]) if len(sys.argv) > 4 else 0, float(sys.argv[5]) if len(sys.argv) > 5 else 0.5); return
    replay = src.endswith(".csv")
    if replay:
        import pandas as pd
        data = pd.read_csv(src).values; pos = 0; t0 = time.time()
        def poll():
            nonlocal pos
            due = min(int((time.time() - t0) * FS), len(data)); out = data[pos:due]; pos = due
            return [list(r) for r in out]
    else:
        import serial
        ser = serial.Serial(src, 115200, timeout=0)
        if mode == "record":                      # 기록은 필터가 켜지는 순간부터 (정착시간을 재려면 필요)
            ser.dtr = False; ser.rts = True       # EN 리셋 (esptool 과 같은 방식) — 리셋 중에는 출력 없음
            time.sleep(0.1); ser.reset_input_buffer()
            ser.rts = False                       # 리셋 해제 → 부팅 메시지는 read_rows 가 걸러낸다
        else:
            time.sleep(2); ser.reset_input_buffer()
        part = [""]
        def poll():
            rows, part[0] = read_rows(ser, part[0], ncol); return rows
    if mode == "record":
        secs, out = float(sys.argv[4]), sys.argv[5]; rows = []; t0 = time.time()
        while time.time() - t0 < secs:
            rows += poll(); time.sleep(0.01)
        with open(out, "w") as f:
            f.write(",".join(COLS[kind]) + "\n")
            for r in rows: f.write(",".join(f"{v:.2f}" for v in r) + "\n")
        print(f"저장: {out} ({len(rows)}샘플 = {len(rows)/FS:.1f}초)")
    elif mode == "live":
        from collections import deque
        plt = font(); from matplotlib.animation import FuncAnimation
        sec = float(sys.argv[4]) if len(sys.argv) > 4 else 8.0; N = int(sec * FS)
        buf = [deque([0.0] * N, maxlen=N) for _ in range(ncol)]
        fig, ax = plt.subplots(ncol, 1, sharex=True, figsize=(11, 2.2 * ncol + 0.6)); ax = np.atleast_1d(ax)
        tt = np.linspace(-sec, 0, N); lines = []
        for a, c in zip(ax, COLS[kind]):
            ln, = a.plot(tt, np.zeros(N), lw=0.8); lines.append(ln); a.set_ylabel(TITLE[c]); a.grid(alpha=0.3)
        ax[-1].set_xlabel("시간 (초, 오른쪽 끝이 지금)")
        def upd(_):
            for r in poll():
                for i in range(ncol): buf[i].append(r[i])
            for i, (a, ln) in enumerate(zip(ax, lines)):
                v = np.array(buf[i]); ln.set_ydata(v)
                lo, hi = v.min(), v.max(); pad = max((hi - lo) * 0.1, 1); a.set_ylim(lo - pad, hi + pad)
            return lines
        ani = FuncAnimation(fig, upd, interval=60, blit=False, cache_frame_data=False)
        plt.show()
main()
