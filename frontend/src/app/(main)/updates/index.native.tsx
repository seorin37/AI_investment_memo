import React from 'react';
import { Linking } from 'react-native';
import { useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { TopBar } from '@/ui/layout/app/TopBar';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';
import { AppUpdates } from '@/ui/screens/updates/app/Updates';
import { useUpdatesData } from '@/ui/screens/updates/useUpdatesData';

/**
 * 앱 업데이트 탭 = UI v2 (ui/screens/updates/app · ⑥). 종목별 업데이트도 같은 화면에서 칩만 바뀜 (원본 11.05 A안).
 * 데이터: useUpdatesData (실제 GET /updates · USE_MOCK 이면 Updates.mock). 소식 → 근거 상세(④-2) · 메모 보드(③).
 */
export default function UpdatesTab() {
  const router = useRouter();
  const { profile: { name: myName } } = useMyProfile();
  const notice = useMockNotice();
  const { stocks, items, now, onMarkRead } = useUpdatesData();
  return (
    <AppUpdates
      stocks={stocks}
      items={items}
      now={now}
      header={({ line, onReadAll, readAllOff }) => (
        <TopBar
          preset="updates"
          title="최신 업데이트"
          showLine={line}
          actions={[
            ...(onReadAll ? [{ icon: 'checkAll' as const, label: '모두 읽음', onPress: onReadAll, color: readAllOff ? '#C9CBD1' : undefined }] : []),
            { icon: 'bell', label: '알림', onPress: () => router.push('/my-inbox') },
          ]}
          avatar={{ name: myName, onPress: () => router.push('/my') }}
        />
      )}
      onOpenEvidence={(u) => router.push({ pathname: '/memo/evidence', params: { id: u.memo_id, fid: u.id } })}
      onOpenBoard={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code } })}
      onOpenSource={(u) => u.url && Linking.openURL(u.url)}
      onMarkRead={onMarkRead}
      onNudge={() => notice('AI 오디오')}
    />
  );
}
