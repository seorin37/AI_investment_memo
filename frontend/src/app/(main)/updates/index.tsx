import React, { useState } from 'react';
import { Linking } from 'react-native';
import { useRouter } from 'expo-router';
import { mockUpdateItems, mockUpdatesNow, mockUpdateStocks } from '@/ui/screens/updates/Updates.mock';
import { WebUpdates } from '@/ui/screens/updates/web/Updates';

/**
 * 웹 최신 업데이트 = UI v2 (ui/screens/updates/web · ⑥). 종목 칩 → /updates/[code].
 * mock: Updates.mock — 읽음 표시는 이 화면 안에서만. [근거 자세히 보기] → 메모 보드(③)의 메모 창을 그 소식 근거로(④-2).
 */
export default function UpdatesPage() {
  const router = useRouter();
  const [items, setItems] = useState(mockUpdateItems);
  return (
    <WebUpdates
      stocks={mockUpdateStocks}
      items={items}
      now={mockUpdatesNow}
      onChangeCode={(c) => (c ? router.navigate({ pathname: '/updates/[code]', params: { code: c } }) : router.navigate('/updates'))}
      onOpenEvidence={(u) => router.navigate({ pathname: '/stocks/[code]', params: { code: u.stock_code, memo: u.memo_id, ev: u.id } })}
      onOpenBoard={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code } })}
      onOpenSource={(u) => u.url && Linking.openURL(u.url)}
      onMarkRead={(ids, read) => setItems((all) => all.map((u) => (ids.includes(u.id) ? { ...u, unread: !read } : u)))}
      onNudge={() => {}}
    />
  );
}
