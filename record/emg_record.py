"""
ESP32 + BioAmp EXG Pill — 근전도(EMG) 측정 데이터를 JSON으로 저장
================================================================
사용법
  1) pip install pyserial
  2) 아래 PORT 를 본인 것으로 변경 (Arduino IDE의 Tools → Port)
  3) Arduino의 Serial Monitor / Serial Plotter 를 닫는다 (포트 충돌 방지)
  4) 실행:  python emg_record.py
  → 측정 중 근육에 힘을 주었다 풀었다(예: 주먹 쥐기) 몇 번 반복하세요.
  → 끝나면 같은 폴더에 emg_YYYYMMDD_HHMMSS.json 파일이 생깁니다.

※ EMG는 250000 baud, 500Hz 입니다. 아두이노 스케치도 BAUD 250000 이어야 합니다.
   저장되는 raw 로 웹 뷰어(emg_viewer.html)가 밴드패스·정류·활성도를 다시 계산합니다.
"""
import serial, json, time
from datetime import datetime

# ── 설정 ──────────────────────────────────────────────
PORT     = 'COM4'      # ← 본인 포트로 변경 (Mac은 '/dev/cu.usbserial-0001')
BAUD     = 250000      # EMG 스케치와 동일하게!
DURATION = 20.0        # 측정 시간(초) — 그동안 힘주기/풀기 몇 번 반복
RATE_HZ  = 500         # EMG 명목 샘플링
# ─────────────────────────────────────────────────────

def parse(line):
    """'Raw:1234,ENV:56' → (1234, 56).  못 읽으면 (None, None)."""
    raw = env = None
    for tok in line.split(','):
        tok = tok.strip()
        if ':' not in tok:
            continue
        k, v = tok.split(':', 1)
        k = k.strip().lower()
        try:
            if   k == 'raw': raw = int(v)
            elif k == 'env': env = int(v)
        except ValueError:
            return None, None
    return raw, env

ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2.0)
ser.reset_input_buffer()
ser.readline()

t_ms, raw_list, env_list = [], [], []
print(f"측정 시작 — {DURATION:.0f}초 동안 근육에 힘주기/풀기를 몇 번 반복하세요!")
t0 = time.perf_counter()
next_report = 5.0
while True:
    now = time.perf_counter() - t0
    if now >= DURATION:
        break
    line = ser.readline().decode(errors='ignore').strip()
    if not line:
        continue
    raw, env = parse(line)
    if raw is None:
        continue
    t_ms.append(round(now * 1000, 1))
    raw_list.append(raw)
    env_list.append(env if env is not None else 0)
    if now >= next_report:
        print(f"  {now:4.1f}s / {DURATION:.0f}s   ({len(raw_list)} samples)")
        next_report += 5.0
ser.close()

eff = round(len(raw_list) / DURATION, 1) if DURATION else 0
out = {
    "device":            "ESP32 + BioAmp EXG Pill",
    "channel":           "EMG",
    "sample_rate_hz":    RATE_HZ,
    "effective_rate_hz": eff,
    "recorded_at":       datetime.now().isoformat(timespec="seconds"),
    "duration_s":        DURATION,
    "n_samples":         len(raw_list),
    "columns":           ["t_ms", "raw", "env"],
    "data": { "t_ms": t_ms, "raw": raw_list, "env": env_list },
}
fname = f"emg_{datetime.now():%Y%m%d_%H%M%S}.json"
with open(fname, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)

print(f"\n저장 완료 → {fname}")
print(f"  샘플 수: {len(raw_list)}개,  실측 레이트: {eff} Hz")
if eff < RATE_HZ * 0.8:
    print("  ⚠ 실측 레이트가 낮습니다 — BAUD가 250000인지, 아두이노 스케치가 EMG용인지 확인하세요.")
