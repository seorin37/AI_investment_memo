import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { IntroSlides } from '@/features/onboarding/IntroSlides';
import { mockIntroSlidesProps } from '@/features/onboarding/IntroSlides.mock';
import { useAuth } from '@/store/auth';

/** 앱: 로그인 전 서비스 소개 3장 → 로그인. 웹(frontend)은 바로 로그인 */
export default function IntroScreen() {
  const router = useRouter();
  const status = useAuth((s) => s.status);
  if (Platform.OS === 'web') return <Redirect href="/login" />;
  if (status === 'signedIn') return <Redirect href="/" />;
  return <IntroSlides {...mockIntroSlidesProps} onDone={() => router.replace('/login')} />;
}
