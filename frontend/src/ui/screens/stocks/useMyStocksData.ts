import { useState } from 'react';
import { env } from '@/config/env';
import { useMyStocks, usePopularStocks } from '@/hooks/queries';
import type { MyStock as ApiMyStock, StockMaster } from '@/types/models';
import { fallbackLogo } from '@/ui/screens/company/useCompanyInfo';
import { useSideStocks } from '@/ui/layout/web/useSideStocks';
import type { SideStock } from '@/ui/layout/web/WebShell.types';
import { mockMyStocksData } from './MyStocks.mock';
import type { MyStock, StockCandidate } from './MyStocks.types';

/** GET /stocks 한 줄 → 화면 줄 (가격은 useStockPrices 가 채움). AI 연결은 모든 종목 가능(ai_ready) */
export function toScreenStock(s: ApiMyStock): MyStock {
  return {
    stock_code: s.code,
    name: s.name,
    ...fallbackLogo(s.code, s.name),
    market: s.market,
    status: s.status,
    memo_count: s.memo_count ?? 0,
    ai_count: s.ai_count ?? 0,
    new_count: s.unread_updates,
    price: null,
    change_pct: null,
    ai_ready: true,
  };
}

/** 많이 찾는 종목 → 추가 후보 (mock 후보에 있으면 그 분야 칩을, 없으면 시장 이름) */
function toCandidate(s: StockMaster): StockCandidate {
  return { stock_code: s.code, name: s.name, ...fallbackLogo(s.code, s.name), market: s.market, sector: s.market, ai_ready: true, price: null, change_pct: null };
}

/**
 * 내 종목 화면 데이터 (2026-11-22, 웹 · 앱 같이).
 * - mock 모드: 지금처럼 MyStocks.mock + 화면 안 상태
 * - 실제 모드: 목록 = GET /stocks (서버 순서 = position, 메모 수 · AI 연결 수 · 안 읽은 소식 포함).
 *   바뀐 목록을 setStocks 로 주면 사이드바와 같은 useSideStocks 가 추가 POST · 보유↔관심 PATCH · 빼기 DELETE · 순서 PUT 으로 보낸다
 *   (같은 캐시 qk.stocks 를 무효화 → 사이드바 · 이 화면이 함께 갱신)
 * - 추가 후보: 많이 찾는 종목(GET /stocks/popular) + 지금 mock 후보(실제 종목코드). 추가 창 검색은 이 목록 안에서만 (창이 로컬 검색)
 */
export function useMyStocksData() {
  const real = !env.useMock;
  const [mock, setMock] = useState<MyStock[]>(mockMyStocksData.stocks);
  const mine = useMyStocks();
  const popular = usePopularStocks(12, real);
  const [, setSide] = useSideStocks();

  if (!real) {
    return { stocks: mock, setStocks: setMock, universe: mockMyStocksData.universe, popular: mockMyStocksData.popular, loading: false, failed: false, retry: () => {} };
  }

  const stocks = (mine.data ?? []).map(toScreenStock);
  const setStocks = (next: MyStock[] | ((all: MyStock[]) => MyStock[])) => {
    const to = typeof next === 'function' ? next(stocks) : next;
    setSide(to.map((s): SideStock => ({ stock_code: s.stock_code, name: s.name, status: s.status, logo: s.logo, logo_bg: s.logo_bg, logo_ink: s.logo_ink })));
  };
  const pop = popular.data ?? [];
  const seen = new Set<string>();
  const universe = [...pop.map(toCandidate), ...mockMyStocksData.universe].filter((u) => !seen.has(u.stock_code) && !!seen.add(u.stock_code))
    .map((u) => mockMyStocksData.universe.find((m) => m.stock_code === u.stock_code) ?? u);
  return {
    stocks,
    setStocks,
    universe,
    popular: pop.length ? pop.slice(0, 5).map((s) => s.code) : mockMyStocksData.popular,
    loading: mine.isPending,
    failed: mine.isError && !mine.data,
    retry: () => void mine.refetch(),
  };
}
