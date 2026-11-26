import React from 'react';
import { Linking } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { TopBar } from '@/ui/layout/app/TopBar';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';
import { AppUpdates } from '@/ui/screens/updates/app/Updates';
import { useAppUpdatesData } from '@/ui/screens/updates/app/useAppUpdates';

/** 앱 종목별 업데이트 (홈 업데이트 위젯에서 들어옴) = 업데이트 탭과 같은 화면, 그 종목 칩이 골라진 채로. 뒤로 = 홈 */
export default function StockUpdatesScreen() {
  const { code } = useLocalSearchParams<{ code: string }>();
  const router = useRouter();
  const { profile: { name: myName } } = useMyProfile();
  const notice = useMockNotice();
  const { stocks, items, now, onMarkRead } = useAppUpdatesData();
  return (
    <AppUpdates
      stocks={stocks}
      items={items}
      now={now}
      code={code}
      header={({ line, onReadAll, readAllOff }) => (
        <TopBar
          preset="updates"
          title="최신 업데이트"
          subtitle="내 종목의 공시·뉴스·주가 변동을 모아봤어요"
          showLine={line}
          actions={[
            ...(onReadAll ? [{ icon: 'checkAll' as const, label: '모두 읽음', onPress: onReadAll, color: readAllOff ? '#C9CBD1' : undefined }] : []),
            { icon: 'bell', label: '알림', onPress: () => router.push('/my-inbox') },
          ]}
          avatar={{ name: myName, onPress: () => router.push('/my') }}
        />
      )}
      onOpenEvidence={(u) => router.push({ pathname: '/memo/evidence', params: { id: u.memo_id, fid: u.id } })}
      onOpenBoard={(c) => router.navigate({ pathname: '/stocks/[code]', params: { code: c } })}
      onOpenSource={(u) => u.url && Linking.openURL(u.url)}
      onMarkRead={onMarkRead}
      onNudge={() => notice('AI 오디오')}
    />
  );
}
