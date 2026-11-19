import type { MemoColor } from '@/types/models';

/** 메모에서 찾은 추적 후보 (서버 추출 결과 · 사용자가 고른 것만 연결) */
export interface TrackingCandidate {
  id: string;
  kind: 'disclosure_news' | 'price';
  label: string; // '실적 발표 내용' · '15만원 이하가 되면 알려드려요'
  /** 메모 속 근거 문장 */
  quote: string;
  /** 가격 조건일 때 */
  price?: { condition: number; direction: '이하' | '이상' };
  selected: boolean;
}

/** 단계: 찾는 중 → 항목 고르기 → (항목 없음) → 연결됨 */
export type AiLinkStep = 'scanning' | 'select' | 'none' | 'done';

export interface AiLinkConfirmProps {
  step: AiLinkStep;
  stock_name: string;
  memo: { title: string; body: string; color: MemoColor };
  candidates: TrackingCandidate[];
  onToggleCandidate: (id: string) => void;
  onConnect: () => void;
  onLater: () => void;
  /** 항목을 못 찾았을 때 메모 수정으로 */
  onEditMemo: () => void;
}
