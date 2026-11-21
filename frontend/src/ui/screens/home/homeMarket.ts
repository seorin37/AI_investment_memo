import type { MarketOverview } from '@/types/models';
import type { MarketIndex, MarketKey } from './Home.types';

/**
 * GET /market/overview → 홈 MarketIndex[] (2026-11-21). 순수 함수 (DB·React 없이 테스트: tests/market-dates.test.mjs).
 * - 지표마다 자기 날짜(dates)·값(series['1Y'])·기준일(trade_date)을 그대로 쓴다. 다른 지표 축에 맞추거나 없는 날 값을 채우지 않는다
 * - days = 코스피 날짜 (뉴스 위젯 기준일에만 씀)
 */
const KEY: Record<MarketOverview['indices'][number]['key'], MarketKey> = { KOSPI: 'kospi', KOSDAQ: 'kosdaq', USDKRW: 'usd' };
const NAME: Record<MarketKey, string> = { kospi: '코스피', kosdaq: '코스닥', usd: '원/달러' };
const SUB: Record<MarketKey, string> = { kospi: 'KOSPI 지수', kosdaq: 'KOSDAQ 지수', usd: '원/달러 환율' };

export function toHomeMarket(o: MarketOverview): { market: MarketIndex[]; days: string[] } {
  const market = o.indices.map((i): MarketIndex => {
    const key = KEY[i.key];
    const closes = i.series['1Y'];
    /* 날짜가 값과 짝이 맞을 때만 쓴다 (짝이 안 맞으면 날짜를 지어내지 않고 비움) */
    const dates = i.dates && i.dates.length === closes.length ? i.dates : [];
    return {
      key,
      name: NAME[key],
      sub: SUB[key],
      value: i.value,
      change: i.change,
      pct: i.change_pct,
      as_of: i.trade_date ?? dates[dates.length - 1] ?? o.as_of.slice(0, 10),
      closes,
      dates,
    };
  });
  const base = market.find((m) => m.key === 'kospi') ?? market[0];
  return { market, days: base?.dates ?? [] };
}
