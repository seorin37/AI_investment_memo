import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useQuizAnswer } from '@/ui/screens/studio/useQuizAnswer';
import { useTodayQuizView } from '@/ui/screens/studio/useTodayQuiz';
import { AppQuiz } from '@/ui/screens/studio/app/Quiz';

/** 앱 오늘의 퀴즈 (원본 studio.html pgQz). 문제는 실제 모드면 DB(GET /quiz/today). 제출은 기기에 저장 (useQuizAnswer) · 크레딧 변화 없음 */
export default function StudioQuizScreen() {
  const router = useRouter();
  const quiz = useTodayQuizView();
  /* 오늘 푼 답 (기기 저장 · 사용자 + 날짜 + 문제) — 앱을 다시 켜도 하루 한 번 */
  const ans = useQuizAnswer(quiz.slug, quiz.ready);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return <AppQuiz q={quiz} done={ans.done} locked={!ans.canSubmit} onBack={() => router.back()} onSubmit={ans.submit} />;
}
