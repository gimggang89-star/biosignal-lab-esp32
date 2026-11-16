"""
ESP32 + BioAmp EXG Pill — 안구전위도(EOG) 측정 데이터를 JSON으로 저장 · 수평(Horizontal)
================================================================
사용법
  1) pip install pyserial
  2) 아래 PORT 를 본인 것으로 변경 (Arduino IDE의 Tools → Port)
  3) Arduino의 Serial Monitor / Serial Plotter 를 닫는다 (포트 충돌 방지)
  4) 실행:  python eog_record.py
  → 측정 중 눈을 '왼쪽 → 정면 → 오른쪽 → 정면'으로 천천히 여러 번 움직이세요.
    (고개는 고정, 눈동자만! 깜빡임은 최소화)
  → 끝나면 같은 폴더에 eog_YYYYMMDD_HHMMSS.json 파일이 생깁니다.

※ EOG는 75Hz, 115200 baud 입니다. 저장되는 raw 로 웹 뷰어(eog_viewer.html)가
   드리프트 제거·밴드패스를 다시 계산합니다.
"""
import serial, json, time
from datetime import datetime

# ── 설정 ──────────────────────────────────────────────
PORT     = 'COM4'      # ← 본인 포트로 변경 (Mac은 '/dev/cu.usbserial-0001')
BAUD     = 115200
DURATION = 24.0        # 측정 시간(초) — 그동안 좌/우 안구 이동 반복
RATE_HZ  = 75          # EOG 명목 샘플링
# ─────────────────────────────────────────────────────

def parse(line):
    """'Raw:2048,EOG:2010' → (2048, 2010).  못 읽으면 (None, None)."""
    raw = eog = None
    for tok in line.split(','):
        tok = tok.strip()
        if ':' not in tok:
            continue
        k, v = tok.split(':', 1)
        k = k.strip().lower()
        try:
            if   k == 'raw': raw = int(v)
            elif k == 'eog': eog = int(v)
        except ValueError:
            return None, None
    return raw, eog

ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2.0)
ser.reset_input_buffer()
ser.readline()

t_ms, raw_list, eog_list = [], [], []
print(f"측정 시작 — {DURATION:.0f}초 동안 눈을 좌/우로 천천히 움직이세요 (고개 고정)!")
t0 = time.perf_counter()
next_report = 5.0
while True:
    now = time.perf_counter() - t0
    if now >= DURATION:
        break
    line = ser.readline().decode(errors='ignore').strip()
    if not line:
        continue
    raw, eog = parse(line)
    if raw is None:
        continue
    t_ms.append(round(now * 1000, 1))
    raw_list.append(raw)
    eog_list.append(eog if eog is not None else 0)
    if now >= next_report:
        print(f"  {now:4.1f}s / {DURATION:.0f}s   ({len(raw_list)} samples)")
        next_report += 5.0
ser.close()

eff = round(len(raw_list) / DURATION, 1) if DURATION else 0
out = {
    "device":            "ESP32 + BioAmp EXG Pill",
    "channel":           "EOG (Horizontal)",
    "sample_rate_hz":    RATE_HZ,
    "effective_rate_hz": eff,
    "recorded_at":       datetime.now().isoformat(timespec="seconds"),
    "duration_s":        DURATION,
    "n_samples":         len(raw_list),
    "columns":           ["t_ms", "raw", "eog"],
    "data": { "t_ms": t_ms, "raw": raw_list, "eog": eog_list },
}
fname = f"eog_{datetime.now():%Y%m%d_%H%M%S}.json"
with open(fname, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)

print(f"\n저장 완료 → {fname}")
print(f"  샘플 수: {len(raw_list)}개,  실측 레이트: {eff} Hz")
