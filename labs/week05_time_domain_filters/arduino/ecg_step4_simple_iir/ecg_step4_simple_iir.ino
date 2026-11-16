// ============================================================
//  5주차 디지털필터(시간영역) 실습
//  Step 4 — Simple IIR Low-pass 필터 (교재 슬라이드 24)
// ------------------------------------------------------------
//  규칙 : y[n] = α · y[n-1] + (1-α) · x[n]
//         이전 출력을 α만큼, 새 입력을 (1-α)만큼 섞음 (재귀)
//  차이 : 배열이 아니라 변수 하나(이전 출력)만 기억하면 된다
//
//     α     특징              -3dB 차단   시정수
//    0.3   빠르지만 덜 부드러움   55.2Hz     3.3ms
//    0.5   중간                 28.8Hz     5.8ms
//    0.7   부드럽고 조금 늦음     14.3Hz    11.2ms
//
//  출력 : "Raw,A03,A05,A07"  (α 3개를 동시에 계산) → python/plot_step4_iir.py
//
//  직접 해보기 (슬라이드 27) :
//     응용 A — 목표 지연(예: 10ms)을 먼저 정하고 위 표에서 α를 역으로 고른다
//     응용 B — Median → IIR 직렬 연결  → ecg_step4b_median_iir.ino
// ============================================================

const int ADC_PIN = 34;   // GPIO34 (ADC1)

const float ALPHA_A03 = 0.3f;
const float ALPHA_A05 = 0.5f;
const float ALPHA_A07 = 0.7f;

// ※ y1 처럼 짧게 쓰면 <math.h>의 y1() 함수와 이름이 겹쳐 컴파일 오류가 날 수 있다
float iir_y_a03 = 0;      // 각 α의 이전 출력
float iir_y_a05 = 0;
float iir_y_a07 = 0;
bool  iir_ready = false;

// 세 α의 계산 방식은 같고 계수만 다르므로 공통 계산을 함수 하나로 뽑아 세 번 호출
float iir_step(float y_prev, float alpha, int x) {
  return alpha * y_prev + (1.0f - alpha) * x;   // 1.0f: ESP32 float 연산기 활용
}

void setup() {
  Serial.begin(115200);
}

void loop() {
  static unsigned long next = micros();
  if ((long)(micros() - next) >= 0) {
    next += 4000;                        // 250Hz
    int raw = analogRead(ADC_PIN);

    if (!iir_ready) {                    // 첫 입력으로 시작
      iir_y_a03 = raw;
      iir_y_a05 = raw;
      iir_y_a07 = raw;
      iir_ready = true;
    }

    iir_y_a03 = iir_step(iir_y_a03, ALPHA_A03, raw);
    iir_y_a05 = iir_step(iir_y_a05, ALPHA_A05, raw);
    iir_y_a07 = iir_step(iir_y_a07, ALPHA_A07, raw);

    Serial.print(raw);
    Serial.print(",");
    Serial.print((int)iir_y_a03);  Serial.print(",");
    Serial.print((int)iir_y_a05);  Serial.print(",");
    Serial.println((int)iir_y_a07);
  }
}
