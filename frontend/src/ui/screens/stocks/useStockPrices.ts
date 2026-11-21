import { env } from '@/config/env';
import { useQuotes } from '@/hooks/queries';
import type { Quote } from '@/types/models';
import type { MyStock, StockCandidate } from './MyStocks.types';

/**
 * 내 종목 목록 · 종목 추가 후보의 가격 (2026-11-21, 기업정보 useCompanyInfo 와 같은 틀).
 * - GET /quotes?codes= 한 번으로 화면의 모든 종목 시세 (원시 종가). 받은 값은 종목별 useQuote 캐시에도 들어감
 * - USE_MOCK=true 면 지금처럼 mock 가격 그대로
 * - 실제 모드: 시세가 없는 종목은 price·change_pct = null(화면 '—'), 하나도 없으면 as_of = '' (화면 '시세 데이터가 아직 연결되지 않았어요')
 * 종목 구성·메모 수는 아직 mock (이번 단계는 가격만)
 */
type Priced = { stock_code: string; price: number | null; change_pct: number | null };

export function withQuotes<T extends Priced>(rows: T[], byCode: Map<string, Quote>): T[] {
  return rows.map((r) => {
    const q = byCode.get(r.stock_code);
    return { ...r, price: q ? q.price : null, change_pct: q ? q.change_pct : null };
  });
}

/** 받은 시세 중 가장 늦은 거래일 (YYYY-MM-DD) */
export function latestTradeDate(quotes: Quote[]): string {
  return quotes.reduce((d, q) => {
    const t = q.trade_date ?? q.as_of.slice(0, 10);
    return t > d ? t : d;
  }, '');
}

export function useStockPrices(stocks: MyStock[], universe: StockCandidate[], mockAsOf: string) {
  const real = !env.useMock;
  const q = useQuotes([...stocks, ...universe].map((s) => s.stock_code), real);
  if (!real) return { stocks, universe, as_of: mockAsOf };
  const quotes = q.data?.quotes ?? [];
  const byCode = new Map(quotes.map((x) => [x.code, x]));
  return { stocks: withQuotes(stocks, byCode), universe: withQuotes(universe, byCode), as_of: latestTradeDate(quotes) };
}
