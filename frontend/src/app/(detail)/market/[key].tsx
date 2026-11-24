import React from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { TopBar } from '@/ui/layout/app/TopBar';
import { AppMarketDetail } from '@/ui/screens/home/app/MarketDetail';
import { useHomeMarket } from '@/ui/screens/home/useHomeMarket';

/** 앱 지수 자세히 = UI v2 (ui/screens/home/app/MarketDetail · ②) — 홈 시장 숫자를 누르면 밀려 들어옴. 데이터: useHomeMarket (실제 모드 GET /market/overview · mock 모드 Home.mock) */
export default function MarketDetailScreen() {
  const router = useRouter();
  const notice = useMockNotice();
  const { key } = useLocalSearchParams<{ key: string }>();
  const { market, days } = useHomeMarket();
  const q = market?.find((m) => m.key === key) ?? market?.[0];
  if (!q || !days.length) return null;
  return <AppMarketDetail index={q} days={days} header={<TopBar preset="market" title={q.name} onBack={() => router.back()} />} onNudge={() => notice('투자 실험실')} />;
}
