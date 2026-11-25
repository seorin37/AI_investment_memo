import assert from 'node:assert/strict';
import test from 'node:test';

import { MOCK_PLAN_CATALOG, defaultPlanKey, toCreditPacks, toPlanCompare, toPlanInfos, toPlanNotes, won } from '../src/ui/screens/my/planView.ts';

/* 2026-11-25 확정안 ⑧: 무료 20 · 플러스 14,900원 80 · 프로 29,900원 160, 추가 50개 9,900원 */
test('플랜 카드: 가격 · 첫 달 · 추천', () => {
  const p = toPlanInfos(MOCK_PLAN_CATALOG);
  assert.deepEqual(p.map((x) => [x.key, x.price, x.tag, x.first]), [
    ['무료', '0원', '', undefined],
    ['PLUS', '14,900원', '추천', '첫 달 7,450원'],
    ['PRO', '29,900원', '', '첫 달 14,950원'],
  ]);
  assert.equal(p[1].features[0], '매달 80 크레딧');
  assert.equal(p[2].features[1], 'AI 추적 항목 최대 100개');
});

test('비교표 · 안내 · 충전 상품 · 처음 고를 카드', () => {
  const cmp = Object.fromEntries(toPlanCompare(MOCK_PLAN_CATALOG));
  assert.deepEqual(cmp['월 크레딧'], ['20', '80', '160']);
  assert.deepEqual(cmp['AI 추적 항목'], ['5개', '30개', '100개']);
  assert.deepEqual(cmp['첫 달 가격'], ['—', '7,450원', '14,950원']);
  assert.deepEqual(cmp['추가 크레딧 50개'], ['9,900원', '9,900원', '9,900원']);
  assert.match(toPlanNotes(MOCK_PLAN_CATALOG)[1], /주간보고서 3, AI 오디오 5, 투자 실험실 1/);
  assert.deepEqual(toCreditPacks(MOCK_PLAN_CATALOG), [{ credits: 50, label: '50 크레딧', price: '9,900원' }]);
  assert.equal(defaultPlanKey(MOCK_PLAN_CATALOG), 'PLUS');
  assert.equal(won(29900), '29,900원');
});
