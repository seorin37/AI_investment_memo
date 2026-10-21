import React from 'react';
import { Platform } from 'react-native';
import { Redirect, Stack } from 'expo-router';
import { AppShell } from '@/components/layout/AppShell';
import { useAuth } from '@/store/auth';
import { colors } from '@/theme/tokens';

/** 로그인 후 영역: 사이드바(웹/태블릿) · 드로어(모바일) + 전역 모달 */
export default function MainLayout() {
  const status = useAuth((s) => s.status);
  if (status !== 'signedIn') return <Redirect href="/login" />;
  return (
    <AppShell>
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.page }, animation: Platform.OS === 'web' ? 'none' : 'fade' }} />
    </AppShell>
  );
}
