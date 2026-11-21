import React, { useCallback, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { useUI } from '@/store/ui';
import { TopBar } from '@/ui/layout/app/TopBar';
import { AppMyStocks } from '@/ui/screens/stocks/app/MyStocks';
import { mockMyStocksData } from '@/ui/screens/stocks/MyStocks.mock';
import type { MyStock } from '@/ui/screens/stocks/MyStocks.types';
import { useStockPrices } from '@/ui/screens/stocks/useStockPrices';

/**
 * 앱 내 종목 탭 = UI v2 (ui/screens/stocks/app · ⑥). 웹은 index.tsx.
 * mock: MyStocks.mock — 추가·옮기기·빼기·순서는 이 화면 안에서만. 종목 → 메모 보드(③) / 기업정보(⑤).
 */
export default function MyStocksTab() {
  const router = useRouter();
  const notice = useMockNotice();
  const setTabBarHidden = useUI((s) => s.setTabBarHidden);
  const [stocks, setStocks] = useState<MyStock[]>(mockMyStocksData.stocks);
  /* 가격: 실제 모드면 GET /quotes 한 번 (2026-11-21), mock 모드면 mock 가격 */
  const priced = useStockPrices(stocks, mockMyStocksData.universe, mockMyStocksData.as_of);
  useFocusEffect(useCallback(() => () => setTabBarHidden(false), [setTabBarHidden]));
  const onSelectionChange = useCallback((n: number) => setTabBarHidden(n > 0), [setTabBarHidden]);
  return (
    <AppMyStocks
      {...mockMyStocksData}
      {...priced}
      header={({ onSearch }) => (
        <TopBar
          preset="stocks"
          title="내 종목"
          actions={[
            { icon: 'search', label: '종목 찾기', onPress: onSearch },
            { icon: 'bell', label: '알림', onPress: () => notice('알림') },
          ]}
          avatar={{ name: '김나라', onPress: () => router.push('/my') }}
        />
      )}
      onSelectionChange={onSelectionChange}
      onOpenStock={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
      onAdd={(code, hold) => {
        const u = mockMyStocksData.universe.find((s) => s.stock_code === code);
        if (!u) return;
        setStocks((all) => [...all, { stock_code: u.stock_code, name: u.name, logo: u.logo, logo_bg: u.logo_bg, logo_ink: u.logo_ink, market: u.market, status: hold, memo_count: 0, ai_count: 0, new_count: 0, price: u.price, change_pct: u.change_pct, ai_ready: u.ai_ready }]);
      }}
      onMove={(codes, hold) => setStocks((all) => all.map((s) => (codes.includes(s.stock_code) ? { ...s, status: hold } : s)))}
      onRemove={(codes) => setStocks((all) => all.filter((s) => !codes.includes(s.stock_code)))}
      onRestore={setStocks}
      onReorder={(codes) => setStocks((all) => codes.map((c) => all.find((s) => s.stock_code === c)).filter((s): s is MyStock => !!s))}
      onWriteMemo={(code) => router.push({ pathname: '/memo/new', params: { code, name: mockMyStocksData.universe.find((s) => s.stock_code === code)?.name ?? '', first_line: '' } })}
    />
  );
}
