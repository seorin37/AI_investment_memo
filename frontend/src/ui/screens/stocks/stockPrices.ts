import type { Quote } from '@/types/models';
import type { MyStock, StockCandidate } from './MyStocks.types';

/**
 * 내 종목 목록 · 종목 추가 후보에 시세 붙이기 (2026-11-21). 순수 함수 (테스트: tests/market-dates.test.mjs).
 * - 시세가 없는 종목은 price·change_pct = null (화면 '—')
 * - 목록 종목의 종가 날짜가 모두 같으면 as_of 한 줄 ('MM.DD 종가 기준'), 다르면 as_of_mixed = true 이고 줄마다 as_of
 * - 목록에 시세가 하나도 없으면 as_of = '' (화면 '시세 데이터가 아직 연결되지 않았어요')
 */
export const quoteDate = (q: Quote) => q.trade_date ?? q.as_of.slice(0, 10);

export function applyQuotes(stocks: MyStock[], universe: StockCandidate[], quotes: Quote[]) {
  const byCode = new Map(quotes.map((q) => [q.code, q]));
  const listDates = new Set(stocks.map((s) => byCode.get(s.stock_code)).filter((q): q is Quote => !!q).map(quoteDate));
  const mixed = listDates.size > 1;
  const as_of = [...listDates].sort().pop() ?? '';
  return {
    stocks: stocks.map((s): MyStock => {
      const q = byCode.get(s.stock_code);
      return { ...s, price: q ? q.price : null, change_pct: q ? q.change_pct : null, as_of: mixed && q ? quoteDate(q) : undefined };
    }),
    universe: universe.map((u): StockCandidate => {
      const q = byCode.get(u.stock_code);
      return { ...u, price: q ? q.price : null, change_pct: q ? q.change_pct : null };
    }),
    as_of,
    as_of_mixed: mixed,
  };
}
