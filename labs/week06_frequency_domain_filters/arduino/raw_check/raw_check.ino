// 준비: 내 원신호 점검 — 출력: raw (ADC 원값)
// 보드: ESP32 Dev Module / 시리얼 115200 / ADC 핀: GPIO34 / 샘플링 250Hz
const int ADC_PIN = 34;                    // GPIO34 (ADC1)

void setup() { Serial.begin(115200); }

void loop() {
  static unsigned long next = micros();
  if ((long)(micros() - next) >= 0) {
    next += 4000;                          // 4ms = 250Hz
    Serial.println(analogRead(ADC_PIN));   // 필터 없는 원값
  }
}
