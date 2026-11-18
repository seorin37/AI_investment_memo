import React, { useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { MobileScreen } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { UpdateFeed } from '@/features/updates/UpdateFeed';
import { mockUpdateFeedProps } from '@/features/updates/UpdateFeed.mock';

/** 앱: 종목 하나의 업데이트 (홈 '새 소식' 줄에서 들어옴). mock 단계 */
export default function StockUpdates() {
  const { code } = useLocalSearchParams<{ code: string }>();
  const router = useRouter();
  const [selected, setSelected] = useState<string | null>(code ?? null);
  const name = mockUpdateFeedProps.stocks.find((s) => s.stock_code === code)?.name ?? '종목';
  return (
    <MobileScreen bar={<TopBar left="back" title={`${name} 업데이트`} onBack={() => router.back()} />}>
      <UpdateFeed
        {...mockUpdateFeedProps}
        selected_stock={selected}
        onSelectStock={setSelected}
        onOpenStock={(c) => router.push({ pathname: '/stocks/[code]', params: { code: c } })}
        onOpenItem={(c) => router.push({ pathname: '/stocks/[code]', params: { code: c } })}
      />
    </MobileScreen>
  );
}
