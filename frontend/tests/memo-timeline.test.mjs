import assert from 'node:assert/strict';
import test from 'node:test';

import { buildTimeline } from '../src/ui/screens/memo/memoTimeline.ts';

/* 2026-11-25 AI 업데이트 탭: 소식은 '붙은 날'(arrived)로 줄 세운다. 메모보다 먼저 나온 자료(11/16 기사)가 11/18에 붙어도 메모 위에 */
const memo = { ai_linked: true, ai_linked_at: '2026-11-17T20:00:00+09:00' };
const versions = [{ version: 1, title: 'HBM4 출하 얼마나?', body: '', saved_at: '2026-11-17T20:00:00+09:00' }];
const feed = (id, at, arrived) => ({ id, kind: '뉴스', at, arrived, headline: id, summary: '', source: '', url: null });

test('메모보다 먼저 나온 자료라도 붙은 날이 뒤면 메모 위에', () => {
  const rows = buildTimeline(memo, versions, [feed('old', '2026-11-16T08:08:00+09:00', '2026-11-18T06:30:00+09:00'), feed('new', '2026-11-17T09:00:00+09:00', '2026-11-18T06:30:01+09:00')]);
  assert.deepEqual(rows.map((r) => (r.t === 'feed' ? r.item.id : r.t)), ['new', 'old', 'ai', 'rev']);
});

test('붙은 날이 없으면(옛 데이터·mock) 자료 날짜로', () => {
  const rows = buildTimeline(memo, versions, [feed('old', '2026-11-16T08:08:00+09:00')]);
  assert.deepEqual(rows.map((r) => (r.t === 'feed' ? r.item.id : r.t)), ['ai', 'rev', 'old']);
});
