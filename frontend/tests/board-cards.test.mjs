import assert from 'node:assert/strict';
import test from 'node:test';

import { addChecklist, addMemo, arrange, removeCards, restoreCards, setPinned } from '../src/ui/screens/board/boardCards.ts';

/* 메모 보드 카드 순서 · 고정 구역 규칙 (앱·웹 공통, DB 없이) */
const card = (id, pinned = false) => ({ id, pinned });
const board = () => ({ memos: [card('p', true), card('a'), card('b')], checklists: [card('c1'), card('c2')], order: ['a', 'p', 'c1', 'b', 'c2'] });

test('고정 먼저, 구역 안은 저장된 순서 · 모르는 id 는 무시', () => {
  assert.deepEqual(arrange(board()), ['p', 'a', 'c1', 'b', 'c2']);
  assert.deepEqual(arrange({ ...board(), order: ['x', 'b'] }), ['p', 'c1', 'c2', 'a', 'b']);
});

test('새 메모 · 새 체크리스트는 일반 구역 맨 위, 기존 카드는 그대로', () => {
  assert.deepEqual(addMemo(board(), card('n')).order, ['p', 'n', 'a', 'c1', 'b', 'c2']);
  const b = addChecklist(board(), card('c3'));
  assert.deepEqual(b.order, ['p', 'c3', 'a', 'c1', 'b', 'c2']);
  assert.equal(b.checklists.length, 3);
});

test('고정하면 고정 구역 맨 위, 풀면 일반 구역 맨 위 (체크리스트도)', () => {
  const on = setPinned(board(), ['c2'], true);
  assert.deepEqual(on.order, ['c2', 'p', 'a', 'c1', 'b']);
  assert.deepEqual(setPinned(on, ['p'], false).order, ['c2', 'p', 'a', 'c1', 'b']);
  assert.deepEqual(setPinned(on, ['c2'], false).order, ['p', 'c2', 'a', 'c1', 'b']);
});

test('지우고 되돌리면 있던 자리로, 두 번 되돌려도 하나', () => {
  const { cards, removed } = removeCards(board(), ['a', 'c1']);
  assert.deepEqual(cards.order, ['p', 'b', 'c2']);
  const back = restoreCards(cards, removed);
  assert.deepEqual(arrange(back), ['p', 'a', 'c1', 'b', 'c2']);
  assert.equal(restoreCards(back, removed).memos.length, 3);
});
