import React from 'react';
import { useRouter } from 'expo-router';
import { ErrorState, Loading } from '@/components/ui/primitives';
import { mockMyStocksData } from '@/ui/screens/stocks/MyStocks.mock';
import type { MyStock } from '@/ui/screens/stocks/MyStocks.types';
import { useMyStocksData } from '@/ui/screens/stocks/useMyStocksData';
import { useStockPrices } from '@/ui/screens/stocks/useStockPrices';
import { WebMyStocks } from '@/ui/screens/stocks/web/MyStocks';

/**
 * 웹 내 종목 = UI v2 (ui/screens/stocks/web · ⑥). 앱은 index.native.tsx.
 * 데이터: useMyStocksData — 실제 모드면 GET /stocks(메모 수 · AI 연결 수 포함) + 추가 · 옮기기 · 빼기 · 순서를 사이드바와 같은 API 로,
 * mock 모드면 지금처럼 MyStocks.mock 과 화면 안 상태. 가격은 useStockPrices(GET /quotes).
 */
export default function MyStocksPage() {
  const router = useRouter();
  const data = useMyStocksData();
  /* 가격: 실제 모드면 GET /quotes 한 번 (2026-11-21), mock 모드면 mock 가격 */
  const priced = useStockPrices(data.stocks, data.universe, mockMyStocksData.as_of);
  if (data.loading) return <Loading height={400} />;
  if (data.failed) return <ErrorState message="내 종목을 불러오지 못했어요" onRetry={data.retry} />;
  return (
      <WebMyStocks
        {...mockMyStocksData}
        {...priced}
        popular={data.popular}
        add_remote={data.add_remote}
        onAddQuery={data.onAddQuery}
        onOpenStock={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code } })}
        onOpenCompany={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code, tab: 'info' } })}
        onAdd={(code, hold) => {
          const u = data.universe.find((s) => s.stock_code === code);
          if (!u) return;
          data.setStocks((all) => [...all, { stock_code: u.stock_code, name: u.name, logo: u.logo, logo_bg: u.logo_bg, logo_ink: u.logo_ink, market: u.market, status: hold, memo_count: 0, ai_count: 0, new_count: 0, price: u.price, change_pct: u.change_pct, ai_ready: u.ai_ready }]);
        }}
        onMove={(codes, hold) => data.setStocks((all) => all.map((s) => (codes.includes(s.stock_code) ? { ...s, status: hold } : s)))}
        onRemove={(codes) => data.setStocks((all) => all.filter((s) => !codes.includes(s.stock_code)))}
        onRestore={data.setStocks}
        onReorder={(codes) => data.setStocks((all) => codes.map((c) => all.find((s) => s.stock_code === c)).filter((s): s is MyStock => !!s))}
        onWriteMemo={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code } })}
      />
  );
}
