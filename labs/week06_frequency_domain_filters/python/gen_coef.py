# 사용법 (scipy 필요: pip install scipy)
#  python gen_coef.py hpf 0.5        : HPF 2차 Butterworth, 차단주파수 0.5Hz
#  python gen_coef.py notch 60 30    : Notch, 중심 60Hz, Q=30
#  python gen_coef.py fir 51 60      : FIR, 탭 51개, 차단주파수 60Hz (Hamming 창)
# 출력된 줄을 스케치의 계수 부분에 그대로 붙여넣는다 (반올림 금지)
import sys
from scipy import signal
FS = 250

def c_array(name, v):
    return f"const float {name}[{len(v)}] = {{" + ", ".join(f"{x:.8f}f" for x in v) + "};"

kind = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    if kind == "hpf":
        b, a = signal.butter(2, float(sys.argv[2]), btype="high", fs=FS)
        print(c_array("HPF_B", b)); print(c_array("HPF_A", a))
    elif kind == "notch":
        b, a = signal.iirnotch(float(sys.argv[2]), float(sys.argv[3]), fs=FS)
        print(c_array("NOT_B", b)); print(c_array("NOT_A", a))
    elif kind == "fir":
        n = int(sys.argv[2])
        h = signal.firwin(n, float(sys.argv[3]), fs=FS)
        print(f"const int   FIR_N = {n};")
        print(c_array("FIR_H", h).replace(f"FIR_H[{n}]", "FIR_H[FIR_N]"))
    else:
        raise ValueError
except (IndexError, ValueError):
    print(__doc__ if __doc__ else open(__file__, encoding="utf-8").read().split("import")[0])
