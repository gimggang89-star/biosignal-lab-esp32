// emg_core.h — EMG 처리 체인 (표본 1개씩, 1 ms 마다 부른다)
// ADC → DC 추정 제거 → HPF 20 Hz → 노치 60 Hz → 정류 → 이동 MAV · 이동 RMS (100 표본 = 100 ms)
//     → 기저선 학습 (0.5~3.0 초, 힘을 뺀다) → 임계 + 히스테리시스 + 최소 지속 → 상태 (0 보정 · 1 이완 · 2 수축)
// 빈칸 ① ② ③ 세 곳을 채운다 (정답본에는 채워져 있다)
#pragma once
#include <math.h>
#include <string.h>

#define FS_HZ       1000        // 표본화 주파수 (Hz)
#define RMS_N       100         // 이동 창 길이 (표본) = 100 ms
#define DC_ALPHA    0.001f      // DC 추정 속도 (시정수 약 1 초)
#define SETTLE_N    500         // 0~0.5 초: 필터 안정화 (학습에 안 씀)
#define LEARN_N     3000        // 0.5~3.0 초: 기저선 학습 (이 동안 힘을 뺀다)
#define K_ON        5.0f        // ON 임계  = mu + K_ON  * sd
#define K_OFF       3.0f        // OFF 임계 = mu + K_OFF * sd
#define SD_FLOOR    0.20f       // sd 하한 = 0.2 * mu (기저선이 너무 고르면 임계가 잡음에 붙는 것을 막는다)
#define MIN_ON_MS   50          // 임계를 연속 50 ms 넘어야 ON
#define MIN_OFF_MS  100         // 연속 100 ms 아래여야 OFF
#define ST_CAL 0                // 상태: 0 보정 중
#define ST_OFF 1                //       1 이완
#define ST_ON  2                //       2 수축

// 2차 IIR (biquad, Direct Form II transposed)
struct Biquad { float b0, b1, b2, a1, a2, z1, z2; };
static inline float biquad(Biquad *f, float x) {
  float y = f->b0 * x + f->z1;
  f->z1 = f->b1 * x - f->a1 * y + f->z2;
  f->z2 = f->b2 * x - f->a2 * y;
  return y;
}
// 계수 (fs = 1000 Hz, scipy.signal.butter(2, 20, 'highpass') · iirnotch(60, 30))
static const float HPF_B[3]   = {0.91496914f, -1.82993829f, 0.91496914f};
static const float HPF_A[3]   = {1.00000000f, -1.82269493f, 0.83718165f};
static const float NOTCH_B[3] = {0.99375596f, -1.84794186f, 0.99375596f};
static const float NOTCH_A[3] = {1.00000000f, -1.84794186f, 0.98751193f};

struct EmgCh {
  float dc; int dc_ok;                 // DC(바이어스) 추정
  Biquad hpf, notch;
  float filt;                          // 필터 후 값 y
  float ab[RMS_N], sq[RMS_N];          // 순환 버퍼: |y|, y*y
  float sumabs, sumsq;                 // 버퍼 합
  int idx;                             // 다음에 쓸 자리
  float mav, rms;                      // 이동 평균 절댓값, 이동 RMS
  long learn_from, learn_to;           // 기저선 학습 구간 (표본 번호)
  double s1, s2, sm; long ln;          // 학습 누적: rms 합, rms^2 합, mav 합, 개수
  float mu, sd, thr_on, thr_off, mav_mu;
  int learned;
  int on, cnt;                         // 현재 ON 여부, 상태를 바꾸려고 연속으로 센 표본 수
};

static void bq_set(Biquad *f, const float *b, const float *a) {
  f->b0 = b[0]; f->b1 = b[1]; f->b2 = b[2]; f->a1 = a[1]; f->a2 = a[2]; f->z1 = 0; f->z2 = 0;
}
static void emg_init(EmgCh *c) {
  memset(c, 0, sizeof(EmgCh));
  bq_set(&c->hpf, HPF_B, HPF_A);
  bq_set(&c->notch, NOTCH_B, NOTCH_A);
  c->learn_from = SETTLE_N; c->learn_to = LEARN_N;
}

