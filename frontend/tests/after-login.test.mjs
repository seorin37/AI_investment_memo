import assert from 'node:assert/strict';
import test from 'node:test';

import { routeAfterLogin } from '../src/lib/afterLogin.ts';

/* 로그인 뒤 신규 판별 (임시 기준: 내 종목 0개 = 신규) */

test('내 종목 0개면 약관으로', async () => {
  assert.equal(await routeAfterLogin(async () => []), '/terms');
});

test('내 종목 1개 이상이면 홈으로', async () => {
  assert.equal(await routeAfterLogin(async () => [{ code: '005930' }]), '/');
  assert.equal(await routeAfterLogin(async () => [{ code: '005930' }, { code: '000660' }]), '/');
});

test('조회 실패면 홈으로 (안내가 잘못 뜨지 않게)', async () => {
  assert.equal(await routeAfterLogin(async () => { throw new Error('401'); }), '/');
});
