/*
 * ESP32 (ESP-WROOM-32) + BioAmp EXG Pill — 뇌파(EEG) 측정
 * ---------------------------------------------------------
 * 배선 : BioAmp VCC->3V3 / GND->GND / OUT->GPIO34  (VCC/GND 반대로 X)
 * 전극 (알파파 '눈 감기' 실험 기준):
 *   - IN+  : 이마 왼쪽(눈썹 위 3~4cm)      ┐ 두 측정 전극은
 *   - IN-  : 이마 오른쪽(눈썹 위 3~4cm)     ┘ 3~4cm 떨어뜨려 부착
 *   - REF  : 귓불 또는 귀 뒤 뼈(유양돌기) — 털·근육 없는 곳
 *   ※ 알파파를 더 강하게 보려면 뒤통수(후두엽 O1/O2, 머리카락 가르고)가 좋지만,
 *     학생 실습은 이마가 붙이기 쉽고 안정적입니다.
 * 보드 : Tools -> Board -> "ESP32 Dev Module"
 *
 * ★ EEG는 생체신호 중 가장 약합니다(µV급):
 *   - 샘플레이트 256Hz   (뇌파 대역 0.5~30Hz를 넉넉히 담기 위함)
 *   - 통신속도 115200    (ECG·EOG와 동일 / EMG의 250000 아님)
 *   - 필터 = 0.5~29.5Hz 밴드패스 (DC·드리프트 + 고주파 + 60Hz 함께 제거)
 * 필터는 Upside Down Labs 공식 EEGFilter(256Hz 기준 4차 밴드패스) 그대로.
 *
 * ▶ 측정 팁: 몸에 힘 빼고 가만히, 이악물기·눈깜빡임 최소화(근전도가 섞임).
 *   눈을 '감으면' 몇 초 뒤 8~13Hz 알파파가 커지고, '뜨면' 사라집니다(Berger 효과).
 * ---------------------------------------------------------
 */
#define SAMPLE_RATE 256
#define BAUD        115200
const int ADC_PIN = 34;

// 0.5~29.5Hz Band-Pass (4차 Butterworth, 2차 섹션 4개 — 256Hz 기준 공식 계수)
float EEGFilter(float input){
  float output = input;
  { static float z1, z2; float x = output - (-0.95391350f)*z1 - (0.25311356f)*z2; output = 0.00735282f*x + 0.01470564f*z1 + 0.00735282f*z2; z2=z1; z1=x; }
  { static float z1, z2; float x = output - (-1.20596630f)*z1 - (0.60558332f)*z2; output = 1.00000000f*x + 2.00000000f*z1 + 1.00000000f*z2; z2=z1; z1=x; }
  { static float z1, z2; float x = output - (-1.97690645f)*z1 - (0.97706395f)*z2; output = 1.00000000f*x + (-2.00000000f)*z1 + 1.00000000f*z2; z2=z1; z1=x; }
  { static float z1, z2; float x = output - (-1.99071687f)*z1 - (0.99086813f)*z2; output = 1.00000000f*x + (-2.00000000f)*z1 + 1.00000000f*z2; z2=z1; z1=x; }
  return output;
}

void setup(){
  Serial.begin(BAUD);
  analogReadResolution(12);       // ESP32 12비트 (0~4095)
}

void loop(){
  // micros() 기반 정확한 256Hz 타이밍
  static unsigned long past = 0;
  unsigned long present = micros();
  unsigned long interval = present - past;
  past = present;
  static long timer = 0;
  timer -= interval;
  if (timer < 0){
    timer += 1000000 / SAMPLE_RATE;   // = 3906us (256Hz)
    int raw = analogRead(ADC_PIN);
    int eeg = (int)EEGFilter((float)raw);   // 밴드패스 → 정제된 EEG(0 중심)
    Serial.print("Raw:");  Serial.print(raw);
    Serial.print(",EEG:"); Serial.println(eeg + 2048);  // 화면 중앙(2048) 기준으로 표시
  }
}
