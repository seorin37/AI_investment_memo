import assert from 'node:assert/strict';
import test from 'node:test';

import { createRealStockApi } from '../src/api/stocks.ts';

function client(responses = {}) {
  const calls = [];
  const invoke = async (method, path, value, body) => {
    calls.push({ method, path, value, body });
    const response = responses[`${method} ${path}`];
    if (response instanceof Error) throw response;
    return response;
  };
  return {
    calls,
    http: {
      get: (path, query) => invoke('GET', path, query),
      post: (path, body) => invoke('POST', path, undefined, body),
      patch: (path, body) => invoke('PATCH', path, undefined, body),
      del: (path) => invoke('DELETE', path),
    },
  };
}

const mine = {
  code: '005930',
  name: '삼성전자',
  market: 'KOSPI',
  status: 'watching',
  tags: null,
  unread_updates: null,
  added_at: '2026-11-05T00:00:00Z',
};

test('uses the FastAPI stock CRUD paths and normalizes responses', async () => {
  const fake = client({
    'GET /stocks': [mine],
    'GET /stocks/search': [{ code: '00104K ', name: 'CJ4우(전환)', market: 'KOSPI' }],
    'GET /stocks/005930': mine,
    'POST /stocks': mine,
    'PATCH /stocks/005930': { ...mine, status: 'holding' },
    'DELETE /stocks/005930': undefined,
  });
  const api = createRealStockApi(fake.http);

  assert.deepEqual(await api.listMyStocks(), [{ ...mine, tags: [], unread_updates: 0 }]);
  assert.equal((await api.searchStocks('삼성'))[0].code, '00104K');
  assert.equal((await api.getStock('005930')).code, '005930');
  assert.equal((await api.addStock('005930', 'watching')).status, 'watching');
  assert.equal((await api.updateStock('005930', { status: 'holding' })).status, 'holding');
  await api.removeStock('005930');

  assert.deepEqual(fake.calls, [
    { method: 'GET', path: '/stocks', value: undefined, body: undefined },
    { method: 'GET', path: '/stocks/search', value: { q: '삼성' }, body: undefined },
    { method: 'GET', path: '/stocks/005930', value: undefined, body: undefined },
    { method: 'POST', path: '/stocks', value: undefined, body: { code: '005930', status: 'watching' } },
    { method: 'PATCH', path: '/stocks/005930', value: undefined, body: { status: 'holding' } },
    { method: 'DELETE', path: '/stocks/005930', value: undefined, body: undefined },
  ]);
});

test('does not turn authentication or network errors into successful data', async () => {
  for (const error of [new Error('401 Unauthorized'), new Error('Network unavailable')]) {
    const fake = client({ 'GET /stocks': error });
    await assert.rejects(() => createRealStockApi(fake.http).listMyStocks(), error);
  }
});
