import { mockJournalGroupOrder } from './Journal.mock';
import type { JBlock, JournalEntry } from './Journal.types';

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

/** 첫 줄 = 제목 (원본: 첫 블록 글자) */
export const titleOf = (blocks: JBlock[]) => (blocks[0]?.text ?? '').trim();

/** 빈 기록 (원본: 글자 없고 사진 없음) */
export const isEmptyEntry = (blocks: JBlock[]) => blocks.every((b) => !b.text.trim());

/** 앱 목록 제목 (원본 n.t = 제목 || '새로운 기록') */
export const appTitle = (j: JournalEntry) => j.title || '새로운 기록';

const esc = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const marks = (b: JBlock) => {
  let h = b.text ? esc(b.text).replace(/\n/g, '<br>') : '<br>';
  if (b.b) h = `<b>${h}</b>`;
  if (b.i) h = `<i>${h}</i>`;
  if (b.u) h = `<u>${h}</u>`;
  if (b.x) h = `<s>${h}</s>`;
  return h;
};

/** 웹 본문 HTML (원본 toHtml: p · h1 · h2 · h3 · ul/ul.dash/ol · blockquote) — 제목·체크리스트 줄은 빼고 */
export function blocksToHtml(blocks: JBlock[]) {
  let out = '';
  let open: string | null = null;
  const close = () => {
    if (open) out += open === 'ol' ? '</ol>' : '</ul>';
    open = null;
  };
  blocks.forEach((b) => {
    const list = b.l === 'dot' ? 'ul' : b.l === 'dash' ? 'ul class="dash"' : b.l === 'num' ? 'ol' : null;
    if (list) {
      if (open !== list) {
        close();
        out += `<${list}>`;
        open = list;
      }
      out += `<li>${marks(b)}</li>`;
      return;
    }
    close();
    if (b.l === 'quote') out += `<blockquote>${marks(b)}</blockquote>`;
    else out += `<${b.s === 'title' ? 'h1' : b.s === 'head' ? 'h2' : b.s === 'sub' ? 'h3' : 'p'}>${marks(b)}</${b.s === 'title' ? 'h1' : b.s === 'head' ? 'h2' : b.s === 'sub' ? 'h3' : 'p'}>`;
  });
  close();
  return out || '<p><br></p>';
}

/** 웹: 제목 · 본문 · 할 일로 나눔 (원본 웹은 제목 칸 · 본문 · '다음 액션' 할 일이 따로) */
export function splitWeb(blocks: JBlock[]) {
  const rest = blocks.slice(1);
  const body = rest.filter((b) => b.check === undefined);
  const todo = rest.filter((b) => b.check !== undefined);
  return { title: blocks[0]?.text ?? '', body, todo };
}
