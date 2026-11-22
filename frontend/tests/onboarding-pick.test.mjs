import assert from 'node:assert/strict';
import test from 'node:test';

import { addSelectedStocks, withSelectedStocks } from '../src/ui/screens/onboarding/pickSave.ts';

/* 온보딩 종목 고르기: 고른 종목 담기 결과 · 화면 목록 */

const pick = { '005930': 'watching', '000660': 'holding', '035420': 'watching' };

test('전부 성공: failed 비어 있음, 차례대로 하나씩 담음', async () => {
  const calls = [];
  const r = await addSelectedStocks(pick, async (code, status) => { calls.push(`${code}:${status}`); });
  assert.deepEqual(r.failed, {});
  assert.deepEqual(r.added, ['005930', '000660', '035420']);
  assert.deepEqual(calls, ['005930:watching', '000660:holding', '035420:watching']);
});

test('일부 실패: 실패한 종목만 (선택 상태 그대로) 남음, 나머지는 계속 담음', async () => {
  const r = await addSelectedStocks(pick, async (code) => {
    if (code === '000660') throw Object.assign(new Error('서버'), { status: 500 });
  });
  assert.deepEqual(r.failed, { '000660': 'holding' });
  assert.deepEqual(r.added, ['005930', '035420']);
});

test('이미 담긴 종목(409)은 성공으로 봄', async () => {
  const r = await addSelectedStocks(pick, async (code) => {
    if (code === '005930') throw Object.assign(new Error('이미 있음'), { status: 409 });
  });
  assert.deepEqual(r.failed, {});
  assert.equal(r.added.length, 3);
});

test('전부 실패: 고른 것 그대로 남음 (네트워크 오류 포함)', async () => {
  const r = await addSelectedStocks(pick, async () => { throw new TypeError('network'); });
  assert.deepEqual(r.failed, pick);
  assert.deepEqual(r.added, []);
});

test('아무것도 안 골랐으면 담지 않음', async () => {
  let called = false;
  const r = await addSelectedStocks({}, async () => { called = true; });
  assert.deepEqual(r, { failed: {}, added: [] });
  assert.equal(called, false);
});

const card = (code, name) => ({ stock_code: code, name, market: 'KOSPI', category: '', logo: name[0], logo_bg: '#000' });

test('화면 목록: 검색 결과에 없는 고른 종목도 뒤에 붙임 (중복 없음)', () => {
  const samsung = card('005930', '삼성전자');
  const hynix = card('000660', 'SK하이닉스');
  const naver = card('035420', 'NAVER');
  const known = { '005930': samsung, '000660': hynix, '035420': naver };
  const out = withSelectedStocks([naver], known, { '005930': 'watching', '035420': 'holding' });
  assert.deepEqual(out.map((s) => s.stock_code), ['035420', '005930']);
});

test('화면 목록: 모르는 종목 코드는 붙이지 않음', () => {
  assert.deepEqual(withSelectedStocks([], {}, { '999999': 'watching' }), []);
});
