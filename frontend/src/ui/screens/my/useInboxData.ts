import { env } from '@/config/env';
import { useMarkAiUpdateRead, useUpdates } from '@/hooks/queries';
import { useMyMock } from '@/store/myMock';
import type { AiUpdate } from '@/types/models';
import { ago } from '@/ui/screens/updates/updatesFormat';
import { mockInbox, type InboxItem } from './My.mock';

/** 알림함에 보여 줄 최대 개수 (최신순) */
const LIMIT = 30;
const kstDay = (iso: string) => new Date(Date.parse(iso) + 9 * 3600_000).toISOString().slice(0, 10);

/** AI 업데이트 카드 → 알림 한 줄. 날짜 묶음은 한국 날짜로 오늘 · 어제 · 이전 */
export function toInboxItem(u: AiUpdate, now: string): InboxItem {
  const at = u.created_at ?? u.published_at;
  const today = kstDay(now);
  const yesterday = kstDay(new Date(Date.parse(now) - 86400_000).toISOString());
  const d = kstDay(at);
  return {
    id: u.id,
    kind: 'ai',
    day: d === today ? '오늘' : d === yesterday ? '어제' : '이전',
    title: `${u.stock_name} · ${u.memo_title}`,
    sub: u.headline || u.summary || '메모에 새 소식이 연결됐어요',
    when: ago(at, now),
    stock_code: u.stock_code,
    memo_id: u.memo_id,
  };
}

/**
 * 알림함(사이드바 종 · 앱 알림) 데이터 (2026-11-23).
 * - 실제 모드: 내 종목의 AI 업데이트(GET /updates, 최근 30일)를 알림으로. 안 읽음 = 카드 read=false (서버 is_read)
 *   누르면 그 카드 · 모두 읽음이면 안 읽은 카드 전부를 POST /ai-updates/{id}/read → 종 배지 · 홈 · 업데이트 화면이 함께 줄어듦
 *   스튜디오 알림(라디오 · 보고서 완성)은 아직 서버에 없어 실제 모드에서는 안 보임
 * - mock 모드: 지금처럼 My.mock 예시와 화면 안 읽음 상태(store/myMock)
 */
export function useInboxData() {
  const real = !env.useMock;
  const updates = useUpdates();
  const markRead = useMarkAiUpdateRead();
  const mockUnread = useMyMock((s) => s.unread);
  const mockRead = useMyMock((s) => s.read);
  const mockReadAll = useMyMock((s) => s.readAll);

  if (!real) return { items: mockInbox, unread: mockUnread, read: mockRead, readAll: mockReadAll };

  const now = new Date().toISOString();
  const cards = ((updates.data ?? []) as AiUpdate[]).slice(0, LIMIT);
  const unread = cards.filter((u) => !u.read).map((u) => u.id);
  return {
    items: cards.map((u) => toInboxItem(u, now)),
    unread,
    read: (id: string) => {
      if (unread.includes(id)) markRead.mutate([id]);
    },
    readAll: () => {
      if (unread.length) markRead.mutate(unread);
    },
  };
}