// 기저선만 다시 학습 (c 명령): 지금부터 2.5 초 동안 힘을 뺀다
static void emg_recal(EmgCh *c, long n) {
  c->learn_from = n; c->learn_to = n + (LEARN_N - SETTLE_N);
  c->s1 = c->s2 = c->sm = 0; c->ln = 0; c->learned = 0; c->on = 0; c->cnt = 0;
}

// 표본 1개 처리. raw: ADC 값(0~4095), n: 시작 후 표본 번호
// 반환: 상태 0/1/2.  *ev: 1 = 기저선 학습 끝(#B), 2 = 수축 시작, 3 = 수축 끝 (없으면 0)
static int emg_step(EmgCh *c, int raw, long n, int *ev) {
  *ev = 0;
  // 1) DC 빼기: 첫 표본으로 시작해서 천천히 따라간다 (바이어스가 2048 이 아니어도 된다)
  if (!c->dc_ok) { c->dc = (float)raw; c->dc_ok = 1; }
  c->dc += ((float)raw - c->dc) * DC_ALPHA;
  float x = (float)raw - c->dc;
  // 2) HPF 20 Hz → 노치 60 Hz
  float y = biquad(&c->notch, biquad(&c->hpf, x));
  c->filt = y;

  // 3) 정류 [빈칸 ①]
  float rect = fabsf(y);

  // 4) 포락선: 순환 버퍼 이동 평균 [빈칸 ②: 제곱 합 갱신 3줄]
  c->sumsq -= c->sq[c->idx];
  c->sumsq += y * y;
  c->sq[c->idx] = y * y;
  c->sumabs += rect - c->ab[c->idx];
  c->ab[c->idx] = rect;                // MAV 는 완성됨
  if (++c->idx >= RMS_N) {
    c->idx = 0;
    // (반올림 오차가 쌓이지 않게 100 표본마다 버퍼를 다시 더한다 — 빈칸과 무관)
    double a = 0, s = 0;
    for (int i = 0; i < RMS_N; i++) { a += c->ab[i]; s += c->sq[i]; }
    c->sumabs = (float)a; c->sumsq = (float)s;
  }
  c->mav = c->sumabs / RMS_N;
  c->rms = sqrtf(fmaxf(c->sumsq, 0.0f) / RMS_N);

  // 5) 기저선 학습: learn_from ~ learn_to 동안 이완 상태의 rms 평균 mu, 표준편차 sd
  if (!c->learned) {
    if (n >= c->learn_from) { c->s1 += c->rms; c->s2 += (double)c->rms * c->rms; c->sm += c->mav; c->ln++; }
    if (n + 1 >= c->learn_to && c->ln > 0) {
      double m = c->s1 / c->ln, v = c->s2 / c->ln - m * m;
      c->mu = (float)m; c->sd = (float)sqrt(v > 0 ? v : 0); c->mav_mu = (float)(c->sm / c->ln);
      if (c->sd < SD_FLOOR * c->mu) c->sd = SD_FLOOR * c->mu;
      c->thr_on = c->mu + K_ON * c->sd; c->thr_off = c->mu + K_OFF * c->sd;
      c->learned = 1; c->on = 0; c->cnt = 0; *ev = 1;
    }
    return ST_CAL;
  }

  // 6) 임계 + 히스테리시스 [빈칸 ③]
  int above = c->on ? (c->rms > c->thr_off) : (c->rms > c->thr_on);
  if (above != c->on) {
    if (++c->cnt >= (c->on ? MIN_OFF_MS : MIN_ON_MS)) {
      c->on = above; c->cnt = 0; *ev = above ? 2 : 3;
    }
  } else c->cnt = 0;
  return c->on ? ST_ON : ST_OFF;
}
