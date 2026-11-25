import assert from 'node:assert/strict';
import test from 'node:test';

import { kstMonthDay, toUsageView, USAGE_UNKNOWN } from '../src/ui/screens/my/usageView.ts';

/* GET /me/usage → 화면 사용량 (renews_at = 다음 주기 시작, 한국 시간 0시). 화면 문구는 모두 '갱신되는 날' */

test("갱신일 'MM.DD' 와 채워지는 날 'M월 D일' 이 같은 날 (renews_at 의 한국 날짜)", () => {
  const v = toUsageView({ usage_percent: 62, renews_at: '2026-12-20T00:00:00+09:00', paused: false });
  assert.deepEqual(v, { usage_pct: 62, usage_renew: '12.20', usage_refill: '12월 20일', paused: false, ai_count: 0, auto_off: 0, credits_used: null, credits_left: null });
});

test('켜진 AI 메모 수 (2026-11-24 선택 창 N)', () => {
  assert.equal(toUsageView({ usage_percent: 100, renews_at: '2026-12-20T00:00:00+09:00', paused: true, ai_memo_count: 5 }).ai_count, 5);
  assert.equal(toUsageView({ usage_percent: 100, renews_at: 'x', paused: true, ai_memo_count: 3 }).ai_count, 3);
  assert.equal(toUsageView({ usage_percent: 0, renews_at: '2026-12-20', paused: false, auto_off_count: 4 }).auto_off, 4);
  const c = toUsageView({ usage_percent: 30, renews_at: '2026-12-20', paused: false, used: 24, balance: 56 });
  assert.deepEqual([c.credits_used, c.credits_left], [24, 56]);
});

test('Z(UTC)로 와도 한국 날짜로: 12/19 15:00Z = 12/20 0시 KST', () => {
  assert.deepEqual(kstMonthDay('2026-12-19T15:00:00Z'), [12, 20]);
  const v = toUsageView({ usage_percent: 0, renews_at: '2026-12-19T15:00:00Z', paused: false });
  assert.equal(v.usage_renew, '12.20');
  assert.equal(v.usage_refill, '12월 20일');
});

test('Z 경계: 14:59Z 는 아직 한국 전날 23:59', () => {
  assert.deepEqual(kstMonthDay('2026-12-19T14:59:00Z'), [12, 19]);
});

test('해 넘김 · 1월 1일 · 날짜만 있는 값', () => {
  assert.equal(toUsageView({ usage_percent: 0, renews_at: '2027-01-01T00:00:00+09:00', paused: false }).usage_renew, '01.01');
  assert.equal(toUsageView({ usage_percent: 0, renews_at: '2026-12-31T15:00:00Z', paused: false }).usage_refill, '1월 1일');
  assert.deepEqual(kstMonthDay('2026-03-01'), [3, 1]);
});

test('다 쓴 상태 · 범위 밖 값', () => {
  assert.equal(toUsageView({ usage_percent: 100, renews_at: '2026-12-20T00:00:00+09:00', paused: true }).paused, true);
  assert.equal(toUsageView({ usage_percent: 140, renews_at: '2026-12-20T00:00:00+09:00', paused: true }).usage_pct, 100);
  assert.equal(toUsageView({ usage_percent: Number.NaN, renews_at: '2026-12-20', paused: false }).usage_pct, 0);
});

test('날짜를 못 읽으면 — 로 (숫자를 지어내지 않음)', () => {
  const v = toUsageView({ usage_percent: 5, renews_at: 'bad', paused: false });
  assert.deepEqual(v, { ...USAGE_UNKNOWN, usage_pct: 5 });
  assert.deepEqual(USAGE_UNKNOWN, { usage_pct: 0, usage_renew: '—', usage_refill: '—', paused: false, ai_count: 0, auto_off: 0, credits_used: null, credits_left: null });
});
