import React, { useState } from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { MobileScreen, useMockNotice, useProfileAction } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { useLargeTitle } from '@/components/motion/Navigation';
import { StudioHome } from '@/features/studio/StudioHome';
import { mockStudioHomeProps } from '@/features/studio/StudioHome.mock';

/** 앱 스튜디오 탭 (웹 frontend 에는 없음 → 홈으로). mock 단계 — 스튜디오는 백엔드 API가 없어 다음 단계에도 mock */
export default function StudioTab() {
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return <StudioScreen />;
}

function StudioScreen() {
  const router = useRouter();
  const profile = useProfileAction();
  const notice = useMockNotice();
  const lt = useLargeTitle();
  const [playing, setPlaying] = useState<string | null>(null);
  return (
    <MobileScreen bar={<TopBar left="title" title="스튜디오" actions={[profile]} lineOpacity={lt.barLineOpacity} />}>
      <StudioHome
        {...mockStudioHomeProps}
        playing_id={playing}
        onPlayAudio={(id) => setPlaying((p) => (p === id ? null : id))}
        onOpenUsage={() => notice('사용량')}
        onOpenFeature={(key) => (key === 'quiz' ? router.push('/studio/quiz') : key === 'report' ? router.push('/studio/report') : notice(key === 'audio' ? 'AI 오디오' : 'AI 투자 실험실'))}
        onOpenMade={() => router.push('/studio/report')}
        onScroll={lt.onScroll}
      />
    </MobileScreen>
  );
}
