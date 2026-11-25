import React, { useCallback } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import { ErrorState, Loading } from '@/components/ui/primitives';
import { useUI } from '@/store/ui';
import { TopBar } from '@/ui/layout/app/TopBar';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';
import { AppMyStocks } from '@/ui/screens/stocks/app/MyStocks';
import { mockMyStocksData } from '@/ui/screens/stocks/MyStocks.mock';
import type { MyStock } from '@/ui/screens/stocks/MyStocks.types';
import { useMyStocksData } from '@/ui/screens/stocks/useMyStocksData';
import { useStockPrices } from '@/ui/screens/stocks/useStockPrices';

/**
 * 앱 내 종목 탭 = UI v2 (ui/screens/stocks/app · ⑥). 웹은 index.tsx.
 * 데이터: useMyStocksData — 실제 모드면 GET /stocks(메모 수 · AI 연결 수 포함) + 추가 · 옮기기 · 빼기 · 순서를 사이드바와 같은 API 로,
 * mock 모드면 지금처럼 MyStocks.mock 과 화면 안 상태. 종목 → 메모 보드(③) / 기업정보(⑤).
 */
export default function MyStocksTab() {
  const router = useRouter();
  const { profile: { name: myName, photoUrl } } = useMyProfile();
  const setTabBarHidden = useUI((s) => s.setTabBarHidden);
  const data = useMyStocksData();
  /* 가격: 실제 모드면 GET /quotes 한 번 (2026-11-21), mock 모드면 mock 가격 */
  const priced = useStockPrices(data.stocks, data.universe, mockMyStocksData.as_of);
  useFocusEffect(useCallback(() => () => setTabBarHidden(false), [setTabBarHidden]));
  const onSelectionChange = useCallback((n: number) => setTabBarHidden(n > 0), [setTabBarHidden]);
  if (data.loading) return <Loading height={400} />;
  if (data.failed) return <ErrorState message="내 종목을 불러오지 못했어요" onRetry={data.retry} />;
  return (
    <AppMyStocks
      {...mockMyStocksData}
      {...priced}
      popular={data.popular}
      add_remote={data.add_remote}
      onAddQuery={data.onAddQuery}
      header={({ onSearch }) => (
        <TopBar
          preset="stocks"
          title="내 종목"
          actions={[
            { icon: 'search', label: '종목 찾기', onPress: onSearch },
            { icon: 'bell', label: '알림', onPress: () => router.push('/my-inbox') },
          ]}
          avatar={{ name: myName, photoUrl, onPress: () => router.push('/my') }}
        />
      )}
      onSelectionChange={onSelectionChange}
      onOpenStock={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
      onAdd={(code, hold) => {
        const u = data.universe.find((s) => s.stock_code === code);
        if (!u) return;
        data.setStocks((all) => [...all, { stock_code: u.stock_code, name: u.name, logo: u.logo, logo_bg: u.logo_bg, logo_ink: u.logo_ink, market: u.market, status: hold, memo_count: 0, ai_count: 0, new_count: 0, price: u.price, change_pct: u.change_pct, ai_ready: u.ai_ready }]);
      }}
      onMove={(codes, hold) => data.setStocks((all) => all.map((s) => (codes.includes(s.stock_code) ? { ...s, status: hold } : s)))}
      onRemove={(codes) => data.setStocks((all) => all.filter((s) => !codes.includes(s.stock_code)))}
      onRestore={data.setStocks}
      onReorder={(codes) => data.setStocks((all) => codes.map((c) => all.find((s) => s.stock_code === c)).filter((s): s is MyStock => !!s))}
      onWriteMemo={(code) => router.push({ pathname: '/memo/new', params: { code, name: data.universe.find((s) => s.stock_code === code)?.name ?? data.stocks.find((s) => s.stock_code === code)?.name ?? '', first_line: '' } })}
    />
  );
}
