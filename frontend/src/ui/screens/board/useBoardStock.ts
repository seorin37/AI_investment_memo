import { env } from '@/config/env';
import { useMyStocks, useQuote, useStock } from '@/hooks/queries';
import type { Quote, StockMaster, StockStatus } from '@/types/models';
import { fallbackLogo } from '@/ui/screens/company/useCompanyInfo';
import type { StockHeadProps } from '@/ui/shared/StockHead.types';

/**
 * 메모 보드 종목 머리 (2026-11-21, 기업정보 useCompanyInfo 와 같은 틀).
 * - 시세: useQuote(GET /stocks/{code}/quote, 원시 종가) · 이름·시장: useStock(GET /stocks/{code}) · 보유/관심: useMyStocks
 * - 로고가 정해지지 않은 종목은 fallbackLogo (기업정보와 같은 규칙)
 * - USE_MOCK=true 면 지금처럼 host 가 넘긴 mock 머리 그대로
 * - 실제 모드에서 시세가 없으면 priceNote(미연결 안내) — 숫자를 지어내지 않는다
 */
const mmdd = (iso: string) => `${iso.slice(5, 7)}.${iso.slice(8, 10)}`;

export const PRICE_NOT_CONNECTED = '이 종목의 시세 데이터는 아직 연결되지 않았어요';

export function toBoardStock(code: string, base: StockHeadProps, quote: Quote | undefined, master: StockMaster | undefined, status: StockStatus | undefined): StockHeadProps {
  const same = base.stock_code === code;
  const name = master?.name ?? (same ? base.name : code);
  const ident: StockHeadProps = same
    ? { ...base, name }
    : { ...base, stock_code: code, name, logo_ink: undefined, ...fallbackLogo(code, name) };
  const head: StockHeadProps = { ...ident, market: master?.market ?? ident.market, status: status ?? ident.status };
  if (!quote) return head;
  return {
    ...head,
    price: quote.price,
    change: quote.change,
    change_pct: quote.change_pct,
    as_of: mmdd(quote.trade_date ?? quote.as_of),
    closes: quote.spark,
  };
}

export function useBoardStock(code: string, base: StockHeadProps): { stock: StockHeadProps; priceNote?: string } {
  const real = !env.useMock;
  const quote = useQuote(code, real);
  const master = useStock(real ? code : '');
  const mine = useMyStocks();
  if (!real) return { stock: base };
  const status = mine.data?.find((s) => s.code === code)?.status;
  const stock = toBoardStock(code, base, quote.data, master.data, status);
  return quote.isError ? { stock, priceNote: PRICE_NOT_CONNECTED } : { stock };
}
