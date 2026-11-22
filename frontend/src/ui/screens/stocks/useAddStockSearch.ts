import { useState } from 'react';
import { env } from '@/config/env';
import { usePopularStocks, useStockSearch } from '@/hooks/queries';
import type { StockMaster } from '@/types/models';
import { fallbackLogo } from '@/ui/screens/company/useCompanyInfo';
import { mockMyStocksData } from './MyStocks.mock';
import type { StockCandidate } from './MyStocks.types';

/** 종목 마스터 → 추가 후보 (분야는 서버에 없어 빈 값 → 추가 창이 칩을 숨김). AI 연결은 모든 종목 가능 */
export function toCandidate(s: StockMaster): StockCandidate {
  return { stock_code: s.code, name: s.name, ...fallbackLogo(s.code, s.name), market: s.market, sector: '', ai_ready: true, price: null, change_pct: null };
}

/**
 * 종목 추가 창(웹 내 종목 · 사이드바 + · 앱 내 종목 시트) 후보 (2026-11-22).
 * - 실제 모드: 검색어가 있으면 GET /stocks/search (코스피 전체 · 온보딩 웹 검색과 같은 useStockSearch), 없으면 GET /stocks/popular.
 *   창은 remote=true 면 받은 목록을 다시 거르지 않고, 검색어가 바뀌면 onQueryChange 로 알려 준다. mock 후보 15개는 쓰지 않음
 * - mock 모드: 지금처럼 MyStocks.mock 후보를 창 안에서 거름
 */
export function useAddStockSearch() {
  const real = !env.useMock;
  const [query, setQuery] = useState('');
  const q = query.trim();
  const popular = usePopularStocks(12, real);
  const search = useStockSearch(real ? q : '');
  if (!real) {
    return { remote: false, universe: mockMyStocksData.universe, popular: mockMyStocksData.popular, onQueryChange: undefined, searching: false };
  }
  const pop = (popular.data ?? []).map(toCandidate);
  const universe = q ? (search.data ?? []).map(toCandidate) : pop;
  return { remote: true, universe, popular: pop.map((s) => s.stock_code), onQueryChange: setQuery, searching: !!q && search.isFetching };
}
