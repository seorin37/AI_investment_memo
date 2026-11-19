import type { Memo, MemoVersion } from '@/types/models';
import type { MemoFeedItem } from './MemoDetail.types';

/** AI 업데이트 탭 한 줄: 메모 기록(고침·첫 메모) · AI 연결 시작 · 소식 */
export type TimelineRow = { t: 'rev'; v: MemoVersion; first: boolean } | { t: 'ai'; at: string } | { t: 'feed'; item: MemoFeedItem };

/* 원본 rkey: 'MM.DD' → MMDD 숫자. 같은 날이면 소식 > AI 연결 시작 > 고친 메모 > 첫 메모 (원본 evList 의 +.5 · +.1 · +.3) */
const dayKey = (iso: string) => {
  const m = iso.match(/-(\d\d)-(\d\d)T/);
  return m ? Number(m[1] + m[2]) : 0;
};

/** 원본 evList: 메모 기록 + (AI 연결이면) 연결 시작 · 소식을 최신순으로 */
export function buildTimeline(memo: Memo, versions: MemoVersion[], feed: MemoFeedItem[]): TimelineRow[] {
  const last = versions.length - 1;
  const rows: { k: number; at: string; r: TimelineRow }[] = versions.map((v, i) => ({ k: dayKey(v.saved_at) + (i === last ? 0 : 0.3), at: v.saved_at, r: { t: 'rev', v, first: i === last } }));
  if (memo.ai_linked && memo.ai_linked_at) rows.push({ k: dayKey(memo.ai_linked_at) + 0.1, at: memo.ai_linked_at, r: { t: 'ai', at: memo.ai_linked_at } });
  if (memo.ai_linked) feed.forEach((f) => rows.push({ k: dayKey(f.at) + 0.5, at: f.at, r: { t: 'feed', item: f } }));
  return rows.sort((a, b) => b.k - a.k || b.at.localeCompare(a.at)).map((x) => x.r);
}

/** 버전이 바뀐 내용 한 줄 (원본 saveRev 의 sum: 제목 바꿈 · 끝에 더함 · 고침) */
export function revSummary(cur: MemoVersion, prev?: MemoVersion): string {
  if (!prev) return '처음 쓴 내용';
  if (cur.title !== prev.title) return `제목 "${prev.title}" → "${cur.title}"`;
  if (cur.body.startsWith(prev.body) && cur.body.length > prev.body.length) {
    const add = cur.body.slice(prev.body.length).replace(/^\n/, '');
    return `"${add.length > 22 ? add.slice(0, 22) + '…' : add}" 추가`;
  }
  return '내용을 고쳤어요';
}

/**
 * 이전 버전 → 이 버전 글 비교 (원본 수정 이력 .vbody: <del> 빨강 지운 글 · <ins> 초록 더한 글).
 * 앞뒤 같은 부분을 빼고 가운데만 지움·더함으로 (어절 경계까지 넓힘).
 */
export function diffParts(prev: string | undefined, cur: string): { t: string; k: 'same' | 'del' | 'ins' }[] {
  if (prev == null || prev === cur) return [{ t: cur, k: 'same' }];
  let a = 0;
  while (a < prev.length && a < cur.length && prev[a] === cur[a]) a++;
  let b = 0;
  while (b < prev.length - a && b < cur.length - a && prev[prev.length - 1 - b] === cur[cur.length - 1 - b]) b++;
  /* 어절 중간에서 끊기지 않게 앞쪽은 빈칸·줄바꿈까지 되돌림 */
  while (a > 0 && !/\s/.test(cur[a - 1])) a--;
  const out: { t: string; k: 'same' | 'del' | 'ins' }[] = [];
  const head = cur.slice(0, a);
  const del = prev.slice(a, prev.length - b);
  const ins = cur.slice(a, cur.length - b);
  const tail = cur.slice(cur.length - b);
  if (head) out.push({ t: head, k: 'same' });
  if (del) out.push({ t: del, k: 'del' });
  if (del && ins) out.push({ t: ' ', k: 'same' });
  if (ins) out.push({ t: ins, k: 'ins' });
  if (tail) out.push({ t: tail, k: 'same' });
  return out;
}

/** 'YYYY-MM-DD…' → 'YYYY년 M월 D일' (원본 앱 .ddate '2026년 10월 1일 작성') */
export function koDate(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d\d)-(\d\d)/);
  return m ? `${m[1]}년 ${Number(m[2])}월 ${Number(m[3])}일` : '';
}

/** 'YYYY-MM-DD…' → 'YYYY. MM. DD' (원본 웹 머리) */
export function dotDate(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d\d)-(\d\d)/);
  return m ? `${m[1]}. ${m[2]}. ${m[3]}` : '';
}

/** 숫자 3자리 쉼표 */
export const won = (v: number) => Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
