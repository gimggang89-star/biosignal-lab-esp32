// ============================================================
//  5주차 디지털필터(시간영역) 실습
//  Step 2 — Moving Average 필터 (교재 슬라이드 12)
// ------------------------------------------------------------
//  규칙 : y[n] = (x[n] + x[n-1] + ... + x[n-N+1]) / N   — 최근 N개 값의 평균
//  구현 : 순환 버퍼(배열 N칸) — 새 값이 오면 가장 오래된 칸을 덮어쓰고
//         인덱스를 0~N-1로 순환
//  출력 : "Raw,MA"  (한 줄에 두 값, 쉼표 구분)  → python/plot_step2_ma.py
//
//  직접 해보기 (슬라이드 15) : MA_N 을 4 · 8 · 16 · 32 로 바꿔 재업로드하고
//     ① R 봉우리 높이(Raw 대비)  ② 잔떨림 크기  ③ 지연 체감  을 기록
//     이론값: N=8 → 지연 14ms · 잔떨림 약 0.35배 / N=32 → 지연 62ms · 약 0.18배
// ============================================================

const int ADC_PIN = 34;   // GPIO34 (ADC1)
const int MA_N    = 8;    // 창 크기 ← 15번에서 이 숫자를 직접 바꿔본다

int  ma_buf[MA_N];        // 최근 N개 순환 버퍼
int  ma_idx   = 0;
bool ma_ready = false;    // 첫 샘플로 채웠는가

int moving_average(int x) {
  if (!ma_ready) {                       // 처음 한 번만
    for (int i = 0; i < MA_N; i++)       // 시작할 때 서서히 올라오는
      ma_buf[i] = x;                     // 가짜 출력을 막는다
    ma_ready = true;
  }
  ma_buf[ma_idx] = x;                    // 오래된 값 덮어씀
  ma_idx = (ma_idx + 1) % MA_N;          // 0~N-1 순환
  int sum = 0;
  for (int i = 0; i < MA_N; i++)
    sum += ma_buf[i];
  return sum / MA_N;                     // 정수 나눗셈
}

void setup() {
  Serial.begin(115200);
}

void loop() {
  static unsigned long next = micros();
  if ((long)(micros() - next) >= 0) {
    next += 4000;                        // 4ms = 250Hz (delay(4)보다 정확)
    int raw = analogRead(ADC_PIN);
    int ma  = moving_average(raw);
    Serial.print(raw);
    Serial.print(",");
    Serial.println(ma);
  }
}
