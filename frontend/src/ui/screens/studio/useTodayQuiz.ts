import { env } from '@/config/env';
import { useTodayQuiz } from '@/hooks/queries';
import { mockQuiz } from './Studio.mock';
import { fromServerQuiz, todayQuiz } from './quizBank';

/**
 * 오늘의 퀴즈 화면 props (2026-11-22).
 * 실제 모드: GET /quiz/today (DB quiz_questions). 읽는 중 · 문제 없음(404) · 실패면 내장 30문제로 대신.
 * enabled=false 면 서버에 묻지 않음 (웹 레이아웃은 퀴즈 화면을 열었을 때만).
 * mock 모드: 내장 30문제 (지금처럼). 연속 참여 · 이번 주 표시는 기록 API 가 없어 예시 값.
 */
export function useTodayQuizView(enabled = true): typeof mockQuiz {
  const real = !env.useMock;
  const server = useTodayQuiz(real && enabled);
  return real && server.data ? fromServerQuiz(mockQuiz, server.data) : todayQuiz(mockQuiz);
}
