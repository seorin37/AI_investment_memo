import { useState } from 'react';
import { env } from '@/config/env';
import { useAddStock, useMyStocks, useRemoveStock, useReorderStocks, useUpdateStock } from '@/hooks/queries';
import type { MyStock } from '@/types/models';
import { fallbackLogo } from '@/ui/screens/company/useCompanyInfo';
import { mockSideStocks } from './WebShell.mock';
import type { SideStock } from './WebShell.types';

/**
 * 웹 사이드바 내 종목 (2026-11-22).
 * - USE_MOCK=true: 지금처럼 셸 안 상태(mockSideStocks)
 * - 실제 모드: 목록 = GET /stocks (서버 순서, 0021 position). 셸은 지금처럼 setSideStocks(바뀐 목록)를 부르고,
 *   이 hook 이 바뀐 점을 API 로 보낸다 — 순서 PUT /stocks/order · 보유/관심 PATCH · 빼기 DELETE · 추가(빼기 되돌리기 포함) POST
 */
export function toSideStock(s: MyStock): SideStock {
  return { stock_code: s.code, name: s.name, status: s.status, ...fallbackLogo(s.code, s.name) };
}

type Next = SideStock[] | ((all: SideStock[]) => SideStock[]);

export function useSideStocks(): [SideStock[], (next: Next) => void] {
  const real = !env.useMock;
  const [mock, setMock] = useState<SideStock[]>(mockSideStocks);
  const mine = useMyStocks();
  const reorder = useReorderStocks();
  const add = useAddStock();
  const update = useUpdateStock();
  const remove = useRemoveStock();
  if (!real) return [mock, setMock];

  const cur = (mine.data ?? []).map(toSideStock);
  const set = (next: Next) => {
    const to = typeof next === 'function' ? next(cur) : next;
    const before = new Map(cur.map((s) => [s.stock_code, s]));
    const after = new Map(to.map((s) => [s.stock_code, s]));
    for (const s of cur) if (!after.has(s.stock_code)) remove.mutate(s.stock_code);
    for (const s of to) {
      const was = before.get(s.stock_code);
      if (!was) add.mutate({ code: s.stock_code, status: s.status });
      else if (was.status !== s.status) update.mutate({ code: s.stock_code, patch: { status: s.status } });
    }
    const kept = to.filter((s) => before.has(s.stock_code)).map((s) => s.stock_code);
    const old = cur.filter((s) => after.has(s.stock_code)).map((s) => s.stock_code);
    if (kept.join() !== old.join()) reorder.mutate(to.map((s) => s.stock_code));
  };
  return [cur, set];
}
