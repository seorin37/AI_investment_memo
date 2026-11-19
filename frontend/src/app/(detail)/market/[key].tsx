import React from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { TopBar } from '@/ui/layout/app/TopBar';
import { AppMarketDetail } from '@/ui/screens/home/app/MarketDetail';
import { mockHomeData } from '@/ui/screens/home/Home.mock';

/** 앱 지수 자세히 = UI v2 (ui/screens/home/app/MarketDetail · ②) — 홈 시장 숫자를 누르면 밀려 들어옴. mock: Home.mock */
export default function MarketDetailScreen() {
  const router = useRouter();
  const notice = useMockNotice();
  const { key } = useLocalSearchParams<{ key: string }>();
  const q = mockHomeData.market?.find((m) => m.key === key) ?? mockHomeData.market?.[0];
  if (!q) return null;
  return <AppMarketDetail index={q} days={mockHomeData.days} header={<TopBar preset="market" title={q.name} onBack={() => router.back()} />} onNudge={() => notice('투자 실험실')} />;
}
