import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useCoach } from '@/store/coach';
import { mockFaq } from '@/ui/screens/my/My.mock';
import { AppHelp } from '@/ui/screens/my/app/Help';

/** 앱 MY › 도움말. '사용법 다시 보기' = 위에 쌓인 화면을 닫고 사용법 안내 첫 카드부터 (원본 my.html → MX.coach(-1)) */
export default function MyHelpScreen() {
  const router = useRouter();
  const replay = useCoach((s) => s.replay);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return <AppHelp faq={mockFaq} onBack={() => router.back()} onReplayGuide={() => {
        router.dismissAll();
        replay();
      }} />;
}
