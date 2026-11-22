import assert from 'node:assert/strict';
import test from 'node:test';

import { createRealBoardApi } from '../src/api/board.ts';

function client(responses = {}) {
  const calls = [];
  const invoke = async (method, path, body) => {
    calls.push({ method, path, body });
    const response = responses[`${method} ${path}`];
    if (response instanceof Error) throw response;
    return response;
  };
  return {
    calls,
    http: {
      get: (path) => invoke('GET', path),
      post: (path, body) => invoke('POST', path, body),
      put: (path, body) => invoke('PUT', path, body),
      patch: (path, body) => invoke('PATCH', path, body),
      del: (path) => invoke('DELETE', path),
    },
  };
}

const common = {
  stock_code: '005930 ',
  position: 0,
  created_at: '2026-11-05T00:00:00Z',
  updated_at: '2026-11-05T00:00:00Z',
};
const memo = {
  ...common, id: 1, kind: 'memo', title: '투자 메모', body: '본문', tags: ['실적'],
  color: 'blue', pinned: true, ai_linked: false, ai_linked_at: null,
  price_conditions: [], unread_updates: 0,
};
const checklist = {
  ...common, id: 2, kind: 'checklist', title: '확인',
  items: [{ id: 20, text: '공시 확인', done: false }],
};
const reference = {
  ...common, id: 3, kind: 'reference', title: '자료',
  links: [{ id: 30, title: 'IR', url: 'https://example.com', ref_type: 'ir', source: 'link' }],
};

test('uses all FastAPI memo-board CRUD paths and normalizes wire values', async () => {
  const fake = client({
    'GET /stocks/005930/board': [memo, checklist, reference],
    'GET /board-items/1': memo,
    'POST /stocks/005930/memos': memo,
    'POST /stocks/005930/checklists': checklist,
    'POST /stocks/005930/references': reference,
    'PATCH /board-items/1': { ...memo, title: '수정' },
    'PATCH /checklists/2/items/20': { ...checklist, items: [{ ...checklist.items[0], done: true }] },
    'PUT /memos/1/ai-link': { ...memo, ai_linked: true },
    'DELETE /board-items/3': undefined,
  });
  const api = createRealBoardApi(fake.http);
  const board = await api.listBoard('005930');
  assert.deepEqual(board.map((item) => item.kind), ['memo', 'checklist', 'reference']);
  assert.equal(board[0].stock_code, '005930');
  assert.equal(board[1].items[0].id, '20');
  assert.equal(board[2].links[0].id, '30');
  assert.equal((await api.getBoardItem('1')).id, '1');
  await api.createMemo('005930', { title: '투자 메모', body: '본문', tags: ['실적'], color: 'blue', ai_linked: false });
  await api.createChecklist('005930', { title: '확인', items: [{ text: '공시 확인', done: false }] });
  await api.createReference('005930', { title: '자료', links: [{ title: 'IR', url: 'https://example.com', ref_type: 'ir', source: 'link' }] });
  await api.updateBoardItem('1', { title: '수정' });
  await api.setBoardChecklistItem('2', '20', true);
  assert.equal((await api.setAiLink('1', true)).ai_linked, true);
  await api.deleteBoardItem('3');
  assert.deepEqual(fake.calls.map(({ method, path }) => `${method} ${path}`), [
    'GET /stocks/005930/board', 'GET /board-items/1', 'POST /stocks/005930/memos',
    'POST /stocks/005930/checklists', 'POST /stocks/005930/references',
    'PATCH /board-items/1', 'PATCH /checklists/2/items/20',
    'PUT /memos/1/ai-link', 'DELETE /board-items/3',
  ]);
});

test('saves the whole board order and answers a confirmation', async () => {
  // 2026-11-20 순서 저장(0019 memos.position · PUT board-order)이 생겨 '순서 저장 안 함' 막기는 없어짐
  const fake = client({
    'PUT /stocks/005930/board-order': [{ ...checklist, position: 0 }, { ...memo, position: 1 }],
    'POST /memos/1/confirmations': { ...memo, analysis: { status: 'confirmed', items: [], confirmations: [] } },
  });
  const api = createRealBoardApi(fake.http);
  const board = await api.reorderBoard('005930', ['2', '1']);
  assert.deepEqual(board.map((b) => [b.id, b.position]), [['2', 0], ['1', 1]]);
  assert.deepEqual(fake.calls[0].body, { ids: [2, 1] });
  const answered = await api.answerConfirmation('1', 'option-token-123');
  assert.equal(answered.analysis.status, 'confirmed');
  assert.deepEqual(fake.calls[1].body, { option_id: 'option-token-123' });
});

test('propagates authentication and network failures', async () => {
  for (const error of [new Error('401 Unauthorized'), new Error('Network unavailable')]) {
    const fake = client({ 'GET /stocks/005930/board': error });
    await assert.rejects(() => createRealBoardApi(fake.http).listBoard('005930'), error);
  }
});

test('rejects an unknown board kind instead of losing fields', async () => {
  const fake = client({ 'GET /stocks/005930/board': [{ ...common, id: 9, kind: 'unknown' }] });
  await assert.rejects(() => createRealBoardApi(fake.http).listBoard('005930'), /지원하지 않는 보드 유형/);
});
