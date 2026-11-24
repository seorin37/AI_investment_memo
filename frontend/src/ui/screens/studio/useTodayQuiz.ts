import { env } from '@/config/env';
import { useTodayQuiz } from '@/hooks/queries';
import { mockQuiz } from './Studio.mock';
import { fromServerQuiz, todayQuiz, type QuizView } from './quizBank';

/**
 * 오늘의 퀴즈 화면 props (2026-11-22).
 * 실제 모드: GET /quiz/today (DB quiz_questions). 읽는 중 · 문제 없음(404) · 실패면 내장 30문제로 대신.
 * enabled=false 면 서버에 묻지 않음 (웹 레이아웃은 퀴즈 화면을 열었을 때만).
 * mock 모드: 내장 30문제 (지금처럼). 연속 참여 · 이번 주 표시는 기록 API 가 없어 예시 값.
 */
export function useTodayQuizView(enabled = true): QuizView & { ready: boolean } {
  const real = !env.useMock;
  const server = useTodayQuiz(real && enabled);
  /* ready: 오늘 문제가 확정됐는지 — 실제 모드는 서버 답이 오거나 실패(내장 문제로 확정)한 뒤. 그 전엔 제출 막음 (다른 slug 로 기록되면 하루 두 번 풀 수 있어서) */
  const ready = !real || server.isSuccess || server.isError;
  return { ...(real && server.data ? fromServerQuiz(mockQuiz, server.data) : todayQuiz(mockQuiz)), ready };
}
