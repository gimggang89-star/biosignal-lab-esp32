5주차 디지털필터(시간영역) 실습 — 코드 모음
=====================================================
교재: "5. ECG 노이즈와 디지털필터_시간영역_실습" (34장)
보드: ESP32 + BioAmp EXG Pill   /   배선: VCC→3.3V · GND→GND · OUT→GPIO34
샘플링: 250Hz (micros() 타이머, 4ms)   /   Baud: 115200

폴더 구성
---------
arduino/                              ← Arduino IDE에서 폴더째 열기 (폴더명 = 스케치명)
  ecg_step1_polarity/          슬라이드  8  극성 자가진단 (Serial Plotter로 R파 방향 확인)
  ecg_step2_moving_average/    슬라이드 12  Moving Average          출력 Raw,MA
  ecg_step3_median/            슬라이드 18  Median (+MA)            출력 Raw,MA,Median
  ecg_step4_simple_iir/        슬라이드 24  Simple IIR α 0.3/0.5/0.7 출력 Raw,A03,A05,A07
  ecg_step4b_median_iir/       슬라이드 27  응용 B Median→IIR 직렬   출력 Raw,Median,IIR_raw,IIR_med
  ecg_step5_all_filters/       슬라이드 29~30  4단 종합              출력 Raw,MA,Median,IIR

python/                               ← 각 스케치의 출력을 실시간 그래프로
  plot_step2_ma.py             슬라이드 14  2단 (Raw / MA)
  plot_step3_median.py         슬라이드 20  3단 (Raw / MA / Median)
  plot_step4_iir.py            슬라이드 26  4단 (Raw / α=0.3 / 0.5 / 0.7)
  plot_step4b_median_iir.py    슬라이드 27  4단 (Raw / Median / IIR단독 / Median→IIR)
  plot_step5_all.py            슬라이드 30  4단 (Raw / MA / Median / IIR)

실행 순서 (매 단계 공통)
------------------------
1. Arduino IDE: Tools → Board "ESP32 Dev Module", Port 확인, 스케치 업로드
   (업로드 중 "Failed to connect" → ESP32의 BOOT 버튼을 누른 채 재시도)
2. Serial Monitor(115200)로 숫자가 쉼표 구분으로 찍히는지 확인
3. ★ Serial Monitor / Serial Plotter 를 닫는다 (파이썬과 포트 동시 사용 불가)
4. 파이썬 파일 상단의 PORT = "COM5" 를 내 포트로 수정
   (Windows: 장치관리자 → 포트(COM & LPT) / Mac: "/dev/cu.usbserial-…")
5. 터미널:  pip install pyserial matplotlib   (처음 한 번)
            python plot_stepN_xxx.py

직접 해보기 — 바꾸는 위치
--------------------------
슬라이드 15  Moving Average N 비교   ecg_step2  const int MA_N = 8;        → 4 · 8 · 16 · 32
슬라이드 21  Median 창 크기 비교      ecg_step3  const int MED_N = 5;       → 3 · 5 · 7  (홀수만)
슬라이드 27  응용 A 목표 지연으로 α   ecg_step4  ALPHA_A03/05/07 중 하나를 골라 사용
                                       (시정수: 0.3→3.3ms, 0.5→5.8ms, 0.7→11.2ms)
슬라이드 27  응용 B Median→IIR        ecg_step4b 그대로 실행 (ALPHA 변경 가능)
※ 파이썬 그래프 제목의 N, α 값은 코드 상단 titles 에서 같이 바꿔 주면 헷갈리지 않음

제출
----
조별 기록표: 슬라이드 15 · 21 · 26 · 29 의 표를 사진 또는 파일로 제출

주의
----
- VCC/GND를 반대로 꽂으면 BioAmp가 손상될 수 있음 — 전원 연결 전 재확인
- 극성(Step 1)에서 R파가 아래로 향하면 IN+(오른팔)/IN−(왼팔) 전극을 서로 바꿔 붙인다 (REF 그대로)
- 오늘 세 필터 모두 60Hz 전원잡음과 느린 기저선 변동은 못 잡는다 → 6주차 High-pass · Notch · FIR
