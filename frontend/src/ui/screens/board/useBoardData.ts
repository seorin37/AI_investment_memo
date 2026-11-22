import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/api';
import { env } from '@/config/env';
import {
  qk,
  useBoard,
  useDeleteBoardItem,
  useMemoTimeline,
  useReorderBoard,
  useRestoreTrash,
  useSetBoardChecklistItem,
  useUpdateBoardItem,
} from '@/hooks/queries';
import type { BoardItem, Checklist, Memo, MemoAnalysis, MemoColor, MemoTimeline, MemoVersion } from '@/types/models';
import type { AiTrackItem, MemoFeedItem } from '@/ui/screens/memo/MemoDetail.types';
import { toFeedItem } from '@/ui/screens/memo/toFeedItem';

/**
 * 메모 보드(③) · 메모 창(④) 실제 데이터 (2026-11-22, 업데이트 useUpdatesData 와 같은 틀).
 * - 보드: GET /stocks/{code}/board → 메모 · 체크리스트(화면은 1개, 첫 번째) · 카드 순서(position)
 * - 메모 창: GET /memos/{id}/timeline → 수정 이력 · AI 소식 · 추적 항목
 * - 쓰기: 화면은 지금처럼 자기 상태를 먼저 바꾸고, 여기 함수가 서버에 보낸다 (mock 모드면 아무것도 안 함)
 * - AI 연결 (전수 검사 결정 7, 임시안 '저장 = 켜기'): 연결 창이 열릴 때 PUT ai-link(켜기) → 분석 결과를 창에 보여 줌,
 *   '일반 메모로 두기' = 끄기. 분석만 하는 API 는 없다
 */
export function boardFrom(items: BoardItem[]): { memos: Memo[]; checklist: Checklist | null; order: string[] } {
  const sorted = [...items].sort((a, b) => a.position - b.position);
  const memos = sorted.filter((b): b is Memo => b.kind === 'memo');
  const checklist = sorted.find((b): b is Checklist => b.kind === 'checklist') ?? null;
  return { memos, checklist, order: sorted.filter((b) => b.kind === 'memo' || b.id === checklist?.id).map((b) => b.id) };
}

const DIR: Record<string, '이하' | '이상'> = {
  price_below: '이하',
  price_above: '이상',
};

/** 분석 항목 → 연결 창·메모 창의 추적 항목. 가격은 조건가가 있을 때만 가격 모양 */
export function toTrackItems(items: { type: string; description: string; price_threshold?: number | null }[]): AiTrackItem[] {
  return items.map((i) =>
    DIR[i.type] && i.price_threshold != null
      ? { kind: 'price', label: i.description, price: i.price_threshold, direction: DIR[i.type], quote: i.description }
      : { kind: 'fact', label: i.description, quote: i.description },
  );
}

/** 타임라인 → 수정 이력(최신이 앞) · 소식 · 추적 항목 */
export function detailFrom(t: MemoTimeline & { tracking_items?: { type: string; description: string }[] }): {
  versions: MemoVersion[];
  feed: MemoFeedItem[];
  trackItems: AiTrackItem[];
} {
  const versions = t.entries
    .flatMap((e) => (e.kind === 'memo_created' || e.kind === 'memo_edit' ? [e.version] : []))
    .sort((a, b) => b.version - a.version);
  const feed = t.entries.flatMap((e) => (e.kind === 'update' ? [toFeedItem(e.update)] : []));
  return { versions, feed, trackItems: toTrackItems((t.tracking_items ?? []).filter((i) => i.type !== 'ask')) };
}

export type ConnectResult = { state: 'items' | 'empty' | 'error'; items: AiTrackItem[] };

const connectResult = (a: MemoAnalysis | null | undefined): ConnectResult => {
  if (!a || a.status === 'failed') return { state: 'error', items: [] };
  const items = toTrackItems(a.items.filter((i) => i.type !== 'ask'));
  return { state: items.length ? 'items' : 'empty', items };
};

export function useBoardData(code: string, openId: string | null) {
  const real = !env.useMock;
  const qc = useQueryClient();
  const board = useBoard(real ? code : '');
  const timeline = useMemoTimeline(openId ?? '', real && !!openId && /^\d+$/.test(openId));
  const update = useUpdateBoardItem(code);
  const del = useDeleteBoardItem(code);
  const restore = useRestoreTrash();
  const reorder = useReorderBoard(code);
  const checkItem = useSetBoardChecklistItem();
  const refresh = () => qc.invalidateQueries({ queryKey: qk.board(code) });

  const data = real && board.data ? boardFrom(board.data) : null;
  const detail = real && timeline.data ? detailFrom(timeline.data) : null;
  const ops = {
    save: (id: string, p: { title: string; body: string }) => real && update.mutate({ id, patch: p }),
    color: (ids: string[], color: MemoColor) => real && ids.forEach((id) => update.mutate({ id, patch: { color } })),
    pin: (ids: string[], pinned: boolean) => real && ids.forEach((id) => update.mutate({ id, patch: { pinned } })),
    checkItem: (checklistId: string, itemId: string, done: boolean) =>
      real && checkItem.mutate({ checklistId, itemId, done, stockCode: code }),
    remove: (ids: string[]) => real && ids.forEach((id) => del.mutate(id)),
    /** 되돌리기 = 휴지통 복원 (trash id 'memo-{id}', be/app/trash/service.py _ID) */
    undoRemove: (ids: string[]) => real && ids.forEach((id) => restore.mutate(`memo-${id}`)),
    reorder: (order: string[]) => real && reorder.mutate(order),
    aiOff: (id: string) => real && api.setAiLink(id, false).finally(refresh),
    /** AI 켜기 + 분석 결과 (연결 창) */
    async aiOn(id: string): Promise<ConnectResult> {
      try {
        return connectResult((await api.setAiLink(id, true)).analysis);
      } catch {
        return { state: 'error', items: [] };
      } finally {
        void refresh();
      }
    },
    /** 새 메모 저장 (AI 켜면 저장 응답에 분석이 같이 옴) */
    async create(input: { title: string; body: string; color: MemoColor; ai: boolean }): Promise<{ memo: Memo; connect: ConnectResult } | null> {
      try {
        const memo = await api.createMemo(code, { title: input.title, body: input.body, color: input.color, tags: [], ai_linked: input.ai });
        void refresh();
        return { memo, connect: connectResult(memo.analysis) };
      } catch {
        return null;
      }
    },
  };
  /** 서버 보드를 새로 받은 시각 — 화면이 이 값이 바뀔 때만 자기 상태를 서버 값으로 맞춘다 */
  const version = real ? board.dataUpdatedAt : 0;
  return { real, data, version, loading: real && board.isLoading, detail, ops };
}
