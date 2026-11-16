// emg_chain.ino — EMG 측정 (BioAmp EXG Pill + ESP32 Dev Module) : 1000 Hz, 115200 baud
// 배선: OUT → GPIO34, VCC → 3.3 V, GND → GND, IN+ · IN- · REF → 전극 3개
//       (실험 6 2채널: 두 번째 보드 OUT → GPIO39(VN), 아래 NCH 를 2 로)
// 같은 폴더의 emg_core.h (처리 체인, 빈칸 ①②③) 를 쓴다. 폴더 이름 = emg_chain
//
// 출력 모드 — 시리얼로 글자 하나를 보내 바꾼다 (바꾸면 처음부터 다시: 기저선 학습도 다시)
//   R  원신호  x                                   1 ms 마다  (시리얼 플로터에서 1 kHz 원신호)
//   F  필터 후 filt                                1 ms 마다  (HPF 20 Hz + 노치 60 Hz 후, 정수 count)
//   P  요약    filt:..,rms:..,thr_on:..,state:..   10 ms 마다 (플로터에서 포락선 · 판정)  ← 컴파일 기본값
//   B  바이너리 (파이썬 viz.py 전용, 표본마다 5 바이트. 터미널에 찍으면 깨져 보인다)
//   c  기저선만 다시 학습 (힘을 뺀 채로 2.5 초)
//   s  상태 한 줄  #S,n,overrun,sat mode=P mav=.. rms=.. thr_on=.. state=..  (시리얼 모니터, 줄 바꿈 없음)
//   2채널이면 R · F 는 한 표본 걸러 "x1,x2", P 는 20 ms 마다
//   #START · #B · #E · #W · #S 진단 줄은 B 모드에서만 나간다 (플로터 그래프가 끊기지 않게)
#include "emg_core.h"

#define OUT_MODE  'P'         // R F P B
#define NCH       2           // 2 = 2채널 (실험 6: 이두 GPIO36 · 삼두 GPIO39). 1채널은 1
#define BAUD      115200      // 모든 모드 공통
#define SAMPLE_US 1000UL      // 1 ms = 1000 Hz

const int ADC_PIN1 = 34;      // GPIO34: 채널 1 (이두)  — 수업 PPT처럼 VP에 꽂았다면 36
const int ADC_PIN2 = 39;      // VN: 채널 2 (삼두, NCH 2 일 때만)
const int LED_PIN  = 2;       // 내장 LED: 채널 1 이 수축(ON)이면 켜진다
const int P_ST_SCALE = 30;    // P 모드에서 state 에 곱하는 값 (rms 와 같은 그래프에 보이게. rms 가 수백이면 100)
const int SAT_LO = 30, SAT_HI = 4065;       // 이 밖이면 ADC 포화
const int BIAS_LO = 1000, BIAS_HI = 3100;   // 기저선 학습이 끝날 때 DC 가 이 밖이면 바이어스 경고
const int FBITS = (NCH == 1) ? 4 : 0;       // B 모드 filt 소수 비트 (1채널 1/16 count, 2채널 정수)

EmgCh ch[NCH];
char  mode = OUT_MODE;
long  n = 0;                  // 시작 후 표본 번호
unsigned long next_us = 0;
unsigned long overrun = 0;    // 1 ms 간격을 놓친 횟수
unsigned long sat_total = 0;  // 포화 표본 수 합계
int   sat_blk[NCH];           // 100 표본 블록 안의 포화 수
long  last_sat_warn = -100000;
int   st[NCH];
float pk[NCH];                // P 모드: 구간 안에서 절댓값이 가장 큰 filt (부호 유지)
int   pcount = 0;

void restart(char m) {        // 모드를 바꾸고 처음부터 다시 시작
  mode = m; n = 0; overrun = 0; sat_total = 0; pcount = 0; last_sat_warn = -100000;
  for (int k = 0; k < NCH; k++) { emg_init(&ch[k]); sat_blk[k] = 0; st[k] = ST_CAL; pk[k] = 0; }
  if (mode == 'B') {
    Serial.printf("\n#START fs=%d baud=%d nch=%d mode=B fbits=%d rms_n=%d k_on=%.1f k_off=%.1f\n",
                  FS_HZ, BAUD, NCH, FBITS, RMS_N, K_ON, K_OFF);
  }
  next_us = micros() + SAMPLE_US;
}

void send_frame(const int *xr) {   // B 모드 프레임: 헤더 1 B + 7 bit 씩 데이터 (1채널 4 B, 2채널 7 B)
  uint64_t bits = 0; int nb = 0;
  for (int k = 0; k < NCH; k++) {
    long q = lroundf(ch[k].filt * (float)(1 << FBITS));
    long lim = 1L << (11 + FBITS);
    if (q > lim - 1) q = lim - 1;
    if (q < -lim) q = -lim;
    bits = (bits << 12) | (uint64_t)(xr[k] & 0xFFF);
    bits = (bits << (12 + FBITS)) | (uint64_t)(q & ((1L << (12 + FBITS)) - 1));
    nb += 24 + FBITS;
  }
  int g = (nb + 6) / 7;
  bits <<= (g * 7 - nb);
  uint8_t buf[8];
  int st2 = (NCH > 1) ? st[NCH - 1] : 0;
  buf[0] = 0x80 | ((st[0] & 3) << 5) | ((st2 & 3) << 3) | (n & 7);
  for (int i = 0; i < g; i++) buf[1 + i] = (uint8_t)((bits >> (7 * (g - 1 - i))) & 0x7F);
  Serial.write(buf, 1 + g);
}

