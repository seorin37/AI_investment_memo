import React, { useState } from 'react';
import { Linking } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { mockUpdateItems, mockUpdatesNow, mockUpdateStocks } from '@/ui/screens/updates/Updates.mock';
import { WebUpdates } from '@/ui/screens/updates/web/Updates';

/** 웹 종목 업데이트 = UI v2 (⑥ · 원본 3.2). 같은 화면에서 그 종목 칩이 골라진 상태. mock: Updates.mock */
export default function StockUpdatesPage() {
  const { code } = useLocalSearchParams<{ code: string }>();
  const router = useRouter();
  const [items, setItems] = useState(mockUpdateItems);
  return (
    <WebUpdates
      stocks={mockUpdateStocks}
      items={items}
      now={mockUpdatesNow}
      code={code}
      onChangeCode={(c) => (c ? router.navigate({ pathname: '/updates/[code]', params: { code: c } }) : router.navigate('/updates'))}
      onOpenEvidence={(u) => router.navigate({ pathname: '/stocks/[code]', params: { code: u.stock_code, memo: u.memo_id, ev: u.id } })}
      onOpenBoard={(c) => router.navigate({ pathname: '/stocks/[code]', params: { code: c } })}
      onOpenSource={(u) => u.url && Linking.openURL(u.url)}
      onMarkRead={(ids, read) => setItems((all) => all.map((u) => (ids.includes(u.id) ? { ...u, unread: !read } : u)))}
      onNudge={() => {}}
    />
  );
}
