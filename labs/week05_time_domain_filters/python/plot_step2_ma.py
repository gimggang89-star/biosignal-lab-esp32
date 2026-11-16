# ============================================================
#  5주차 디지털필터(시간영역) 실습
#  Step 2 — Moving Average 실시간 시각화 (교재 슬라이드 14)
# ------------------------------------------------------------
#  아두이노 : ecg_step2_moving_average.ino  (출력 "Raw,MA")
#  실행 전  : ① PORT 를 내 장치관리자/시스템정보의 포트 번호로 수정
#             ② Arduino Serial Monitor/Plotter 를 반드시 닫아 둘 것 (포트 동시 사용 불가)
#             ③ pip install pyserial matplotlib
#  실행     : python plot_step2_ma.py
#  화면     : 위 Raw ECG(잔털 있음) / 아래 Moving Average(더 매끈함)
# ============================================================
import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

PORT   = "COM5"     # 각자 포트로 수정 (Mac: "/dev/cu.usbserial-0001")
BAUD   = 115200
WINDOW = 500        # 약 2초 분량(250Hz)

ser = serial.Serial(PORT, BAUD, timeout=1)
raw_data = deque([0]*WINDOW, maxlen=WINDOW)
ma_data  = deque([0]*WINDOW, maxlen=WINDOW)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               figsize=(10, 6))
line1, = ax1.plot(raw_data)
line2, = ax2.plot(ma_data)
ax1.set_title("Raw ECG");  ax1.set_ylim(0, 4095)
ax2.set_title("Moving Average (N=8)")
ax2.set_ylim(0, 4095)

def update(frame):
    while ser.in_waiting:
        line = ser.readline().decode(
            errors="ignore").strip()
        try:
            r, m = line.split(",")
            raw_data.append(int(r))
            ma_data.append(int(m))
        except ValueError:
            continue            # 깨진 줄 무시
    line1.set_ydata(raw_data)
    line2.set_ydata(ma_data)
    return line1, line2

ani = FuncAnimation(fig, update, interval=30,
                    cache_frame_data=False)   # 프레임 캐시 끔(메모리 경고 방지)
plt.tight_layout()
plt.show()
