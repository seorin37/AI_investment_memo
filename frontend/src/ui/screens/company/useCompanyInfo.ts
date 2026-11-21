import { useCandles, useFinancials, useMyStocks, useProfile, useQuote } from '@/hooks/queries';
import type { Candle, ChartRange, Financials, Quote, StockProfile } from '@/types/models';
import type { StockHeadProps } from '@/ui/shared/StockHead.types';
import type { CompanyInfoProps } from './CompanyInfo.types';

/**
 * 기업정보 화면 데이터 (2026-11-21): mockCompanyByCode 대신 실제 API 4개를 화면 props 모양으로 묶는다.
 * - GET /stocks/{code}/profile · /quote · /candles(1W·1M·3M·1Y) · /financials (mock 모드에서는 같은 함수의 mock 응답)
 * - 1Y 는 API 가 일봉 250개라 주봉으로 묶는다 (화면은 1Y 주봉)
 * - 재무가 없으면(financials.preparing) 화면의 '준비 중'
 */
export type CompanyData = Omit<CompanyInfoProps, 'onBack' | 'onMore' | 'onChangeTab' | 'onNudge'>;

const PALETTE = ['#3D73F0', '#EA002C', '#00A86B', '#F59E0B', '#7046F5', '#0EA5E9', '#E11D48', '#14B8A6'];

/** 로고가 정해지지 않은 종목: 이름 첫 글자 + 종목코드로 고른 색 */
export function fallbackLogo(code: string, name: string): Pick<StockHeadProps, 'logo' | 'logo_bg'> {
  const n = [...code].reduce((a, c) => a + c.charCodeAt(0), 0);
  return { logo: (name || code).slice(0, 1), logo_bg: PALETTE[n % PALETTE.length] };
}

/** 일봉 → 주봉 (월요일 시작 주). 날짜는 그 주의 마지막 거래일 */
export function weekly(days: Candle[]): Candle[] {
  const out: Candle[] = [];
  let key = '';
  for (const d of days) {
    const t = new Date(`${d.date}T00:00:00Z`);
    const monday = new Date(t.getTime() - ((t.getUTCDay() + 6) % 7) * 86400000).toISOString().slice(0, 10);
    const last = out[out.length - 1];
    if (last && key === monday) {
      last.high = Math.max(last.high, d.high);
      last.low = Math.min(last.low, d.low);
      last.close = d.close;
      last.volume += d.volume;
      last.date = d.date;
    } else {
      key = monday;
      out.push({ ...d });
    }
  }
  return out;
}

const mmdd = (iso: string) => `${iso.slice(5, 7)}.${iso.slice(8, 10)}`;

export function toCompanyData(code: string, profile: StockProfile, quote: Quote | undefined, fin: Financials | undefined,
                              candles: Record<ChartRange, Candle[]>, status: StockHeadProps['status']): CompanyData {
  const last = candles['1M'][candles['1M'].length - 1];
  const price = quote?.price ?? last?.close ?? profile.prev_close;
  const stock: StockHeadProps = {
    stock_code: code,
    name: profile.name,
    market: profile.market,
    status,
    ...fallbackLogo(code, profile.name),
    price,
    change: quote?.change ?? price - profile.prev_close,
    change_pct: quote?.change_pct ?? (profile.prev_close ? ((price - profile.prev_close) / profile.prev_close) * 100 : 0),
    as_of: mmdd(quote?.as_of ?? last?.date ?? ''),
    closes: quote?.spark?.length ? quote.spark : candles['1M'].map((c) => c.close),
  };
  const lastQ = fin?.quarters[fin.quarters.length - 1];
  return {
    stock,
    profile,
    quote_as_of: quote?.as_of ?? last?.date ?? '',
    candles: { ...candles, '1Y': weekly(candles['1Y']) },
    quarters: (fin?.quarters ?? []).map(({ period_end: _end, ...q }) => q),
    health: fin?.health ?? { debt: null, current: null, quick: null, interest: null, reserve: null },
    health_as_of: fin?.health_as_of ?? lastQ?.period_end ?? '',
    financial: fin?.financial ?? false,
    preparing: !fin || fin.preparing,
  };
}

/** 기업정보 데이터. 모두 받기 전에는 data=null. 시세·차트가 없으면(주가 데이터 없음) error */
export function useCompanyInfo(code: string) {
  const profile = useProfile(code);
  const quote = useQuote(code);
  const fin = useFinancials(code);
  const c1w = useCandles(code, '1W');
  const c1m = useCandles(code, '1M');
  const c3m = useCandles(code, '3M');
  const c1y = useCandles(code, '1Y');
  const mine = useMyStocks();
  const pending = [profile, c1w, c1m, c3m, c1y].some((q) => q.isLoading) || fin.isLoading;
  if (pending) return { data: null, loading: true, error: null } as const;
  if (!profile.data || !c1m.data) return { data: null, loading: false, error: profile.error ?? c1m.error ?? new Error('no data') } as const;
  const status = mine.data?.find((s) => s.code === code)?.status ?? 'watching';
  const candles = { '1W': c1w.data ?? [], '1M': c1m.data, '3M': c3m.data ?? [], '1Y': c1y.data ?? [] };
  return { data: toCompanyData(code, profile.data, quote.data, fin.data, candles, status), loading: false, error: null } as const;
}
