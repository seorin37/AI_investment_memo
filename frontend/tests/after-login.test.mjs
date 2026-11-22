import assert from 'node:assert/strict';
import test from 'node:test';

import { routeAfterLogin, routeAfterTerms } from '../src/lib/afterLogin.ts';

/* 로그인 뒤 판별 = 필수 약관 동의 완료(GET /me/terms complete) · 약관 동의 뒤 갈 곳 */

test('로그인 뒤: 약관 미동의면 /terms', async () => {
  assert.equal(await routeAfterLogin(async () => ({ complete: false })), '/terms');
});

test('로그인 뒤: 동의했으면 종목 0개여도 / (건너뛰기 반복 없음)', async () => {
  assert.equal(await routeAfterLogin(async () => ({ complete: true })), '/');
});

test('로그인 뒤: 동의 + 종목 N개도 / (종목 수는 보지 않음)', async () => {
  let asked = false;
  const terms = async () => { asked = true; return { complete: true }; };
  assert.equal(await routeAfterLogin(terms), '/');
  assert.equal(asked, true);
});

test('로그인 뒤: 조회 실패면 / (안내가 잘못 뜨지 않게)', async () => {
  assert.equal(await routeAfterLogin(async () => { throw new Error('401'); }), '/');
});

const agreed = async () => ({ complete: true });

test('약관 뒤: 저장 성공 + 내 종목 0개면 /onboarding/pick', async () => {
  assert.deepEqual(await routeAfterTerms({ agree: agreed, listMyStocks: async () => [] }), { ok: true, next: '/onboarding/pick' });
});

test('약관 뒤: 저장 성공 + 내 종목 1개 이상이면 /', async () => {
  assert.deepEqual(await routeAfterTerms({ agree: agreed, listMyStocks: async () => [{ code: '005930' }] }), { ok: true, next: '/' });
  assert.deepEqual(await routeAfterTerms({ agree: agreed, listMyStocks: async () => [{ code: '005930' }, { code: '000660' }] }), { ok: true, next: '/' });
});

test('약관 뒤: 저장 실패면 이동 없음 (종목도 묻지 않음)', async () => {
  let listed = false;
  const r = await routeAfterTerms({ agree: async () => { throw new Error('422'); }, listMyStocks: async () => { listed = true; return []; } });
  assert.deepEqual(r, { ok: false });
  assert.equal(listed, false);
});

test('약관 뒤: 저장 응답이 complete false 면 실패로 봄', async () => {
  assert.deepEqual(await routeAfterTerms({ agree: async () => ({ complete: false }), listMyStocks: async () => [] }), { ok: false });
});

test('약관 뒤: 저장 성공 뒤 종목 조회가 실패하면 /', async () => {
  assert.deepEqual(await routeAfterTerms({ agree: agreed, listMyStocks: async () => { throw new Error('net'); } }), { ok: true, next: '/' });
});
