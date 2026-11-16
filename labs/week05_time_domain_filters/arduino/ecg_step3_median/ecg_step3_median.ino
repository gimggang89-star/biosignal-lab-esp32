// ============================================================
//  5주차 디지털필터(시간영역) 실습
//  Step 3 — Median 필터 (교재 슬라이드 18)
// ------------------------------------------------------------
//  규칙 : 최근 N개를 크기순으로 정렬하고 정중앙 값을 출력 (N은 홀수)
//  차이 : Moving Average는 값의 크기를 그대로 반영 / Median은 순위만 보고 크기는 무시
//         → 스파이크는 정렬하면 맨 끝으로 밀려 선택되지 않는다
//  제거 조건 : 연속된 스파이크가 (N-1)/2 샘플 이하일 때만 완전히 제거
//              (N=3 → 1샘플, N=5 → 2샘플, N=7 → 3샘플)
//  출력 : "Raw,MA,Median"  → python/plot_step3_median.py
//
//  직접 해보기 (슬라이드 21) :
//     방법 A — 손을 짧게/길게 흔들거나 케이블을 톡 건드려 스파이크를 만들어 본다
//     방법 B — MED_N 을 3 · 5 · 7 로 바꿔 재업로드하고 제거 한계를 비교
// ============================================================

const int ADC_PIN = 34;   // GPIO34 (ADC1)

// ---------- Moving Average (Step 2와 동일, 이어서 사용) ----------
const int MA_N    = 8;
int  ma_buf[MA_N];
int  ma_idx   = 0;
bool ma_ready = false;

int moving_average(int x) {
  if (!ma_ready) {
    for (int i = 0; i < MA_N; i++) ma_buf[i] = x;
    ma_ready = true;
  }
  ma_buf[ma_idx] = x;
  ma_idx = (ma_idx + 1) % MA_N;
  int sum = 0;
  for (int i = 0; i < MA_N; i++) sum += ma_buf[i];
  return sum / MA_N;
}

// ---------- Median ----------
const int MED_N = 5;      // 창 크기(홀수) ← 21번에서 3/5/7로 바꿔 본다
int  med_buf[MED_N];      // 최근 N개(시간 순서 유지)
bool med_ready = false;

int median_filter(int x) {
  if (!med_ready) {                      // 처음 한 번만 첫 샘플로 채움
    for (int i = 0; i < MED_N; i++)
      med_buf[i] = x;
    med_ready = true;
  }
  for (int i = 0; i < MED_N - 1; i++)    // 한 칸씩 밀고
    med_buf[i] = med_buf[i + 1];
  med_buf[MED_N - 1] = x;                // 새 값 맨 뒤

  int s[MED_N];                          // 복사본만 정렬
  for (int i = 0; i < MED_N; i++)        // (원본을 정렬하면 시간 순서가 망가진다)
    s[i] = med_buf[i];
  for (int i = 0; i < MED_N; i++)
    for (int j = i + 1; j < MED_N; j++)
      if (s[i] > s[j]) {
        int t = s[i]; s[i] = s[j]; s[j] = t;
      }
  return s[MED_N / 2];                   // 정중앙 (N=5 → s[2])
}

void setup() {
  Serial.begin(115200);
}

void loop() {
  static unsigned long next = micros();
  if ((long)(micros() - next) >= 0) {
    next += 4000;                        // 250Hz
    int raw = analogRead(ADC_PIN);
    int ma  = moving_average(raw);
    int med = median_filter(raw);
    Serial.print(raw);  Serial.print(",");
    Serial.print(ma);   Serial.print(",");
    Serial.println(med);
  }
}
