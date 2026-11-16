# ============================================================
#  5주차 디지털필터(시간영역) 실습
#  Step 5 — 4단 종합 시각화 : Raw · MA · Median · IIR (교재 슬라이드 30)
# ------------------------------------------------------------
#  아두이노 : ecg_step5_all_filters.ino  (출력 "Raw,MA,Median,IIR")
#  실행 전  : PORT 수정 · Serial Monitor 닫기 · pip install pyserial matplotlib
#  실행     : python plot_step5_all.py
#  화면     : 오늘 배운 세 필터의 차이가 한눈에 — 20·26번 코드를 4단(raw,ma,med,iir)으로 확장
#
#  60Hz 관찰 (슬라이드 31) : 배터리 → 충전기 연결 순서로 측정하면서
#             Raw의 고주파 잔떨림이 두꺼워지는지, 세 필터가 얼마나 눌러 주는지 비교
# ============================================================
import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

PORT = "COM4"; BAUD = 115200; WINDOW = 500
ser = serial.Serial(PORT, BAUD, timeout=1)
cols = ["raw", "ma", "med", "iir"]
data = {c: deque([0]*WINDOW, maxlen=WINDOW) for c in cols}

fig, axes = plt.subplots(4, 1, sharex=True,
                         figsize=(10, 9))
lines = {}
titles = {"raw": "Raw ECG", "ma": "Moving Average (N=8)",
          "med": "Median (N=5)", "iir": "Simple IIR (a=0.7)"}
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
                data[c].append(float(v))
        except ValueError:
            continue
    for c in cols:
        lines[c].set_ydata(data[c])
    return list(lines.values())

ani = FuncAnimation(fig, update, interval=30,
                    cache_frame_data=False)
plt.tight_layout()
plt.show()