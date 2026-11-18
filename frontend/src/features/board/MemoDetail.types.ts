import type { MemoColor } from '@/types/models';

export type MemoDetailTab = 'memo' | 'ai';

/** 이 메모에서 AI가 추적 중인 항목 (사용자가 확인한 것만) */
export interface DetailTrackingItem {
  id: string;
  kind: 'disclosure_news' | 'price';
  label: string; // '실적 발표 내용' · '15만원 이하가 되면 알려드려요'
}

/** AI 업데이트 탭의 소식 1개 */
export interface DetailUpdate {
  id: string;
  kind: 'news' | 'disclosure' | 'price';
  date: string; // 'MM.DD'
  is_new: boolean;
  headline: string; // 'HBM4 공급 확대 소식이 나왔어요'
  /** 뉴스: "메모에서 확인하려던 ○○ 관련 뉴스예요" 한 줄 / 공시: AI 요약 / 주가: 코드로 계산한 문장 */
  summary: string;
  source: string; // '한국경제 · 2026. 10. 15. 08:40'
  /** 뉴스 기사 제목 (원문 링크로 열기) */
  article_title?: string;
  /** 가격 조건 소식: 종가 · 조건가 · 차이 */
  price?: { close: number; condition: number; gap_text: string; tone: 'near' | 'far' };
}

export interface DetailMemo {
  id: string;
  title: string;
  body: string;
  color: MemoColor;
  pinned: boolean;
  ai_linked: boolean;
  /** '2026년 10월 1일 작성' */
  date_full: string;
  /** 'MM.DD' — AI 연결 시작일, 첫 메모일 (소식이 없을 때 기록 줄에 씀) */
  ai_linked_on?: string;
  created_on: string;
  tracking_items: DetailTrackingItem[];
}

export interface MemoDetailProps {
  memo: DetailMemo;
  updates: DetailUpdate[];
  tab: MemoDetailTab;
  onChangeTab: (tab: MemoDetailTab) => void;
  /** 메모 글 수정 (첫 줄 = 제목). 완료는 상단 바(TopBar)의 [완료]에서 호스트가 처리 */
  editing: boolean;
  draft: string;
  onStartEdit: () => void;
  onChangeDraft: (text: string) => void;
  /** AI 사용량을 다 써서 AI 업데이트가 멈췄을 때 */
  ai_paused?: boolean;
  onBuyCredit?: () => void;
  onChangePlan?: () => void;
  onOpenEvidence: (update_id: string) => void;
  onOpenOriginal: (update_id: string) => void;
  /** 켜기 → AiLinkConfirm 화면, 끄기 → 확인 시트 (호스트) */
  onToggleAi: () => void;
  onOpenHistory: () => void;
}
