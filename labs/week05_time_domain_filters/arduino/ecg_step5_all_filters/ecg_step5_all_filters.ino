// ============================================================
//  5주차 디지털필터(시간영역) 실습
//  Step 5 — 4단 종합 코드 (교재 슬라이드 29~30)
// ------------------------------------------------------------
//  Step 2·3·4 코드를 하나로 합친 최종본
//  moving_average()·median_filter()는 Step 2·3과 완전히 동일
//  IIR은 α = 0.7 하나만 적용
//
//  출력 : "Raw,MA,Median,IIR"  (네 값이 한 줄에)  → python/plot_step5_all.py
//
//  60Hz 관찰 (슬라이드 31, 질문 1 확인) :
//     노트북을 배터리로 두고 측정 → 충전기를 연결한 채 측정
//     → Raw 그래프의 고주파 잔떨림이 충전기 연결 시 더 두꺼워지는지 확인
//     → 같은 구간에서 MA·Median·IIR 그래프가 그 잔떨림을 얼마나 눌러 주는지 비교
//
//  세 필터 종합 한 줄 :
//     튀는 값 → Median · 전체 잔떨림 → Moving Average · 지속적인 빠른 떨림 → Simple IIR
//     그러나 60Hz와 기저선 변동은 셋 다 못 잡는다 → 6주차 High-pass · Notch · FIR
// ============================================================

const int   ADC_PIN   = 34;   // GPIO34 (ADC1)
const int   MA_N      = 8;
const int   MED_N     = 5;
const float ALPHA_A07 = 0.7f;

int   ma_buf[MA_N];
int   ma_idx   = 0;
bool  ma_ready = false;

int   med_buf[MED_N];
bool  med_ready = false;

float iir_y_a07 = 0;
bool  iir_ready = false;

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

int median_filter(int x) {
  if (!med_ready) {
    for (int i = 0; i < MED_N; i++) med_buf[i] = x;
    med_ready = true;
  }
  for (int i = 0; i < MED_N - 1; i++)
    med_buf[i] = med_buf[i + 1];
  med_buf[MED_N - 1] = x;
  int s[MED_N];
  for (int i = 0; i < MED_N; i++) s[i] = med_buf[i];
  for (int i = 0; i < MED_N; i++)
    for (int j = i + 1; j < MED_N; j++)
      if (s[i] > s[j]) {
        int t = s[i]; s[i] = s[j]; s[j] = t;
      }
  return s[MED_N / 2];
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
    if (!iir_ready) {
      iir_y_a07 = raw;
      iir_ready = true;
    }
    iir_y_a07 = ALPHA_A07 * iir_y_a07
              + (1.0f - ALPHA_A07) * raw;

    Serial.print(raw); Serial.print(",");
    Serial.print(ma);  Serial.print(",");
    Serial.print(med); Serial.print(",");
    Serial.println((int)iir_y_a07);
  }
}
