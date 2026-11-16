// 실험 3: 고주파 제거 (FIR) — 빈칸 ①② 를 채우시오
// 보드: ESP32 Dev Module / 시리얼 115200 / ADC 핀: GPIO34 / 샘플링 250Hz
#include <math.h>

const int   ADC_PIN = 34;                 // GPIO34 (ADC1)
const float FS      = 250.0f;             // 샘플링 250Hz

// ===== 바꿔 볼 값 =====
const float INJECT_HZ   = 0;              // 0: 주입 없음 / 0.3, 60, 80 등: 그 주파수의 사인파를 입력에 더한다
const float INJECT_AMP  = 100;            // 주입 사인파 크기 (ADC 숫자 단위)
const bool  START_RESET = true;           // true: 첫 샘플을 빼서 0 근처에서 시작 / false: 원값(약 2000) 그대로

// ===== FIR 계수 (python gen_coef.py fir 51 60 의 결과) =====
const int   FIR_N = 51;
const float FIR_H[FIR_N]={-0.00000000f, -0.00110809f, -0.00016400f, 0.00159773f, 0.00051658f, -0.00254332f, -0.00126358f, 0.00395284f, 0.00265040f, -0.00578664f, -0.00496760f, 0.00795827f, 0.00857586f, -0.01034054f, -0.01397639f, 0.01277600f, 0.02199686f, -0.01509110f, -0.03431804f, 0.01711240f, 0.05528399f, -0.01868333f, -0.10096122f, 0.01967941f, 0.31685595f, 0.48049510f, 0.31685595f, 0.01967941f, -0.10096122f, -0.01868333f, 0.05528399f, 0.01711240f, -0.03431804f, -0.01509110f, 0.02199686f, 0.01277600f, -0.01397639f, -0.01034054f, 0.00857586f, 0.00795827f, -0.00496760f, -0.00578664f, 0.00265040f, 0.00395284f, -0.00126358f, -0.00254332f, 0.00051658f, 0.00159773f, -0.00016400f, -0.00110809f, -0.00000000f};

// ===== FIR: 순환 버퍼 =====
float fir_buf[FIR_N];
int   fir_idx = 0;

float fir_step(float x) {
  fir_buf[fir_idx] = x;                    // 새 샘플을 현재 자리에 쓴다
  float acc = 0;
  int k = fir_idx;                         // 최신 샘플부터
  for (int i = 0; i < FIR_N; i++) {
    acc += ______①______;                  // 계수 × 버퍼 값
    k = ______②______;                         // 한 칸 과거로 (0이면 끝으로 돌아간다)
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
