import assert from 'node:assert/strict';
import test from 'node:test';

import { planKey, planName, withCurrentPlan } from '../src/ui/screens/my/planLabel.ts';

/* 요금제 표시 (users.plan → 화면 문구 · mockPlans key · '현재 플랜' 태그) */

test('planName: free·plus·pro, 모르는 값·없음은 무료', () => {
  assert.equal(planName('free'), '무료 플랜');
  assert.equal(planName('plus'), 'PLUS 플랜');
  assert.equal(planName('pro'), 'PRO 플랜');
  assert.equal(planName(undefined), '무료 플랜');
  assert.equal(planName(null), '무료 플랜');
  assert.equal(planName('enterprise'), '무료 플랜');
});

test('planKey: mockPlans key 와 같은 값', () => {
  assert.equal(planKey('free'), '무료');
  assert.equal(planKey('plus'), 'PLUS');
  assert.equal(planKey('pro'), 'PRO');
  assert.equal(planKey(undefined), '무료');
});

const plans = [
  { key: '무료', tag: '현재 플랜' },
  { key: 'PLUS', tag: '추천' },
  { key: 'PRO', tag: '' },
];

test("withCurrentPlan: 무료면 그대로 ('추천' 유지)", () => {
  assert.deepEqual(withCurrentPlan(plans, '무료').map((p) => p.tag), ['현재 플랜', '추천', '']);
});

test("withCurrentPlan: PRO 면 '현재 플랜'이 PRO 로 옮겨 가고 무료 태그는 지움", () => {
  assert.deepEqual(withCurrentPlan(plans, 'PRO').map((p) => p.tag), ['', '추천', '현재 플랜']);
});

test("withCurrentPlan: PLUS 면 '추천' 대신 '현재 플랜'", () => {
  assert.deepEqual(withCurrentPlan(plans, 'PLUS').map((p) => p.tag), ['', '현재 플랜', '']);
});

test('withCurrentPlan: 원래 목록은 바꾸지 않음', () => {
  withCurrentPlan(plans, 'PRO');
  assert.deepEqual(plans.map((p) => p.tag), ['현재 플랜', '추천', '']);
});
