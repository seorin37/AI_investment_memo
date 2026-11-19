import type { ISODate, Memo, MemoColor, MemoVersion } from '@/types/models';

/** 소식 종류 (원본 앱 FK · 웹 KIND) */
export type FeedKind = '뉴스' | '공시' | '주가';

/**
 * AI 업데이트 한 건 (원본 앱 n.feed · 웹 m.timeline 의 뉴스·공시·주가).
 * models 의 AiUpdate 와 같은 뜻 — 화면에 필요한 값만 (API 연결 단계에서 AiUpdate → 이 모양으로).
 */
export interface MemoFeedItem {
  id: string;
  kind: FeedKind;
  /** 소식 날짜 (정렬 · 'MM.DD' 표시) */
  at: ISODate;
  /** 카드 제목: 'HBM4 공급 확대 소식이 나왔어요' */
  headline: string;
  /** 펼친 내용 (AI 요약 · 주가는 코드 계산 문장) */
  summary: string;
  /** 출처 줄: '한국경제 · 2026. 10. 15. 08:40' · 'DART · 2026. 10. 13. 17:05' · 'KIS · 10.11 종가' */
  source: string;
  /** 원문 링크 (뉴스·공시) */
  url: string | null;
  /** 뉴스: 기사 제목 (본문은 보여 주지 않음) */
  article_title?: string;
  /** 공시: 원문 일부 (짚기 1 을 누르면 펼침) · 그중 밑줄 칠 부분 */
  quote?: string;
  quote_mark?: string;
  /** 이 소식이 붙을 때의 메모 버전 (MemoVersion.version) */
  memo_version: number;
  /** 안 읽은 소식 */
  unread: boolean;
}

/** AI 가 메모에서 찾은 추적 항목 (서버가 정함 · 읽기 전용) */
export type AiTrackItem =
  | { kind: 'price'; label: string; price: number; direction: '이하' | '미만' | '이상'; quote: string }
  | { kind: 'fact'; label: string; quote: string };

/** 메모 상세 (웹·앱 같은 props) */
export interface MemoDetailProps {
  memo: Memo;
  /** 종목 이름 (웹 머리 '종목 · 날짜 작성' · 확인 시트 칩) */
  stockName: string;
  /** 수정 이력 — 최신이 앞 (models.MemoVersion) */
  versions: MemoVersion[];
  /** AI 업데이트 — 순서 무관 (화면이 날짜순으로) */
  feed: MemoFeedItem[];
  /** 추적 중인 항목 (AI 연결된 메모) */
  trackItems: AiTrackItem[];
  /** 마지막 확인 시각 문장 (소식이 없을 때 '마지막 확인 11.18 장 마감 후') */
  lastChecked?: string;
  /** 처음 여는 탭 (새 소식이 있으면 'ai') */
  initialTab?: 'memo' | 'ai';
  /** AI 사용량을 다 씀 */
  aiSpent?: boolean;
  /** 보드 이름 (앱 뒤로 버튼 옆 글자 · 알림에서 열면 '알림') */
  backLabel?: string;

  onBack: () => void;
  /** 편집 완료 (첫 줄 = 제목 · splitMemo) — 글이 바뀐 경우에만 */
  onSave: (p: { title: string; body: string }) => void;
  onChangeColor: (color: MemoColor) => void;
  onTogglePin: (pinned: boolean) => void;
  onDelete: () => void;
  onCopy: () => void;
  /** AI 연결 켜기 (AI 연결 창으로) */
  onConnectAi: () => void;
  /** AI 연결 끄기 (확인 시트에서 '연결 해제') */
  onDisconnectAi: () => void;
  /** AI 업데이트 탭을 봄 (안 읽은 소식 읽음 처리) */
  onSeenUpdates?: () => void;
  /** 원문 열기 (앱 안 브라우저) */
  onOpenSource?: (item: MemoFeedItem) => void;
  /** 근거 자세히 보기 (근거 상세 화면 — 다음 묶음) */
  onOpenEvidence?: (item: MemoFeedItem) => void;
  /** 넛지: 이 메모에 붙은 소식을 주간보고서로 */
  onNudge?: () => void;
  onSpentAction?: (a: 'credit' | 'plan') => void;
}

/** 새 메모 (웹·앱 같은 props) */
export interface NewMemoProps {
  stockName: string;
  /** 빈 보드 예시 칩에서 오면 그 문장이 첫 줄 */
  initialText?: string;
  onCancel: () => void;
  /** 첫 줄 = 제목 (splitMemo). ai = AI 연결 스위치 */
  onSave: (p: { title: string; body: string; color: MemoColor; ai: boolean }) => void;
  /** 웹 새 메모 창의 [체크리스트] 탭 (체크리스트 만들기는 체크리스트 묶음) */
  onSwitchToChecklist?: () => void;
}

/** AI 연결 창 상태: 분석 중 · 항목 있음 · 항목 없음 · 분석 실패 */
export type AiLinkState = 'loading' | 'items' | 'empty' | 'error';

export interface AiLinkProps {
  stockName: string;
  memo: { title: string; body: string; color: MemoColor };
  state: AiLinkState;
  items: AiTrackItem[];
  /** 새 메모 저장 직후에 열림 (단계 ① 메모 저장 ✓ 이 막 켜짐) */
  fromNew?: boolean;
  /** 확인 (AI 연결 시작) */
  onConfirm: () => void;
  /** 일반 메모로 두기 · 닫기 */
  onCancel: () => void;
  /** 항목 없음: 메모 수정 */
  onEditMemo?: () => void;
  /** 분석 실패: 다시 시도 */
  onRetry?: () => void;
}
