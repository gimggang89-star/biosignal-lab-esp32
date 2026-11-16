# ============================================================
#  5주차 디지털필터(시간영역) 실습
#  Step 3 — Median 실시간 시각화, 3단 그래프 (교재 슬라이드 20)
# ------------------------------------------------------------
#  아두이노 : ecg_step3_median.ino  (출력 "Raw,MA,Median")
#  실행 전  : PORT 수정 · Serial Monitor 닫기 · pip install pyserial matplotlib
#  실행     : python plot_step3_median.py
#  기대 화면: 손을 흔들면 맨 위 Raw는 크게 튀고, 가운데 MA는 완만한 혹으로 남고,
#             맨 아래 Median은 거의 반응하지 않는다
#  Step 2에서 바뀐 것: med_data 덱과 세 번째 서브플롯(ax3) 추가,
#                     split(",")가 3개 값을 받도록 수정
# ============================================================
import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

PORT = "COM5"; BAUD = 115200; WINDOW = 500
ser = serial.Serial(PORT, BAUD, timeout=1)
raw_data = deque([0]*WINDOW, maxlen=WINDOW)
ma_data  = deque([0]*WINDOW, maxlen=WINDOW)
med_data = deque([0]*WINDOW, maxlen=WINDOW)

fig, (ax1, ax2, ax3) = plt.subplots(
    3, 1, sharex=True, figsize=(10, 8))
line1, = ax1.plot(raw_data)
line2, = ax2.plot(ma_data)
line3, = ax3.plot(med_data)
ax1.set_title("Raw ECG");      ax1.set_ylim(0, 4095)
ax2.set_title("MA (N=8)");     ax2.set_ylim(0, 4095)
ax3.set_title("Median (N=5)"); ax3.set_ylim(0, 4095)

def update(frame):
    while ser.in_waiting:
        line = ser.readline().decode(
            errors="ignore").strip()
        try:
            r, m, d = line.split(",")
            raw_data.append(int(r))
            ma_data.append(int(m))
            med_data.append(int(d))
        except ValueError:
            continue
    line1.set_ydata(raw_data)
    line2.set_ydata(ma_data)
    line3.set_ydata(med_data)
    return line1, line2, line3

ani = FuncAnimation(fig, update, interval=30,
                    cache_frame_data=False)
plt.tight_layout()
plt.show()
