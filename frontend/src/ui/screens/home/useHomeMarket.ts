import { env } from '@/config/env';
import { useMarketOverview } from '@/hooks/queries';
import { mockHomeData } from './Home.mock';
import type { MarketIndex } from './Home.types';
import { toHomeMarket } from './homeMarket';

/**
 * 홈 시장 지수 데이터 (2026-11-21, 기업정보 useCompanyInfo 와 같은 틀: hook 하나 + 변환 함수 하나).
 * - GET /market/overview → toHomeMarket (homeMarket.ts): 지표마다 자기 날짜 시리즈
 * - USE_MOCK=true 면 지금처럼 Home.mock 값 (API 를 부르지 않음)
 * - 실제 모드: 받기 전에는 빈 배열, 실패하거나 지수가 하나도 없으면 null → 위젯의 '불러오지 못함' 안내
 */
export function useHomeMarket() {
  const real = !env.useMock;
  const q = useMarketOverview(real);
  if (!real) return { market: mockHomeData.market, days: mockHomeData.days, retry: () => {} };
  const retry = () => void q.refetch();
  if (q.isLoading) return { market: [] as MarketIndex[], days: [] as string[], retry };
  if (!q.data || !q.data.indices.length) return { market: null, days: [] as string[], retry };
  return { ...toHomeMarket(q.data), retry };
}
