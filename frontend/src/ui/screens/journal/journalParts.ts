import { mockJournalGroupOrder } from './Journal.mock';
import type { JournalEntry } from './Journal.types';

/** 목록 둘째 줄 미리보기: 첫 줄(제목) 뒤 글을 한 줄로 (원본 prevOf) */
export const preview = (j: JournalEntry) =>
  j.blocks
    .slice(1)
    .map((b) => b.text.replace(/\n/g, ' ').trim())
    .filter(Boolean)
    .join(' ');

/** 웹 목록 둘째 줄: 본문 첫 문장 (원본 web body[0] 첫 문장) */
export const firstSentence = (j: JournalEntry) => {
  const b = j.blocks.slice(1).find((x) => x.check === undefined && x.s === 'body' && x.text.trim());
  return (b?.text.replace(/\n/g, ' ') ?? '').split(/(?<=[.!?。])\s/)[0];
};

/** 검색 (제목 + 미리보기에 그대로 들어간 글자) */
export const searchJournal = (list: JournalEntry[], q: string) => {
  const t = q.trim();
  if (!t) return list;
  return list.filter((j) => `${j.title} ${preview(j)}`.includes(t));
};

/** 글자를 찾은 말 기준으로 나눔 — [앞, 찾은 말, 뒤, 찾은 말, …] (홀수 칸이 찾은 말) */
export const splitHit = (text: string, q: string) => {
  const t = q.trim();
  if (!t) return [text];
  const out: string[] = [];
  text.split(t).forEach((p, i, a) => {
    out.push(p);
    if (i < a.length - 1) out.push(t);
  });
  return out;
};

/** 고정됨 + 날짜 묶음 (grouping 꺼지면 '모든 기록' 한 묶음 · 원본 render) */
export function groupJournal(list: JournalEntry[], grouping: boolean, allLabel: string) {
  const pins = list.filter((j) => j.pinned);
  const rest = list.filter((j) => !j.pinned);
  const groups: { key: string; items: JournalEntry[] }[] = [];
  if (grouping) {
    const order = [...mockJournalGroupOrder, ...rest.map((j) => j.group).filter((g) => !mockJournalGroupOrder.includes(g))];
    [...new Set(order)].forEach((g) => {
      const r = rest.filter((j) => j.group === g);
      if (r.length) groups.push({ key: g, items: r });
    });
  } else if (rest.length) groups.push({ key: allLabel, items: rest });
  return { pins, groups };
}
