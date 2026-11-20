import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { TopBar } from '@/ui/layout/app/TopBar';
import { mockMyProfile, mockMyUsage } from '@/ui/screens/my/My.mock';
import { mockMade, mockStudioCounts, mockStudioFeatures } from '@/ui/screens/studio/Studio.mock';
import { AppStudioHome } from '@/ui/screens/studio/app/StudioHome';

/**
 * 앱 스튜디오 탭 = UI v2 (원본 app/studio.html · ⑧-8a). 옛 화면 features/studio/StudioHome 은 라우트에서만 뺌.
 * 사용량·갱신일은 My.mock. 오디오·실험실은 ⑧-8b·8d 전까지 안내, 퀴즈·주간보고서는 옛 화면으로.
 * 웹은 오른쪽 스튜디오 열을 쓰므로 홈으로.
 */
const NOT_YET = '아직 연결되지 않았어요 · 데이터는 그대로예요';

export default function StudioTab() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppStudioHome
      header={
        <TopBar
          preset="studio"
          title="스튜디오"
          actions={[{ icon: 'bell', label: '알림', onPress: () => router.push('/my-inbox') }]}
          avatar={{ name: mockMyProfile.name, onPress: () => router.push('/my') }}
        />
      }
      features={mockStudioFeatures}
      made={mockMade}
      usage_pct={mockMyUsage.usage_pct}
      usage_refill={mockMyUsage.usage_refill}
      {...mockStudioCounts}
      onFeature={(k) => (k === 'quiz' ? router.push('/studio/quiz') : k === 'report' ? router.push('/studio/report') : toast(NOT_YET))}
      onOpenMade={(m) => (m.kind === 'report' ? router.push('/studio/report') : toast(NOT_YET))}
      onBuyCredit={() => router.push('/studio-charge')}
      onChangePlan={() => router.push('/my-plans')}
    />
  );
}
