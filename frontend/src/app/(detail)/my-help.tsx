import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { mockFaq } from '@/ui/screens/my/My.mock';
import { AppHelp } from '@/ui/screens/my/app/Help';

/** 앱 MY › 도움말. '사용법 다시 보기'는 ⑩ 사용법 안내 전까지 안내만 */
export default function MyHelpScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return <AppHelp faq={mockFaq} onBack={() => router.back()} onReplayGuide={() => toast('사용법 안내는 아직 준비 중이에요')} />;
}
