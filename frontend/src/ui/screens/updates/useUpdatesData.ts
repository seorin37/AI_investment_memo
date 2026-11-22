import { useState } from 'react';
import { env } from '@/config/env';
import { useMarkAiUpdateRead, useMyStocks, useUpdates } from '@/hooks/queries';
import type { AiUpdate, MyStock } from '@/types/models';
import { fallbackLogo } from '@/ui/screens/company/useCompanyInfo';
import { toFeedItem } from '@/ui/screens/memo/toFeedItem';
import { mockUpdateItems, mockUpdatesNow, mockUpdateStocks } from './Updates.mock';
import type { UpdateItem, UpdateStock } from './Updates.types';

/**
 * 업데이트 화면(⑥) 데이터 (2026-11-22, 기업정보 useCompanyInfo 와 같은 틀).
 * - 종목: useMyStocks (GET /stocks, 내 종목 순서) · 소식: useUpdates (GET /updates, 내 종목 최근 30일 카드)
 * - 종목 칩으로 거르는 건 화면이 한다 → 늘 전체를 받음
 * - 읽음: POST /ai-updates/{id}/read. '안 읽음으로'는 서버 API 가 없어 이 화면 안에서만 (전수 검사 결정 13)
 * - USE_MOCK=true 면 지금처럼 Updates.mock
 */
export function toUpdateStock(s: MyStock): UpdateStock {
  return { stock_code: s.code, name: s.name, market: s.market, status: s.status, ai_ready: true, ...fallbackLogo(s.code, s.name) };
}

export function toUpdateItem(u: AiUpdate): UpdateItem {
  return { ...toFeedItem(u), stock_code: u.stock_code, memo_id: u.memo_id, memo_title: u.memo_title, memo_color: u.memo_color ?? 'yellow' };
}

export function useUpdatesData() {
  const real = !env.useMock;
  const stocks = useMyStocks();
  const updates = useUpdates();
  const markRead = useMarkAiUpdateRead();
  /** 화면에서 바꾼 읽음 상태 (id → 읽음). 서버 값보다 먼저 */
  const [readOverride, setReadOverride] = useState<Record<string, boolean>>({});
  const [mockItems, setMockItems] = useState(mockUpdateItems);

  const onMarkRead = (ids: string[], read: boolean) => {
    if (!real) return setMockItems((all) => all.map((u) => (ids.includes(u.id) ? { ...u, unread: !read } : u)));
    setReadOverride((o) => ({ ...o, ...Object.fromEntries(ids.map((id) => [id, read])) }));
    if (read) ids.forEach((id) => markRead.mutate(id));
  };

  if (!real) return { stocks: mockUpdateStocks, items: mockItems, now: mockUpdatesNow, loading: false, error: null, onMarkRead };

  // 계약 타입은 MarketUpdate[] 지만 실제 서버는 AiUpdate(메모·요약·근거 포함)를 준다 (be/app/updates/service.py market_updates)
  const items = ((updates.data ?? []) as AiUpdate[]).map(toUpdateItem).map((u) => (u.id in readOverride ? { ...u, unread: !readOverride[u.id] } : u));
  return {
    stocks: (stocks.data ?? []).map(toUpdateStock),
    items,
    now: new Date().toISOString(),
    loading: stocks.isLoading || updates.isLoading,
    error: stocks.error ?? updates.error ?? null,
    onMarkRead,
  };
}
