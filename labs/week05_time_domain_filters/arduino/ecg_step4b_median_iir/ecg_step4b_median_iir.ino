// ============================================================
//  5주차 디지털필터(시간영역) 실습
//  Step 4-B — 응용 B : Median → IIR 직렬 연결 (교재 슬라이드 27)
// ------------------------------------------------------------
//  Step 3의 median_filter()를 가져와, IIR에 raw 대신 median_filter(raw)를 입력
//  → 스파이크(Median 제거)와 잔떨림(IIR 완화)을 동시에 줄인 결과를
//    IIR 단독 적용과 나란히 비교한다
//
//  출력 : "Raw,Median,IIR_raw,IIR_med"  → python/plot_step4b_median_iir.py
//     IIR_raw : raw            → IIR(α)      (IIR 단독)
//     IIR_med : raw → Median   → IIR(α)      (직렬 연결)
// ============================================================

const int ADC_PIN = 34;   // GPIO34 (ADC1)

// ---------- Median (Step 3과 동일) ----------
const int MED_N = 5;
int  med_buf[MED_N];
bool med_ready = false;

int median_filter(int x) {
  if (!med_ready) {
    for (int i = 0; i < MED_N; i++) med_buf[i] = x;
    med_ready = true;
  }
  for (int i = 0; i < MED_N - 1; i++) med_buf[i] = med_buf[i + 1];
  med_buf[MED_N - 1] = x;
  int s[MED_N];
  for (int i = 0; i < MED_N; i++) s[i] = med_buf[i];
  for (int i = 0; i < MED_N; i++)
    for (int j = i + 1; j < MED_N; j++)
      if (s[i] > s[j]) { int t = s[i]; s[i] = s[j]; s[j] = t; }
  return s[MED_N / 2];
}

// ---------- Simple IIR (Step 4와 동일) ----------
const float ALPHA = 0.7f;   // 응용 A에서 고른 α로 바꿔도 된다 (0.3 / 0.5 / 0.7)

float iir_y_raw = 0;        // IIR 단독      의 이전 출력
float iir_y_med = 0;        // Median → IIR  의 이전 출력
bool  iir_ready = false;

float iir_step(float y_prev, float alpha, int x) {
  return alpha * y_prev + (1.0f - alpha) * x;
}

void setup() {
  Serial.begin(115200);
}

void loop() {
  static unsigned long next = micros();
  if ((long)(micros() - next) >= 0) {
    next += 4000;                        // 250Hz
    int raw = analogRead(ADC_PIN);
    int med = median_filter(raw);

    if (!iir_ready) {
      iir_y_raw = raw;
      iir_y_med = med;
      iir_ready = true;
    }
    iir_y_raw = iir_step(iir_y_raw, ALPHA, raw);   // IIR 단독
    iir_y_med = iir_step(iir_y_med, ALPHA, med);   // Median → IIR

    Serial.print(raw);             Serial.print(",");
    Serial.print(med);             Serial.print(",");
    Serial.print((int)iir_y_raw);  Serial.print(",");
    Serial.println((int)iir_y_med);
  }
}
