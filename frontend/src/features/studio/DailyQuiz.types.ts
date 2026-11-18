/** 오늘의 퀴즈 (보상 없이 참여 기록만 · 11.17 결정) */
export interface QuizQuestion {
  date_label: string; // '어제(11.06 금) 증시 퀴즈'
  question: string;
  options: string[]; // 4지선다
  answer_index: number;
  explanation: string;
  concept: string; // 관련 개념
  source: string; // '한국거래소 (11.06 기준)'
}

export interface QuizDay {
  label: string; // '월'
  state: 'done' | 'today' | 'missed' | 'upcoming';
}

export interface DailyQuizProps {
  quiz: QuizQuestion;
  streak_days: number;
  week: QuizDay[];
  /** 오늘 이미 제출했으면 고른 번호 (없으면 null) */
  submitted_index: number | null;
  onSubmit: (index: number) => void;
}
