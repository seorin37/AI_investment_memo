import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { mockQuiz } from '@/ui/screens/studio/Studio.mock';
import { AppQuiz } from '@/ui/screens/studio/app/Quiz';

/** 앱 오늘의 퀴즈 (원본 studio.html pgQz). 제출은 화면 상태만 · 크레딧 변화 없음 */
export default function StudioQuizScreen() {
  const router = useRouter();
  const done = useStudioPlayer((s) => s.quizPick);
  const submit = useStudioPlayer((s) => s.submitQuiz);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return <AppQuiz q={mockQuiz} done={done} onBack={() => router.back()} onSubmit={submit} />;
}
