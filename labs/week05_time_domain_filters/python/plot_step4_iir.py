# ============================================================
#  5주차 디지털필터(시간영역) 실습
#  Step 4 — Simple IIR α 비교 그래프, 4단 (교재 슬라이드 26)
# ------------------------------------------------------------
#  아두이노 : ecg_step4_simple_iir.ino  (출력 "Raw,A03,A05,A07")
#  실행 전  : PORT 수정 · Serial Monitor 닫기 · pip install pyserial matplotlib
#  실행     : python plot_step4_iir.py
#  화면     : 위에서 아래로 Raw · α=0.3 · 0.5 · 0.7 — 아래로 갈수록 더 부드러워진다
#             (Raw가 갑자기 뛰거나 떨어질 때 A03은 거의 같이 움직이고
#              A07은 훨씬 완만하게 따라간다)
# ============================================================
import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

PORT = "COM5"; BAUD = 115200; WINDOW = 500
ser = serial.Serial(PORT, BAUD, timeout=1)
cols = ["raw", "a03", "a05", "a07"]
data = {c: deque([0]*WINDOW, maxlen=WINDOW) for c in cols}

fig, axes = plt.subplots(4, 1, sharex=True,
                         figsize=(10, 9))
lines = {}
titles = {"raw": "Raw", "a03": "IIR a=0.3",
          "a05": "IIR a=0.5", "a07": "IIR a=0.7"}
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
