import assert from 'node:assert/strict';
import test from 'node:test';

import { toUsageView, USAGE_UNKNOWN } from '../src/ui/screens/my/usageView.ts';

/* GET /me/usage → 화면 사용량 (renews_at = 다음 주기 시작, 한국 시간 0시) */

test('갱신일 = 다음 주기 시작 하루 전 (MM.DD), 채워지는 날 = 다음 주기 시작 (M월 D일)', () => {
  const v = toUsageView({ usage_percent: 62, renews_at: '2026-12-20T00:00:00+09:00', paused: false });
  assert.deepEqual(v, { usage_pct: 62, usage_renew: '12.19', usage_refill: '12월 20일', paused: false });
});

test('달 · 해 넘김: 1/1 시작이면 12.31, 3/1 시작이면 2월 말일', () => {
  assert.equal(toUsageView({ usage_percent: 0, renews_at: '2027-01-01T00:00:00+09:00', paused: false }).usage_renew, '12.31');
  assert.equal(toUsageView({ usage_percent: 0, renews_at: '2026-03-01T00:00:00+09:00', paused: false }).usage_renew, '02.28');
  assert.equal(toUsageView({ usage_percent: 0, renews_at: '2028-03-01T00:00:00+09:00', paused: false }).usage_renew, '02.29');
});

test('기기 시간대와 무관 (서버 날짜 부분 그대로)', () => {
  // UTC 로 바꾸면 전날 15시지만 화면은 한국 날짜
  assert.equal(toUsageView({ usage_percent: 10, renews_at: '2026-12-01T00:00:00+09:00', paused: false }).usage_refill, '12월 1일');
});

test('다 쓴 상태 · 범위 밖 값', () => {
  assert.deepEqual(toUsageView({ usage_percent: 100, renews_at: '2026-12-20T00:00:00+09:00', paused: true }).paused, true);
  assert.equal(toUsageView({ usage_percent: 140, renews_at: '2026-12-20T00:00:00+09:00', paused: true }).usage_pct, 100);
  assert.equal(toUsageView({ usage_percent: Number.NaN, renews_at: '2026-12-20', paused: false }).usage_pct, 0);
});

test('날짜를 못 읽으면 — 로 (숫자를 지어내지 않음)', () => {
  const v = toUsageView({ usage_percent: 5, renews_at: 'bad', paused: false });
  assert.deepEqual(v, { ...USAGE_UNKNOWN, usage_pct: 5 });
  assert.deepEqual(USAGE_UNKNOWN, { usage_pct: 0, usage_renew: '—', usage_refill: '—', paused: false });
});
