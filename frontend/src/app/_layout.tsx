import React, { useEffect, useState } from 'react';
import { Platform } from 'react-native';
import { SplashScreen, Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ApiError } from '@/api';
import { setMotionEnabled } from '@/components/motion/motion';
import { useAuth } from '@/store/auth';
import { colors } from '@/theme/tokens';
import { CoachOverlay } from '@/ui/shared/Coach';
import { DarkLayer, useDark } from '@/ui/shared/Dark';
import { useDarkDom } from '@/ui/shared/darkMode';

void SplashScreen.preventAutoHideAsync();
/* 11.18 결정: 화면 전환·페이드 등 모션 켬 (기기 '동작 줄이기'가 켜져 있으면 그대로 따름) */
setMotionEnabled(true);

export default function RootLayout() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: (count, err) => !(err instanceof ApiError && [401, 403, 404].includes(err.status)) && count < 2,
            refetchOnWindowFocus: Platform.OS === 'web',
          },
        },
      }),
  );

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
        {/* 사용법 안내 (화면 위 모든 곳을 덮음) */}
        <CoachOverlay />
      </DarkLayer>
    </QueryClientProvider>
  );
}
