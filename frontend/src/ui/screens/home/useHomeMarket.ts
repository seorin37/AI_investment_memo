import { env } from '@/config/env';
import { useMarketOverview } from '@/hooks/queries';
import type { MarketOverview } from '@/types/models';
import { mockHomeData } from './Home.mock';
import type { MarketIndex, MarketKey } from './Home.types';

/**
 * 홈 시장 지수 데이터 (2026-11-21, 기업정보 useCompanyInfo 와 같은 틀: hook 하나 + 변환 함수 하나).
 * - GET /market/overview → 홈 MarketIndex[] + days(지수 날짜 축 · 뉴스 기준일)
 * - USE_MOCK=true 면 지금처럼 Home.mock 값 (API 를 부르지 않음)
 * - 실제 모드: 받기 전에는 빈 배열, 실패하거나 지수가 하나도 없으면 null → 위젯의 '불러오지 못함' 안내
 */
const KEY: Record<MarketOverview['indices'][number]['key'], MarketKey> = { KOSPI: 'kospi', KOSDAQ: 'kosdaq', USDKRW: 'usd' };
const NAME: Record<MarketKey, string> = { kospi: '코스피', kosdaq: '코스닥', usd: '원/달러' };
const SUB: Record<MarketKey, string> = { kospi: 'KOSPI 지수', kosdaq: 'KOSDAQ 지수', usd: '원/달러 환율' };

/** 날짜 축(days)에 맞춰 값을 고른다: 그 날 값이 없으면 그 전 가장 가까운 관측값 (원/달러는 관측일이 거래일과 다를 수 있음) */
export function alignTo(days: string[], dates: string[], values: number[]): number[] {
  const out: number[] = [];
  let j = 0;
  let last = values[0];
  for (const d of days) {
    while (j < dates.length && dates[j] <= d) last = values[j++];
    out.push(last);
  }
  return out;
}

export function toHomeMarket(o: MarketOverview): { market: MarketIndex[]; days: string[] } {
  const base = o.indices.find((i) => i.key === 'KOSPI') ?? o.indices[0];
  const days = base?.dates ?? [];
  const market = o.indices.map((i): MarketIndex => {
    const key = KEY[i.key];
    const year = i.series['1Y'];
    const same = !!i.dates && i.dates.length === days.length && i.dates[i.dates.length - 1] === days[days.length - 1];
    return {
      key,
      name: NAME[key],
      sub: SUB[key],
      value: i.value,
      change: i.change,
      pct: i.change_pct,
      as_of: i.trade_date ?? o.as_of.slice(0, 10),
      closes: same || !i.dates || !days.length ? year : alignTo(days, i.dates, year),
    };
  });
  return { market, days };
}

export function useHomeMarket() {
  const real = !env.useMock;
  const q = useMarketOverview(real);
  if (!real) return { market: mockHomeData.market, days: mockHomeData.days, retry: () => {} };
  const retry = () => void q.refetch();
  if (q.isLoading) return { market: [] as MarketIndex[], days: [] as string[], retry };
  if (!q.data || !q.data.indices.length) return { market: null, days: [] as string[], retry };
  return { ...toHomeMarket(q.data), retry };
}
