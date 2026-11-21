import { env } from '@/config/env';
import { useQuotes } from '@/hooks/queries';
import type { MyStock, StockCandidate } from './MyStocks.types';
import { applyQuotes } from './stockPrices';

/**
 * 내 종목 목록 · 종목 추가 후보의 가격 (2026-11-21, 기업정보 useCompanyInfo 와 같은 틀).
 * - GET /quotes?codes= 한 번으로 화면의 모든 종목 시세 (원시 종가). 받은 값은 종목별 useQuote 캐시에도 들어감
 * - 변환: applyQuotes (stockPrices.ts) — 종목 날짜가 다르면 줄마다 기준일
 * - USE_MOCK=true 면 지금처럼 mock 가격 그대로
 * 종목 구성·메모 수는 아직 mock (이번 단계는 가격만)
 */
export function useStockPrices(stocks: MyStock[], universe: StockCandidate[], mockAsOf: string) {
  const real = !env.useMock;
  const q = useQuotes([...stocks, ...universe].map((s) => s.stock_code), real);
  if (!real) return { stocks, universe, as_of: mockAsOf, as_of_mixed: false };
  return applyQuotes(stocks, universe, q.data?.quotes ?? []);
}
