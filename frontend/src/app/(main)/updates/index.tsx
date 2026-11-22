import React from 'react';
import { Linking } from 'react-native';
import { useRouter } from 'expo-router';
import { useUpdatesData } from '@/ui/screens/updates/useUpdatesData';
import { WebUpdates } from '@/ui/screens/updates/web/Updates';

/**
 * 웹 최신 업데이트 = UI v2 (ui/screens/updates/web · ⑥). 종목 칩 → /updates/[code].
 * 데이터: useUpdatesData (실제 GET /updates · USE_MOCK 이면 Updates.mock). [근거 자세히 보기] → 메모 보드(③)의 메모 창을 그 소식 근거로(④-2).
 */
export default function UpdatesPage() {
  const router = useRouter();
  const { stocks, items, now, onMarkRead } = useUpdatesData();
  return (
    <WebUpdates
      stocks={stocks}
      items={items}
      now={now}
      onChangeCode={(c) => (c ? router.navigate({ pathname: '/updates/[code]', params: { code: c } }) : router.navigate('/updates'))}
      onOpenEvidence={(u) => router.navigate({ pathname: '/stocks/[code]', params: { code: u.stock_code, memo: u.memo_id, ev: u.id } })}
      onOpenBoard={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code } })}
      onOpenSource={(u) => u.url && Linking.openURL(u.url)}
      onMarkRead={onMarkRead}
      onNudge={() => {}}
    />
  );
}
