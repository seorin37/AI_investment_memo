import React, { useState } from 'react';
import { Linking } from 'react-native';
import { useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { TopBar } from '@/ui/layout/app/TopBar';
import { AppUpdates } from '@/ui/screens/updates/app/Updates';
import { mockUpdateItems, mockUpdatesNow, mockUpdateStocks } from '@/ui/screens/updates/Updates.mock';

/**
 * 앱 업데이트 탭 = UI v2 (ui/screens/updates/app · ⑥). 종목별 업데이트도 같은 화면에서 칩만 바뀜 (원본 11.05 A안).
 * mock: Updates.mock — 읽음 표시는 이 화면 안에서만. 소식 → 근거 상세(④-2) · 메모 보드(③).
 */
export default function UpdatesTab() {
  const router = useRouter();
  const notice = useMockNotice();
  const [items, setItems] = useState(mockUpdateItems);
  return (
    <AppUpdates
      stocks={mockUpdateStocks}
      items={items}
      now={mockUpdatesNow}
      header={({ title, line, onSearch, onReadAll, readAllOff }) => (
        <TopBar
          preset="updates"
          title={title ? '최신 업데이트' : undefined}
          showLine={line}
          actions={[
            ...(onReadAll ? [{ icon: 'checkAll' as const, label: '모두 읽음', onPress: onReadAll, color: readAllOff ? '#C9CBD1' : undefined }] : []),
            { icon: 'search', label: '검색', onPress: onSearch },
            { icon: 'bell', label: '알림', onPress: () => notice('알림') },
          ]}
          avatar={{ name: '김나라', onPress: () => router.push('/my') }}
        />
      )}
      onOpenEvidence={(u) => router.push({ pathname: '/memo/evidence', params: { id: u.memo_id, fid: u.id } })}
      onOpenBoard={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code } })}
      onOpenSource={(u) => u.url && Linking.openURL(u.url)}
      onMarkRead={(ids, read) => setItems((all) => all.map((u) => (ids.includes(u.id) ? { ...u, unread: !read } : u)))}
      onNudge={() => notice('AI 오디오')}
    />
  );
}
