import React, { useEffect } from 'react';
import { Platform } from 'react-native';
import { SplashScreen, Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import { QueryClientProvider } from '@tanstack/react-query';
import { setMotionEnabled } from '@/components/motion/motion';
import { queryClient } from '@/lib/queryClient';
import { useAuth } from '@/store/auth';
import { colors } from '@/theme/tokens';
import { CoachOverlay } from '@/ui/shared/Coach';
import { CoachExample } from '@/ui/shared/CoachExample';
import { DarkLayer, useDark } from '@/ui/shared/Dark';
import { useDarkDom } from '@/ui/shared/darkMode';

void SplashScreen.preventAutoHideAsync();
/* 11.18 결정: 화면 전환·페이드 등 모션 켬 (기기 '동작 줄이기'가 켜져 있으면 그대로 따름) */
setMotionEnabled(true);

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts({
    'Pretendard-Regular': require('../../assets/fonts/Pretendard-Regular.otf'),
    'Pretendard-Medium': require('../../assets/fonts/Pretendard-Medium.otf'),
    'Pretendard-SemiBold': require('../../assets/fonts/Pretendard-SemiBold.otf'),
    'Pretendard-Bold': require('../../assets/fonts/Pretendard-Bold.otf'),
    'Pretendard-ExtraBold': require('../../assets/fonts/Pretendard-ExtraBold.otf'),
  });

  const dark = useDark();
  /* 웹: html 전체 반전 (원본 theme.css) — 앱은 DarkLayer */
  useDarkDom(dark);
  const bootstrap = useAuth((s) => s.bootstrap);
  const authStatus = useAuth((s) => s.status);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const ready = (fontsLoaded || !!fontError) && authStatus !== 'loading';

  useEffect(() => {
    if (ready) SplashScreen.hide();
  }, [ready]);

  if (!ready) return null;

  return (
    <QueryClientProvider client={queryClient}>
      <StatusBar style={dark ? 'light' : 'dark'} />
      <DarkLayer>
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.page }, animation: Platform.OS === 'web' ? 'none' : 'default' }} />
        {/* 사용법 안내 메모 단계 예시 화면 (실제 모드에서 열 실제 AI 메모가 없을 때) — 안내보다 먼저 그려 안내가 위에 옴 */}
        <CoachExample />
        {/* 사용법 안내 (화면 위 모든 곳을 덮음) */}
        <CoachOverlay />
      </DarkLayer>
    </QueryClientProvider>
  );
}
