import type { JournalBlock as ApiBlock, JournalEntry as ApiEntry, JournalLineFormat } from '@/types/models';
import type { JBlock, JournalEntry } from './Journal.types';

/**
 * 투자 기록 화면 ↔ 서버 (GET·POST /journal · PATCH /journal/{id}) 변환 (2026-11-22, 표 C-32).
 * - 화면 첫 줄(제목 줄) = 서버 title. 나머지 줄 = 서버 blocks
 *   body → paragraph · head → heading · sub → heading level 2 · check → checklist(checked)
 *   l → list_style · b/i/u/x → bold/italic/underline/strike (켜진 것만 보냄)
 * - 화면에 없는 표·첨부 블록은 extra 로 들고 있다가 저장할 때 뒤에 그대로 다시 보냄 (지우지 않음)
 * - 날짜 글자·묶음은 서버 updated_at(고친 날)으로, 한국 시간 기준
 * 화면 전용 html(웹 편집기 글자 일부 서식)은 서버에 칸이 없어 보내지 않음 — 다시 열면 줄 서식만 남음
 */

const KST_MS = 9 * 3600_000;
const DAY_MS = 86_400_000;

/** ISO → 한국 날짜·시각 숫자 */
function kst(iso: string | Date) {
  const d = new Date(+new Date(iso) + KST_MS);
  return { y: d.getUTCFullYear(), m: d.getUTCMonth() + 1, d: d.getUTCDate(), h: d.getUTCHours(), mi: d.getUTCMinutes(), day: Math.floor(+d / DAY_MS) };
}

const hm = (h: number, mi: number) => `${h < 12 ? '오전' : '오후'} ${h % 12 || 12}:${String(mi).padStart(2, '0')}`;

/** 목록 날짜 · 기록 위 날짜 · 묶음 이름 (원본 n.d · j.date · n.full · n.g) */
export function journalDates(iso: string, now: Date = new Date()): Pick<JournalEntry, 'date' | 'web_date' | 'full' | 'group'> {
  const t = kst(iso);
  const n = kst(now);
  const ago = n.day - t.day;
  const group =
    ago <= 0 ? '오늘' : ago === 1 ? '어제' : ago <= 7 ? '지난 7일' : ago <= 30 ? '지난 30일' : t.y === n.y ? `${t.m}월` : `${t.y}년 ${t.m}월`;
  return {
    date: ago <= 0 ? hm(t.h, t.mi) : `${t.y}. ${t.m}. ${t.d}.`,
    web_date: `${t.m}월 ${t.d}일`,
    full: `${t.y}년 ${t.m}월 ${t.d}일 ${hm(t.h, t.mi)}`,
    group,
  };
}

function formatOf(b: JBlock): JournalLineFormat {
  const f: JournalLineFormat = {};
  if (b.l) f.list_style = b.l;
  if (b.b) f.bold = true;
  if (b.i) f.italic = true;
  if (b.u) f.underline = true;
  if (b.x) f.strike = true;
  return f;
}

function lineOf(f: JournalLineFormat): Pick<JBlock, 'l' | 'b' | 'i' | 'u' | 'x'> {
  const o: Pick<JBlock, 'l' | 'b' | 'i' | 'u' | 'x'> = {};
  if (f.list_style) o.l = f.list_style;
  if (f.bold) o.b = true;
  if (f.italic) o.i = true;
  if (f.underline) o.u = true;
  if (f.strike) o.x = true;
  return o;
}

/** 화면 줄들 → 서버 {title, blocks}. extra(표·첨부)는 뒤에 그대로 */
export function toServer(blocks: JBlock[], extra: ApiBlock[] = []): { title: string; blocks: ApiBlock[] } {
  const title = (blocks[0]?.text ?? '').trim();
  const used = new Set(extra.map((b) => b.id));
  let n = 0;
  const nextId = () => {
    let id: string;
    do id = `l${++n}`;
    while (used.has(id));
    return id;
  };
  const lines: ApiBlock[] = blocks.slice(1).map((b) => {
    const id = nextId();
    const f = formatOf(b);
    if (b.check !== undefined) return { id, type: 'checklist', text: b.text, checked: !!b.check, ...f };
    if (b.s === 'sub') return { id, type: 'heading', text: b.text, level: 2, ...f };
    if (b.s === 'head' || b.s === 'title') return { id, type: 'heading', text: b.text, ...f };
    return { id, type: 'paragraph', text: b.text, ...f };
  });
  return { title, blocks: [...lines, ...extra] };
}

/** 서버 기록 → 화면 기록 (첫 줄 = 제목 줄) */
export function fromServer(e: ApiEntry, now: Date = new Date()): JournalEntry {
  const lines: JBlock[] = [];
  const extra: ApiBlock[] = [];
  for (const b of e.blocks) {
    if (b.type === 'table' || b.type === 'attachment') {
      extra.push(b);
      continue;
    }
    const f = lineOf(b);
    if (b.type === 'checklist') lines.push({ s: 'body', text: b.text, check: !!b.checked, ...f });
    else if (b.type === 'heading') lines.push({ s: b.level === 2 ? 'sub' : 'head', text: b.text, ...f });
    else lines.push({ s: 'body', text: b.text, ...f });
  }
  return {
    id: e.id,
    title: e.title,
    ...journalDates(e.updated_at, now),
    pinned: !!e.pinned,
    blocks: [{ s: 'title', text: e.title }, ...lines],
    updated_at: e.updated_at,
    extra: extra.length ? extra : undefined,
  };
}

/** 목록 순서: 고친 날 최신부터 (화면 규칙 — 서버는 만든 순으로 줌) */
export const byEdited = (a: JournalEntry, b: JournalEntry) => +new Date(b.updated_at ?? 0) - +new Date(a.updated_at ?? 0);
