"""
ESP32 + BioAmp EXG Pill — 뇌파(EEG) 측정 데이터를 JSON으로 저장
================================================================
사용법
  1) pip install pyserial
  2) 아래 PORT 를 본인 것으로 변경 (Arduino IDE의 Tools → Port)
  3) Arduino의 Serial Monitor / Serial Plotter 를 닫는다 (포트 충돌 방지)
  4) 실행:  python eeg_record.py
  → 화면 안내에 맞춰 '눈 뜨기 / 눈 감기'를 반복하세요.
    ‧ 몸에 힘 빼고 가만히, 이악물기·눈깜빡임 최소화(근전도가 섞임)
    ‧ 눈을 감으면 몇 초 뒤 8~13Hz 알파파가 커집니다(Berger 효과)
  → 끝나면 같은 폴더에 eeg_YYYYMMDD_HHMMSS.json 파일이 생깁니다.

※ EEG는 256Hz, 115200 baud 입니다(ECG·EOG와 동일, EMG의 250000 아님).
   저장되는 raw 로 웹 뷰어(eeg_viewer.html)가 밴드패스·대역별 필터·
   주파수 스펙트럼(FFT)을 다시 계산합니다.
"""
import serial, json, time
from datetime import datetime

# ── 설정 ──────────────────────────────────────────────
PORT     = 'COM4'      # ← 본인 포트로 변경 (Mac은 '/dev/cu.usbserial-0001')
BAUD     = 115200
DURATION = 30.0        # 측정 시간(초)
RATE_HZ  = 256         # EEG 명목 샘플링
# 눈 뜸/감음 프로토콜 (t초부터 해당 상태) — 알파파 비교용
PHASES   = [(0.0, "눈 뜸"), (10.0, "눈 감음"), (20.0, "눈 뜸")]
# ─────────────────────────────────────────────────────

def parse(line):
    """'Raw:2048,EEG:2050' → (2048, 2050).  못 읽으면 (None, None)."""
    raw = eeg = None
    for tok in line.split(','):
        tok = tok.strip()
        if ':' not in tok:
            continue
        k, v = tok.split(':', 1)
        k = k.strip().lower()
        try:
            if   k == 'raw': raw = int(v)
            elif k == 'eeg': eeg = int(v)
        except ValueError:
            return None, None
    return raw, eeg

ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2.0)
ser.reset_input_buffer()
ser.readline()

t_ms, raw_list, eeg_list = [], [], []
print(f"측정 시작 — {DURATION:.0f}초. 안내에 맞춰 눈을 뜨고/감으세요.")
print(f"  ▶ 지금: {PHASES[0][1]} (편하게, 가만히)")
t0 = time.perf_counter()
next_report = 5.0
phase_idx = 1
while True:
    now = time.perf_counter() - t0
    if now >= DURATION:
        break
    # 다음 페이즈 안내
    if phase_idx < len(PHASES) and now >= PHASES[phase_idx][0]:
        print(f"  ▶ 지금: {PHASES[phase_idx][1]}"
              + ("   ← 몇 초 뒤 알파파가 커집니다" if PHASES[phase_idx][1] == "눈 감음" else ""))
        phase_idx += 1
    line = ser.readline().decode(errors='ignore').strip()
    if not line:
        continue
    raw, eeg = parse(line)
    if raw is None:
        continue
    t_ms.append(round(now * 1000, 1))
    raw_list.append(raw)
    eeg_list.append(eeg if eeg is not None else 0)
    if now >= next_report:
        print(f"     {now:4.1f}s / {DURATION:.0f}s   ({len(raw_list)} samples)")
        next_report += 5.0
ser.close()

eff = round(len(raw_list) / DURATION, 1) if DURATION else 0
out = {
    "device":            "ESP32 + BioAmp EXG Pill",
    "channel":           "EEG",
    "sample_rate_hz":    RATE_HZ,
    "effective_rate_hz": eff,
    "recorded_at":       datetime.now().isoformat(timespec="seconds"),
    "duration_s":        DURATION,
    "n_samples":         len(raw_list),
    "events":            [{"t_s": t, "label": lab} for t, lab in PHASES],
    "columns":           ["t_ms", "raw", "eeg"],
    "data": { "t_ms": t_ms, "raw": raw_list, "eeg": eeg_list },
}
fname = f"eeg_{datetime.now():%Y%m%d_%H%M%S}.json"
with open(fname, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)

print(f"\n저장 완료 → {fname}")
print(f"  샘플 수: {len(raw_list)}개,  실측 레이트: {eff} Hz")
if eff < RATE_HZ * 0.8:
    print("  ⚠ 실측 레이트가 낮습니다 — BAUD 115200·아두이노 스케치가 EEG용(256Hz)인지 확인하세요.")
print("  → eeg_viewer.html 에 끌어놓아 밴드/스펙트럼을 확인하세요. '눈 감음' 구간에서 알파파를 보세요.")
