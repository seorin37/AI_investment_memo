import assert from 'node:assert/strict';
import test from 'node:test';

import { refillLabel, toStudioHead } from '../src/ui/screens/studio/studioHead.ts';

/* 스튜디오 숫자 (GET /me/usage · /stocks 길이 · /ai/stats → 화면) */

const usage = (over = {}) => ({
  usage_percent: 38, used: 11, balance: 19, period_start: '2026-11-01',
  renews_at: '2026-11-30T15:00:00+00:00', renew_label: '11.30 갱신', paused: false, ...over,
});

test('사용량 · 다시 채워지는 날(한국 날짜) · 종목 수 · AI 연결 메모 수', () => {
  assert.deepEqual(toStudioHead(usage(), 4, { linked_memos: 7, updates_this_month: 3, linked_stocks: 2 }), {
    usage_pct: 38, usage_refill: '12월 1일', stock_count: 4, ai_memo_count: 7, spent: false,
  });
});

test('다 씀: 100% 이거나 paused', () => {
  assert.equal(toStudioHead(usage({ usage_percent: 100 }), 1, undefined).spent, true);
  assert.equal(toStudioHead(usage({ usage_percent: 40, paused: true }), 1, undefined).spent, true);
  assert.equal(toStudioHead(usage({ usage_percent: 130 }), 1, undefined).usage_pct, 100);
});

test('받는 중이면 0 · 빈 글자', () => {
  assert.deepEqual(toStudioHead(undefined, undefined, undefined), { usage_pct: 0, usage_refill: '', stock_count: 0, ai_memo_count: 0, spent: false });
});

test('갱신일은 한국 시간 기준', () => {
  assert.equal(refillLabel('2026-11-30T15:00:00Z'), '12월 1일');     // KST 12-01 00:00
  assert.equal(refillLabel('2026-12-31T15:00:00Z'), '1월 1일');
});
