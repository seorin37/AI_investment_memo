import React from 'react';
import { Image } from 'react-native';
import { useRouter } from 'expo-router';
import { MobileScreen, useMockNotice, useProfileAction } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { useLargeTitle } from '@/components/motion/Navigation';
import { MobileHome } from '@/features/home/MobileHome';
import { mockMobileHomeProps } from '@/features/home/MobileHome.mock';

/** 앱 홈 탭 (웹은 index.tsx 의 HomeScreen). mock 단계: MobileHome.mock 데이터 */
export default function HomeTab() {
  const router = useRouter();
  const profile = useProfileAction();
  const notice = useMockNotice();
  const lt = useLargeTitle();
  return (
    <MobileScreen
      bar={
        <TopBar
          left="logo"
          logo={<Image source={require('../../../assets/images/logo-wordmark.png')} style={{ width: 96, height: 32 }} resizeMode="contain" />}
          actions={[{ kind: 'icon', icon: 'bell', label: '알림', onPress: () => notice('알림') }, profile]}
          lineOpacity={lt.barLineOpacity}
        />
      }
    >
      <MobileHome
        {...mockMobileHomeProps}
        onScroll={lt.onScroll}
        onOpenUpdates={() => router.navigate('/updates')}
        onOpenStockUpdates={(code) => router.navigate({ pathname: '/updates/[code]', params: { code } })}
        onOpenMarket={() => notice('시장 자세히')}
        onRetryMarket={() => notice('다시 시도')}
        onOpenNews={() => notice('뉴스 원문')}
      />
    </MobileScreen>
  );
}
