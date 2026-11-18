/** 오늘의 퀴즈 예시 — 체험판/웹과 같은 문제 (정답 SK하이닉스) */
import type { DailyQuizProps } from '@/features/studio/DailyQuiz.types';

export const mockDailyQuizProps: DailyQuizProps = {
  quiz: {
    date_label: '어제(11.06 금) 증시 퀴즈',
    question: '어제 코스피에서 거래대금이\n가장 많았던 종목은?',
    options: ['삼성전자', 'SK하이닉스', '현대차', 'LG에너지솔루션'],
    answer_index: 1,
    explanation: 'SK하이닉스가 약 2조 1,000억 원으로 거래대금 1위였어요.',
    concept: '거래대금은 거래량에 가격을 곱한 값이라, 비싼 종목이 많이 거래될수록 커져요.',
    source: '한국거래소 (11.06 기준) · 화면 예시',
  },
  streak_days: 3,
  week: [
    { label: '월', state: 'done' },
    { label: '화', state: 'done' },
    { label: '수', state: 'done' },
    { label: '목', state: 'today' },
    { label: '금', state: 'upcoming' },
  ],
  submitted_index: null,
  onSubmit: () => {},
};

/** 제출한 뒤 */
export const mockDailyQuizDoneProps: DailyQuizProps = {
  ...mockDailyQuizProps,
  streak_days: 4,
  week: mockDailyQuizProps.week.map((d) => (d.state === 'today' ? { ...d, state: 'done' } : d)),
  submitted_index: 1,
};
