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
