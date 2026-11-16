// 실험 1: 기저선 제거 (HPF) — 빈칸 ①②③ 을 채우시오
// 보드: ESP32 Dev Module / 시리얼 115200 / ADC 핀: GPIO34 / 샘플링 250Hz
#include <math.h>

const int   ADC_PIN = 34;                 // GPIO34 (ADC1)
const float FS      = 250.0f;             // 샘플링 250Hz

// ===== 바꿔 볼 값 =====
const float INJECT_HZ   = 0;              // 0: 주입 없음 / 0.3, 60, 80 등: 그 주파수의 사인파를 입력에 더한다
const float INJECT_AMP  = 100;            // 주입 사인파 크기 (ADC 숫자 단위)
const bool  START_RESET = true;           // true: 첫 샘플을 빼서 0 근처에서 시작 / false: 원값(약 2000) 그대로

// ===== HPF 계수 (python gen_coef.py hpf 0.5 의 결과, 반올림 금지) =====
const float HPF_B[3]={0.99115360f, -1.98230719f, 0.99115360f};
const float HPF_A[3]={1.00000000f, -1.98222893f, 0.98238545f};

// ===== 2차 필터(Biquad) =====
// 이론 식: y = b0*x + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]
struct Biquad { float b0, b1, b2, a1, a2, xp1, xp2, yp1, yp2; };

float biquad_step(Biquad &f, float x) {
  float y = ______①______;        // b0·x + b1·x[n-1] + b2·x[n-2] − a1·y[n-1] − a2·y[n-2]
  f.xp2 = f.xp1;  f.xp1 = __②__;  // 입력 기억 갱신
  f.yp2 = f.yp1;  f.yp1 = __③__;  // 출력 기억 갱신
  return y;
}

Biquad hpf = { HPF_B[0], HPF_B[1], HPF_B[2], HPF_A[1], HPF_A[2], 0, 0, 0, 0 };

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
    float y = biquad_step(hpf, x);                  // HPF
    Serial.print(x, 1); Serial.print(","); Serial.println(y, 2);
  }
}
