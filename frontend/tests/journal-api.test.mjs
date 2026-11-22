import assert from 'node:assert/strict';
import test from 'node:test';

import { byEdited, fromServer, journalDates, toServer } from '../src/ui/screens/journal/journalApi.ts';

/* 투자 기록 화면 ↔ 서버 변환 (DB 없이). 서식이 오가며 사라지지 않고, 날짜는 한국 시간 기준 */

const UI = [
  { s: 'title', text: '  10/13 투자 복기 ' },
  { s: 'body', text: '오늘 반도체가 올랐다.' },
  { s: 'head', text: '다음 액션' },
  { s: 'sub', text: '작은 제목', u: true },
  { s: 'body', text: '하나', l: 'dot', b: true },
  { s: 'body', text: '인용', l: 'quote', i: true },
  { s: 'body', text: '실적 발표일 확인', check: true, x: true },
  { s: 'body', text: '분할 매수 계획', check: false },
];

test('화면 → 서버: 제목 분리 · 줄 모양 · 서식은 켜진 것만', () => {
  const { title, blocks } = toServer(UI);
  assert.equal(title, '10/13 투자 복기');
  assert.deepEqual(blocks, [
    { id: 'l1', type: 'paragraph', text: '오늘 반도체가 올랐다.' },
    { id: 'l2', type: 'heading', text: '다음 액션' },
    { id: 'l3', type: 'heading', text: '작은 제목', level: 2, underline: true },
    { id: 'l4', type: 'paragraph', text: '하나', list_style: 'dot', bold: true },
    { id: 'l5', type: 'paragraph', text: '인용', list_style: 'quote', italic: true },
    { id: 'l6', type: 'checklist', text: '실적 발표일 확인', checked: true, strike: true },
    { id: 'l7', type: 'checklist', text: '분할 매수 계획', checked: false },
  ]);
});

const entry = (over = {}) => ({
  id: '42', title: '10/13 투자 복기', stock_code: null, stock_name: null, pinned: true,
  created_at: '2026-10-13T09:20:00+00:00', updated_at: '2026-10-13T09:20:00+00:00', ...over,
});

test('서버 → 화면 → 서버: 서식이 그대로 돌아옴 (왕복)', () => {
  const sent = toServer(UI);
  const back = fromServer(entry({ blocks: sent.blocks }), new Date('2026-11-22T03:00:00Z'));
  assert.deepEqual(back.blocks, [{ s: 'title', text: '10/13 투자 복기' }, ...UI.slice(1)]);
  assert.equal(back.pinned, true);
  assert.equal(back.id, '42');
  assert.deepEqual(toServer(back.blocks, back.extra), sent);
});

test('화면에 없는 표·첨부는 extra 로 들고 있다가 저장할 때 뒤에 그대로 (id 겹치지 않게)', () => {
  const table = { id: 'l1', type: 'table', rows: [['항목', '값']] };
  const file = { id: 'f', type: 'attachment', name: 'IR.pdf', url: 'https://example.com/ir.pdf' };
  const back = fromServer(entry({ blocks: [{ id: 'p', type: 'paragraph', text: '본문' }, table, file] }));
  assert.deepEqual(back.blocks, [{ s: 'title', text: '10/13 투자 복기' }, { s: 'body', text: '본문' }]);
  assert.deepEqual(back.extra, [table, file]);
  const { blocks } = toServer(back.blocks, back.extra);
  assert.deepEqual(blocks.map((b) => b.id), ['l2', 'l1', 'f']);          // 표의 id l1 과 겹치지 않게 l2
  assert.deepEqual(blocks.slice(1), [table, file]);
});

test('빈 기록: 제목 줄 하나만', () => {
  assert.deepEqual(fromServer(entry({ title: '', blocks: [] })).blocks, [{ s: 'title', text: '' }]);
  assert.deepEqual(toServer([{ s: 'title', text: '' }]), { title: '', blocks: [] });
});

test('날짜 글자 (한국 시간): 오늘은 시각, 그 밖은 날짜', () => {
  const now = new Date('2026-11-22T07:20:00Z');                          // KST 11-22 오후 4:20
  assert.deepEqual(journalDates('2026-11-22T07:20:00Z', now), { date: '오후 4:20', web_date: '11월 22일', full: '2026년 11월 22일 오후 4:20', group: '오늘' });
  assert.deepEqual(journalDates('2026-10-13T09:20:00Z', now), { date: '2026. 10. 13.', web_date: '10월 13일', full: '2026년 10월 13일 오후 6:20', group: '10월' });
  assert.equal(journalDates('2026-11-21T23:59:00Z', now).full, '2026년 11월 22일 오전 8:59');
  assert.equal(journalDates('2026-11-21T00:05:00Z', now).full, '2026년 11월 21일 오전 9:05');
  assert.equal(journalDates('2026-11-21T04:00:00Z', now).date, '2026. 11. 21.');
  assert.equal(journalDates('2026-11-21T16:00:00+00:00', now).full.endsWith('오전 1:00'), true);
});

test('날짜 묶음: 오늘 · 어제 · 지난 7일 · 지난 30일 · 월 · 다른 해', () => {
  const now = new Date('2026-11-22T03:00:00Z');                          // KST 11-22 정오
  const g = (iso) => journalDates(iso, now).group;
  assert.equal(g('2026-11-21T15:30:00Z'), '오늘');                       // UTC 로는 21일이지만 KST 22일 00:30
  assert.equal(g('2026-11-21T14:30:00Z'), '어제');                       // KST 21일 23:30
  assert.equal(g('2026-11-15T03:00:00Z'), '지난 7일');
  assert.equal(g('2026-10-25T03:00:00Z'), '지난 30일');
  assert.equal(g('2026-09-25T03:00:00Z'), '9월');
  assert.equal(g('2025-12-31T03:00:00Z'), '2025년 12월');
});

test('목록 순서: 고친 날 최신부터', () => {
  const list = [{ id: 'a', updated_at: '2026-11-20T00:00:00Z' }, { id: 'b', updated_at: '2026-11-22T00:00:00Z' }, { id: 'c', updated_at: '2026-11-21T00:00:00Z' }];
  assert.deepEqual([...list].sort(byEdited).map((j) => j.id), ['b', 'c', 'a']);
});
