#define SAMPLE_RATE 500
#define BAUD        250000
const int ADC_PIN = 34;

// 74.5~149.5Hz Band-Pass (4차 Butterworth, 2차 섹션 4개 — 500Hz 기준 계수)
float EMGFilter(float input){
  float output = input;
  { static float z1, z2; float x = output - 0.05159732f*z1 - 0.36347401f*z2; output = 0.01856301f*x + 0.03712602f*z1 + 0.01856301f*z2; z2=z1; z1=x; }
  { static float z1, z2; float x = output - (-0.53945795f)*z1 - 0.39764934f*z2; output = 1.0f*x + (-2.0f)*z1 + 1.0f*z2; z2=z1; z1=x; }
  { static float z1, z2; float x = output - 0.47319594f*z1 - 0.70744137f*z2; output = 1.0f*x + 2.0f*z1 + 1.0f*z2; z2=z1; z1=x; }
  { static float z1, z2; float x = output - (-1.00211112f)*z1 - 0.74520226f*z2; output = 1.0f*x + (-2.0f)*z1 + 1.0f*z2; z2=z1; z1=x; }
  return output;
}

// 엔벨로프(활성도): |밴드패스 신호|를 최근 128개 이동합으로 평활
#define ENV_BUF 128
int  circ[ENV_BUF];
int  envIdx = 0;
long envSum = 0;
int getEnvelope(int absEmg){
  envSum -= circ[envIdx];
  envSum += absEmg;
  circ[envIdx] = absEmg;
  envIdx = (envIdx + 1) % ENV_BUF;
  return (int)((envSum / ENV_BUF) * 2);
}

void setup(){
  Serial.begin(BAUD);
  analogReadResolution(12);       // ESP32 12비트 (0~4095)
}

void loop(){
  // micros() 기반 정확한 500Hz 타이밍
  static unsigned long past = 0;
  unsigned long present = micros();
  unsigned long interval = present - past;
  past = present;
  static long timer = 0;
  timer -= interval;
  if (timer < 0){
    timer += 1000000 / SAMPLE_RATE;    // = 2000us (500Hz)
    int raw = analogRead(ADC_PIN);
    float sig = EMGFilter((float)raw);         // 밴드패스
    int env = getEnvelope(abs((int)sig));      // 정류 + 평활 = 활성도
    Serial.print("Raw:");  Serial.print(raw);
    Serial.print(",ENV:"); Serial.println(env);
  }
}
