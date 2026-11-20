import React, { useState } from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
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
    onDone: () => router.replace('/login'),
  };
  return Platform.OS === 'web' ? <WebIntro {...props} /> : <AppIntro {...props} />;
}
