import React, { useState } from 'react';
import { useRouter } from 'expo-router';
import { mockMyStocksData } from '@/ui/screens/stocks/MyStocks.mock';
import type { MyStock } from '@/ui/screens/stocks/MyStocks.types';
import { useStockPrices } from '@/ui/screens/stocks/useStockPrices';
import { WebMyStocks } from '@/ui/screens/stocks/web/MyStocks';

/**
 * 웹 내 종목 = UI v2 (ui/screens/stocks/web · ⑥). 앱은 index.native.tsx.
 * mock: MyStocks.mock — 추가·옮기기·빼기는 이 화면 안에서만 (사이드바 종목은 셸에서 따로).
 */
export default function MyStocksPage() {
  const router = useRouter();
  const [stocks, setStocks] = useState<MyStock[]>(mockMyStocksData.stocks);
  /* 가격: 실제 모드면 GET /quotes 한 번 (2026-11-21), mock 모드면 mock 가격 */
  const priced = useStockPrices(stocks, mockMyStocksData.universe, mockMyStocksData.as_of);
  return (
      <WebMyStocks
        {...mockMyStocksData}
        {...priced}
        onOpenStock={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code } })}
        onOpenCompany={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code, tab: 'info' } })}
        onAdd={(code, hold) => {
          const u = mockMyStocksData.universe.find((s) => s.stock_code === code);
          if (!u) return;
          setStocks((all) => [...all, { stock_code: u.stock_code, name: u.name, logo: u.logo, logo_bg: u.logo_bg, logo_ink: u.logo_ink, market: u.market, status: hold, memo_count: 0, ai_count: 0, new_count: 0, price: u.price, change_pct: u.change_pct, ai_ready: u.ai_ready }]);
        }}
        onMove={(codes, hold) => setStocks((all) => all.map((s) => (codes.includes(s.stock_code) ? { ...s, status: hold } : s)))}
        onRemove={(codes) => setStocks((all) => all.filter((s) => !codes.includes(s.stock_code)))}
        onRestore={setStocks}
        onReorder={(codes) => setStocks((all) => codes.map((c) => all.find((s) => s.stock_code === c)).filter((s): s is MyStock => !!s))}
        onWriteMemo={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code } })}
      />
  );
}
