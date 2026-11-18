import React, { useState } from 'react';
import { useRouter } from 'expo-router';
import { MobileScreen } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { DailyQuiz } from '@/features/studio/DailyQuiz';
import { mockDailyQuizProps } from '@/features/studio/DailyQuiz.mock';

/** 오늘의 퀴즈. mock 단계 (스튜디오는 백엔드 API 없음) */
export default function QuizScreen() {
  const router = useRouter();
  const [picked, setPicked] = useState<number | null>(mockDailyQuizProps.submitted_index);
  return (
    <MobileScreen bar={<TopBar left="back" title="오늘의 퀴즈" onBack={() => router.back()} />}>
      <DailyQuiz {...mockDailyQuizProps} submitted_index={picked} onSubmit={setPicked} />
    </MobileScreen>
  );
}
