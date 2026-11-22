import assert from 'node:assert/strict';
import test from 'node:test';

import { checklistsFrom, layoutFrom, updateRows, widgetsFrom } from '../src/ui/screens/home/homeMine.ts';
import { toFeedItem } from '../src/ui/screens/memo/toFeedItem.ts';

/* 홈 내 데이터 · 업데이트 카드 변환 (DB 없이, 2026-11-22) */

const stock = (code, name, status, unread) => ({ code, name, market: 'KOSPI', status, tags: [], unread_updates: unread, added_at: '2026-11-01' });
const card = (over = {}) => ({
  id: '7', stock_code: '105560', stock_name: 'KB금융', type: 'disclosure', title: '분기보고서 (2026.09)', source: 'DART',
  url: 'https://dart.fss.or.kr/x', published_at: '2026-11-16', memo_id: '4', memo_title: '[점검] M07', memo_version: 1,
  summary: '요약', headline: '분기배당 주당배당금 공시', read: false, relevance: 1, memo_color: 'blue',
  sources: [{ kind: 'disclosure', ref: 'disc:1', title: '분기보고서 (2026.09)', source: 'DART', url: null, published_at: '2026-11-16', quote: '[청크 1094] 주당배당금은 1,143원이에요.' }],
  ...over,
});
const logo = (code, name) => ({ logo: name[0], logo_bg: '#000' });

test('widgets: 저장한 적 없으면 기본, 서버 checklist = 화면 check, 모르는 위젯은 뺌', () => {
  assert.deepEqual(widgetsFrom({ mode: 'unset', widgets: [] }, ['market', 'news']), ['market', 'news']);
  assert.deepEqual(widgetsFrom(undefined, ['market']), ['market']);
  const saved = { mode: 'template', widgets: [{ id: 'a', type: 'checklist', span: 2 }, { id: 'b', type: 'calendar', span: 2 }, { id: 'c', type: 'market', span: 4 }] };
  assert.deepEqual(widgetsFrom(saved, []), ['check', 'market']);
  assert.deepEqual(layoutFrom(['market', 'check']).widgets.map((w) => [w.type, w.span]), [['market', 4], ['checklist', 2]]);
});

test('updates: 종목마다 안 읽은 수 + 그 종목 가장 새 카드', () => {
  const rows = updateRows([stock('105560', 'KB금융', 'watching', 3), stock('035420', 'NAVER', 'holding', 0)], [card(), card({ id: '3', headline: '옛 카드' })], logo);
  assert.equal(rows[0].new_count, 3);
  assert.deepEqual(rows[0].latest, { kind: '공시', title: '분기배당 주당배당금 공시', memo_title: '[점검] M07', memo_color: 'blue' });
  assert.equal(rows[1].latest, undefined);
  assert.equal(rows[1].logo, 'N');
});

test('checklists: 종목별로 묶기', () => {
  const out = checklistsFrom([
    { id: '1', checklist_id: '9', text: '공시 확인', done: false, stock_code: '000660', stock_name: 'SK하이닉스' },
    { id: '2', checklist_id: '9', text: '실적 확인', done: true, stock_code: '000660', stock_name: 'SK하이닉스' },
  ]);
  assert.equal(out['000660'].id, '9');
  assert.deepEqual(out['000660'].items.map((i) => [i.id, i.done]), [['1', false], ['2', true]]);
});

test('toFeedItem: 공시 — 날짜만 온 값은 한국 0시, 원문 앞 청크 표시는 뺌', () => {
  const f = toFeedItem(card());
  assert.equal(f.kind, '공시');
  assert.equal(f.at, '2026-11-16T00:00:00+09:00');
  assert.equal(f.source, 'DART · 2026. 11. 16.');
  assert.equal(f.quote, '주당배당금은 1,143원이에요.');
  assert.equal(f.report, '분기보고서 (2026.09)');
  assert.equal(f.unread, true);
});

test('toFeedItem: 가격 — 조건가와 차이, 차트 날짜', () => {
  const f = toFeedItem(card({
    type: 'price', source: 'KRX', url: null, published_at: '2026-11-10', read: true, sources: [],
    price: { state: 'reached', observed_value: 1212000, observed_trade_date: '2026-11-10', threshold: 400000, direction: 'above', closes: [1100000, 1212000], closes_from: '2026-10-28' },
  }));
  assert.equal(f.kind, '주가');
  assert.equal(f.source, 'KRX · 11.10 종가');
  assert.deepEqual([f.price.cond, f.price.direction, f.price.tone, f.price.gap, f.price.from, f.price.to],
    [400000, '이상', 'reached', '+812,000원 (+203.0%)', '10.28', '11.10']);
});
