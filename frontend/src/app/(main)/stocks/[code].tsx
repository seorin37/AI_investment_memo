import React from 'react';
import { View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Page } from '@/components/layout/Page';
import { Loading, PillTabs } from '@/components/ui/primitives';
import { BoardScreen } from '@/features/board/BoardScreen';
import { CompanyInfo } from '@/features/company/CompanyInfo';
import { StockHeader } from '@/features/stock/StockHeader';
import { useMyStocks, useProfile } from '@/hooks/queries';

/** 6. 기업 메모장(보드) · 7. 기업정보 — /stocks/000660?tab=info */
export default function StockScreen() {
  const { code, tab } = useLocalSearchParams<{ code: string; tab?: 'board' | 'info' }>();
  const router = useRouter();
  const { data: mine } = useMyStocks();
  const { data: profile } = useProfile(code);
  const my = mine?.find((s) => s.code === code);
  const stock = my ?? (profile ? { code: profile.code, name: profile.name, market: profile.market } : null);
  const active = tab === 'info' ? 'info' : 'board';

  if (!stock) return <Loading height={400} />;

  return (
    <Page top={56}>
      <StockHeader stock={stock} mine={my} />
      <View style={{ marginTop: 24, marginBottom: 24 }}>
        <PillTabs
          items={[
            { key: 'board', label: '보드' },
            { key: 'info', label: '기업 정보' },
          ]}
          value={active}
          onChange={(k) => router.setParams({ tab: k })}
        />
      </View>
      {active === 'board' ? <BoardScreen stockCode={code} /> : <CompanyInfo stockCode={code} stockName={stock.name} />}
    </Page>
  );
}
