import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/api';
import { env } from '@/config/env';
import { qk, useBoardItem, useDeleteBoardItem, useMemoTimeline, useStock, useUpdateBoardItem } from '@/hooks/queries';
import type { Memo, MemoColor, MemoVersion } from '@/types/models';
import { connectResult, detailFrom, type ConnectResult } from '@/ui/screens/board/useBoardData';
import { mockDetailStockName, mockLastChecked, mockTrackItems } from './MemoDetail.mock';
import type { AiTrackItem, MemoFeedItem } from './MemoDetail.types';
import { feedOf, findMemo, mockUpdateStocks, versionsOf } from '@/ui/screens/updates/Updates.mock';

/**
 * 앱 메모 화면들(상세 · 근거 · 수정 이력 · AI 연결) 데이터 (2026-11-22, 웹은 보드 안 창이라 useBoardData 를 씀).
 * - 실제 모드: 메모 GET /board-items/{id} · 이력/소식/추적 항목 GET /memos/{id}/timeline · 종목 이름 GET /stocks/{code}
 *   저장 · 색 · 고정 PATCH · 삭제 DELETE · AI 끄기 PUT ai-link
 * - mock 모드: 지금처럼 보드 예시 메모(Updates.mock findMemo)
 */
const pad = (n: number) => String(n).padStart(2, '0');

/** 추적 항목들의 가장 최근 확인 시각 → '11.22 06:30' (한국 시간) */
export function lastCheckedText(items: { last_checked_at?: string | null }[] | undefined): string | undefined {
  const at = (items ?? []).map((i) => i.last_checked_at).filter((v): v is string => !!v).sort().pop();
  if (!at) return undefined;
  const t = new Date(Date.parse(at) + 9 * 3600_000);
  return `${pad(t.getUTCMonth() + 1)}.${pad(t.getUTCDate())} ${pad(t.getUTCHours())}:${pad(t.getUTCMinutes())}`;
}

export interface MemoScreenData {
  memo: Memo | null;
  stockName: string;
  versions: MemoVersion[];
  feed: MemoFeedItem[];
  trackItems: AiTrackItem[];
  lastChecked?: string;
}

export function useMemoScreen(id: string) {
  const real = !env.useMock;
  const qc = useQueryClient();
  const realId = real && /^\d+$/.test(id) ? id : '';
  const item = useBoardItem(realId, !!realId);
  const timeline = useMemoTimeline(realId, !!realId);
  const memo = item.data?.kind === 'memo' ? item.data : null;
  const stock = useStock(memo?.stock_code ?? '');
  const code = memo?.stock_code ?? '';
  const update = useUpdateBoardItem(code);
  const del = useDeleteBoardItem(code);
  const [mockMemo, setMockMemo] = useState<Memo | null>(() => (real ? null : findMemo(id)));

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: qk.boardItem(id) });
    void qc.invalidateQueries({ queryKey: qk.timeline(id) });
    if (code) void qc.invalidateQueries({ queryKey: qk.board(code) });
  };

  if (!real) {
    const m = mockMemo;
    const data: MemoScreenData = {
      memo: m,
      stockName: m ? mockUpdateStocks.find((s) => s.stock_code === m.stock_code)?.name ?? mockDetailStockName : mockDetailStockName,
      versions: m ? versionsOf(m.id) : [],
      feed: m ? feedOf(m.id) : [],
      trackItems: m ? mockTrackItems[m.id] ?? [] : [],
      lastChecked: mockLastChecked,
    };
    return { real, data, loading: false, setMockMemo, ops: null };
  }

  const detail = timeline.data ? detailFrom(timeline.data) : null;
  const raw = timeline.data as (typeof timeline.data & { tracking_items?: { last_checked_at?: string | null }[] }) | undefined;
  const data: MemoScreenData = {
    memo,
    stockName: stock.data?.name ?? code,
    versions: detail?.versions ?? [],
    feed: detail?.feed ?? [],
    trackItems: detail?.trackItems ?? [],
    lastChecked: lastCheckedText(raw?.tracking_items),
  };
  const ops = {
    save: (p: { title: string; body: string }) => update.mutate({ id, patch: p }),
    color: (color: MemoColor) => update.mutate({ id, patch: { color } }),
    pin: (pinned: boolean) => update.mutate({ id, patch: { pinned } }),
    remove: () => del.mutateAsync(id),
    aiOff: () => api.setAiLink(id, false).finally(refresh),
    async aiOn(): Promise<ConnectResult> {
      try {
        return connectResult((await api.setAiLink(id, true)).analysis);
      } catch {
        return { state: 'error', items: [] };
      } finally {
        refresh();
      }
    },
  };
  return { real, data, loading: item.isLoading || timeline.isLoading, setMockMemo, ops };
}
