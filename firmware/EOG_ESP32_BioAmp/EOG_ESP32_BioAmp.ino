
#define SAMPLE_RATE 75
#define BAUD        115200
const int ADC_PIN = 34;

// 0.5~19.5Hz Band-Pass (4차 Butterworth, 2차 섹션 4개 — 75Hz 기준 계수)
float EOGFilter(float input){
  float output = input;
  { static float z1, z2; float x = output - 0.02977423f*z1 - 0.04296318f*z2; output = 0.09797471f*x + 0.19594942f*z1 + 0.09797471f*z2; z2=z1; z1=x; }
  { static float z1, z2; float x = output - 0.08383952f*z1 - 0.46067709f*z2; output = 1.0f*x + 2.0f*z1 + 1.0f*z2; z2=z1; z1=x; }
  { static float z1, z2; float x = output - (-1.92167271f)*z1 - 0.92347975f*z2; output = 1.0f*x + (-2.0f)*z1 + 1.0f*z2; z2=z1; z1=x; }
  { static float z1, z2; float x = output - (-1.96758891f)*z1 - 0.96933514f*z2; output = 1.0f*x + (-2.0f)*z1 + 1.0f*z2; z2=z1; z1=x; }
  return output;
}

void setup(){
  Serial.begin(BAUD);
  analogReadResolution(12);       // ESP32 12비트 (0~4095)
}

void loop(){
  // micros() 기반 정확한 75Hz 타이밍
  static unsigned long past = 0;
  unsigned long present = micros();
  unsigned long interval = present - past;
  past = present;
  static long timer = 0;
  timer -= interval;
  if (timer < 0){
    timer += 1000000 / SAMPLE_RATE;   // = 13333us (75Hz)
    int raw = analogRead(ADC_PIN);
    int eog = (int)EOGFilter((float)raw);   // 밴드패스 → 정제된 EOG(0 중심)
    Serial.print("Raw:");  Serial.print(raw);
    Serial.print(",EOG:"); Serial.println(eog + 2048);  // 화면 중앙(2048) 기준으로 표시
  }
}
