import React, { useState } from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { markIntroSeen } from '@/lib/introSeen';
import { useAuth } from '@/store/auth';
import { mockIntroPages } from '@/ui/screens/auth/Auth.mock';
import { AppIntro } from '@/ui/screens/auth/app/Intro';
import { WebIntro } from '@/ui/screens/auth/web/Intro';

export default function IntroScreen() {
  const router = useRouter();
  const status = useAuth((s) => s.status);
  const [page, setPage] = useState(0);
  if (status === 'signedIn') return <Redirect href="/" />;
  const props = {
    pages: mockIntroPages,
    page,
    onPageChange: setPage,
    /* 본 상태 저장 (웹은 다음부터 /login 으로 바로, 앱은 지금 동작 그대로) */
    onDone: () => {
      void markIntroSeen();
      router.replace('/login');
    },
  };
  return Platform.OS === 'web' ? <WebIntro {...props} /> : <AppIntro {...props} />;
}
