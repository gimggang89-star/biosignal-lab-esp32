// 실험 3: 고주파 제거 (FIR 51탭, fc 60Hz, Hamming 창) — 출력: x(입력), fir
// 보드: ESP32 Dev Module / 시리얼 115200 / ADC 핀: GPIO34 / 샘플링 250Hz
#include <math.h>

const int   ADC_PIN = 34;                 // GPIO34 (ADC1)
const float FS      = 250.0f;             // 샘플링 250Hz

// ===== 바꿔 볼 값 =====
const float INJECT_HZ   = 65;              // 0: 주입 없음 / 0.3, 60, 80 등: 그 주파수의 사인파를 입력에 더한다
const float INJECT_AMP  = 100;            // 주입 사인파 크기 (ADC 숫자 단위)
const bool  START_RESET = true;           // true: 첫 샘플을 빼서 0 근처에서 시작 / false: 원값(약 2000) 그대로

// ===== FIR 계수 (python gen_coef.py fir 51 60 의 결과) =====
const int   FIR_N = 51;
const float FIR_H[FIR_N] = {-0.00000000f, -0.00093804f, -0.00118474f, -0.00020399f, 0.00160153f, 0.00254494f, 0.00085417f, -0.00299243f, -0.00540756f, -0.00252456f, 0.00497077f, 0.01031472f, 0.00603915f, -0.00728185f, -0.01811480f, -0.01278414f, 0.00959667f, 0.03079006f, 0.02597985f, -0.01156780f, -0.05531918f, -0.05792320f, 0.01289017f, 0.14216336f, 0.26822991f, 0.32053397f, 0.26822991f, 0.14216336f, 0.01289017f, -0.05792320f, -0.05531918f, -0.01156780f, 0.02597985f, 0.03079006f, 0.00959667f, -0.01278414f, -0.01811480f, -0.00728185f, 0.00603915f, 0.01031472f, 0.00497077f, -0.00252456f, -0.00540756f, -0.00299243f, 0.00085417f, 0.00254494f, 0.00160153f, -0.00020399f, -0.00118474f, -0.00093804f, -0.00000000f};

// ===== FIR: 순환 버퍼 =====
float fir_buf[FIR_N];
int   fir_idx = 0;

float fir_step(float x) {
  fir_buf[fir_idx] = x;                    // 새 샘플을 현재 자리에 쓴다
  float acc = 0;
  int k = fir_idx;                         // 최신 샘플부터
  for (int i = 0; i < FIR_N; i++) {
    acc += FIR_H[i] * fir_buf[k];          // 계수 × 버퍼 값
    k = (k == 0) ? FIR_N - 1 : k - 1;      // 한 칸 과거로 (0이면 끝으로 돌아간다)
  }
  fir_idx = (fir_idx + 1) % FIR_N;         // 다음 쓸 자리로
  return acc;
}

// ===== 노이즈 주입: 크기를 아는 사인파를 입력에 더한다 =====
float inj_phase = 0;
float inject() {
  if (INJECT_HZ <= 0) return 0;
  float v = INJECT_AMP * sinf(inj_phase);
  inj_phase += 2.0f * PI * INJECT_HZ / FS;
  if (inj_phase > 2.0f * PI) inj_phase -= 2.0f * PI;
  return v;
}

void setup() { Serial.begin(115200); }

void loop() {
  static unsigned long next = micros();
  static bool first = true;
  static int base = 0;
  if ((long)(micros() - next) >= 0) {
    next += 4000;                                   // 4ms = 250Hz
    int raw = analogRead(ADC_PIN);
    if (first) { base = START_RESET ? raw : 0; first = false; }
    float x = (float)(raw - base) + inject();       // 입력(+주입)
    float y = fir_step(x);                          // FIR
    Serial.print(x, 1); Serial.print(","); Serial.println(y, 2);
  }
}
