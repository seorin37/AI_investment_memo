import React from 'react';
import { Platform, View } from 'react-native';
import { Redirect, Stack } from 'expo-router';
import { MobileToast } from '@/components/layout/MobileScreen';
import { PUSH_SCREEN_OPTIONS } from '@/components/motion/Navigation';
import { useAuth } from '@/store/auth';

/**
 * 앱 전용: 하단 탭 위로 밀려 들어와 탭바를 가리는 화면 (메모 상세 · 새 메모 · AI 연결 · 체크리스트 · MY · 퀴즈 · 주간보고서 · 투자 기록 편집).
 * 웹(frontend)은 이 화면들이 없어 홈으로.
 */
export default function DetailLayout() {
  const status = useAuth((s) => s.status);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  if (status !== 'signedIn') return <Redirect href="/intro" />;
  return (
    <View style={{ flex: 1 }}>
      <Stack screenOptions={PUSH_SCREEN_OPTIONS}>
        <Stack.Screen name="memo/link" options={{ animation: 'slide_from_bottom' }} />
        <Stack.Screen name="memo/new" options={{ animation: 'slide_from_bottom' }} />
        {/* 원본 openCheck: 보드에서 열면 밀려 들어오고, + 버튼으로 새로 만들면 아래에서 올라옴 */}
        <Stack.Screen name="checklist/[id]" options={({ route }) => ((route.params as { id?: string } | undefined)?.id === 'new' ? { animation: 'slide_from_bottom' } : {})} />
      </Stack>
      <MobileToast bottom={32} />
    </View>
  );
}
