# ============================================================
#  5주차 디지털필터(시간영역) 실습
#  Step 4-B — 응용 B : Median → IIR 직렬 연결 비교 (교재 슬라이드 27)
# ------------------------------------------------------------
#  아두이노 : ecg_step4b_median_iir.ino  (출력 "Raw,Median,IIR_raw,IIR_med")
#  실행 전  : PORT 수정 · Serial Monitor 닫기 · pip install pyserial matplotlib
#  실행     : python plot_step4b_median_iir.py
#  화면     : Raw / Median / IIR 단독 / Median→IIR
#             손을 흔들어 스파이크를 만들었을 때
#             IIR 단독(3번째)은 꼬리가 남고, Median→IIR(4번째)은 거의 반응하지 않는지 비교
# ============================================================
import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

PORT = "COM5"; BAUD = 115200; WINDOW = 500
ser = serial.Serial(PORT, BAUD, timeout=1)
cols = ["raw", "med", "iir_raw", "iir_med"]
data = {c: deque([0]*WINDOW, maxlen=WINDOW) for c in cols}

fig, axes = plt.subplots(4, 1, sharex=True,
                         figsize=(10, 9))
lines = {}
titles = {"raw": "Raw", "med": "Median (N=5)",
          "iir_raw": "IIR a=0.7 (raw -> IIR)",
          "iir_med": "Median -> IIR a=0.7"}
for ax, c in zip(axes, cols):
    lines[c], = ax.plot(data[c])
    ax.set_title(titles[c]); ax.set_ylim(0, 4095)

def update(frame):
    while ser.in_waiting:
        line = ser.readline().decode(
            errors="ignore").strip()
        vals = line.split(",")
        if len(vals) != 4:
            continue
        try:
            for c, v in zip(cols, vals):
                data[c].append(int(v))
        except ValueError:
            continue
    for c in cols:
        lines[c].set_ydata(data[c])
    return list(lines.values())

ani = FuncAnimation(fig, update, interval=30,
                    cache_frame_data=False)
plt.tight_layout()
plt.show()