void status_line() {          // s 명령
  Serial.printf("#S,%ld,%lu,%lu mode=%c mav=%.1f rms=%.1f thr_on=%.1f state=%d",
                n, overrun, sat_total, mode, ch[0].mav, ch[0].rms, ch[0].thr_on, st[0]);
  if (NCH > 1) Serial.printf(" mav2=%.1f rms2=%.1f thr_on2=%.1f state2=%d", ch[NCH - 1].mav, ch[NCH - 1].rms, ch[NCH - 1].thr_on, st[NCH - 1]);
  Serial.print("\n");
}

void handle_cmd() {
  while (Serial.available() > 0) {
    int c = Serial.read();
    if (c == 'r' || c == 'R') restart('R');
    else if (c == 'f' || c == 'F') restart('F');
    else if (c == 'p' || c == 'P') restart('P');
    else if (c == 'b' || c == 'B') restart('B');
    else if (c == 'c' || c == 'C') {
      for (int k = 0; k < NCH; k++) emg_recal(&ch[k], n);
      if (mode == 'B') Serial.printf("#RECAL n=%ld\n", n);
    }
    else if (c == 's' || c == 'S') status_line();
  }
}

void sample() {
  int xr[NCH], ev[NCH] = {0};
  xr[0] = analogRead(ADC_PIN1);
  if (NCH > 1) xr[NCH - 1] = analogRead(ADC_PIN2);
  for (int k = 0; k < NCH; k++) {
    st[k] = emg_step(&ch[k], xr[k], n, &ev[k]);
    if (xr[k] <= SAT_LO || xr[k] >= SAT_HI) { sat_blk[k]++; sat_total++; }
  }
  digitalWrite(LED_PIN, st[0] == ST_ON ? HIGH : LOW);

  if (mode == 'R' || mode == 'F') {
    if (NCH == 1 || (n & 1) == 0) {               // 2채널은 한 표본 걸러 (회선 여유)
      for (int k = 0; k < NCH; k++) {
        if (k) Serial.print(',');
        Serial.print(mode == 'R' ? xr[k] : (int)lroundf(ch[k].filt));
      }
      Serial.print("\n");
    }
  } else if (mode == 'P') {
    for (int k = 0; k < NCH; k++) if (fabsf(ch[k].filt) > fabsf(pk[k])) pk[k] = ch[k].filt;
    if (++pcount >= 10 * NCH) {                   // 1채널 10 ms, 2채널 20 ms 마다
      for (int k = 0; k < NCH; k++) {
        if (NCH == 1) Serial.printf("filt:%d,rms:%.1f,thr_on:%.1f,state:%d", (int)lroundf(pk[k]), ch[k].rms, ch[k].thr_on, st[k] * P_ST_SCALE);
        else Serial.printf("%sfilt%d:%d,rms%d:%.1f,thr_on%d:%.1f,state%d:%d", k ? "," : "", k + 1, (int)lroundf(pk[k]), k + 1, ch[k].rms, k + 1, ch[k].thr_on, k + 1, st[k] * P_ST_SCALE);
        pk[k] = 0;
      }
      Serial.print("\n");
      pcount = 0;
    }
  } else if (mode == 'B') {
    send_frame(xr);
    for (int k = 0; k < NCH; k++) {
      if (ev[k] == 1) {                           // 기저선 학습 끝: 평균 · 표준편차 · 임계 · MAV 평균
        Serial.printf("#B,%ld,%.2f,%.2f,%.2f,%.2f,%.2f,%d\n", n, ch[k].mu, ch[k].sd, ch[k].thr_on, ch[k].thr_off, ch[k].mav_mu, k + 1);
        if (ch[k].dc < BIAS_LO || ch[k].dc > BIAS_HI) Serial.printf("#W,%ld,BIAS,%.0f,%d\n", n, ch[k].dc, k + 1);
      } else if (ev[k] == 2 || ev[k] == 3) {
        Serial.printf("#E,%ld,%d,%d\n", n, ev[k] == 2 ? 1 : 0, k + 1);
      }
    }
  }

  if (n % 100 == 99) {                            // 최근 100 ms 중 5 표본 이상 포화면 경고 (1 초에 한 번)
    for (int k = 0; k < NCH; k++) {
      if (sat_blk[k] >= 5 && mode == 'B' && n - last_sat_warn >= 1000) {
        Serial.printf("#W,%ld,SAT,%d,%d\n", n, sat_blk[k], k + 1);
        last_sat_warn = n;
      }
      sat_blk[k] = 0;
    }
  }
  if (mode == 'B' && n > 0 && n % 10000 == 0) Serial.printf("#S,%ld,%lu,%lu\n", n, overrun, sat_total);
  n++;
}

void setup() {
  Serial.setTxBufferSize(4096);   // begin 보다 먼저 (PC 가 잠깐 멈춰도 약 0.8 초분을 받아 둔다)
  Serial.begin(BAUD);
  analogReadResolution(12);       // 0~4095
  analogSetAttenuation(ADC_11db); // 입력 약 0.15~2.45 V 권장
  pinMode(LED_PIN, OUTPUT);
  restart(mode);
}

void loop() {
  handle_cmd();
  unsigned long now = micros();
  long late = (long)(now - next_us);
  if (late < 0) return;
  if (late > (long)SAMPLE_US) { overrun++; next_us = now; }   // 1 표본 넘게 늦었다 → 시각을 다시 맞춘다
  next_us += SAMPLE_US;
  sample();
}
