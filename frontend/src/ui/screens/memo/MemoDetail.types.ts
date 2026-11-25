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
  /** 공시 근거: 보고서 이름 */
  report?: string;
  /** 뉴스 근거: 제공 (원본 '한국경제 · 네이버 뉴스') */
  provider?: string;
  /** 가격 조건 근거 (코드 계산 · 전일 확정 종가) */
  price?: {
    close: number;
    cond: number;
    direction: '이하' | '미만' | '이상';
    /** 조건과의 차이 '+30,500원 (+20.3%)' */
    gap: string;
    /** 팀 11.09 결정: 가격 소식은 near = 가까워졌어요 · reached = 도달했어요 두 가지만 */
    tone: 'near' | 'reached';
    /** 차트 종가 (오래된 → 최근) */
    closes: number[];
    /** 차트 처음 · 끝 날짜 'MM.DD' */
    from: string;
    to: string;
  };
  /** 이 소식이 붙을 때의 메모 버전 (MemoVersion.version) */
  memo_version: number;
  /** 안 읽은 소식 */
  unread: boolean;
}

/** AI 가 메모에서 찾은 추적 항목 (서버가 정함 · 읽기 전용) */
export type AiTrackItem =
  | { kind: 'price'; label: string; price: number; direction: '이하' | '미만' | '이상'; quote: string }
  | { kind: 'fact'; label: string; quote: string }
  /** 한 번 답하는 질문 (tracking_items.type='ask', 다음 매일 실행에서 답) — 연결 창에만 보인다 (2026-11-23) */
  | { kind: 'ask'; label: string; quote: string };

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
  /** 웹: 처음부터 이 소식의 근거 상세로 열기 (업데이트 화면 ⑥ '근거 자세히 보기') */
  initialEvidence?: string;
  /** 바깥에서 탭 바꾸기 (근거 상세 [메모 보기] → 'memo'). 같은 탭을 다시 요청할 때는 key 를 바꿈 */
  tabRequest?: { tab: 'memo' | 'ai'; key: string };
  /** AI 사용량을 다 씀 */
  aiSpent?: boolean;
  /** 사용량이 다시 채워지는 날 ('12월 1일', GET /me/usage) */
  aiRefill?: string;
  /** 지금 AI 연결이 켜진 메모 수. 크레딧 0이고 이 값이 있으면 '충전하지 않으면 N개가 모두 꺼져요' (끄기 대기, 2026-11-24) */
  aiCount?: number;
  /** 보드 이름 (앱 뒤로 버튼 옆 글자 · 알림에서 열면 '알림') */
  backLabel?: string;
  /** 머리에 붙는 칩 (사용법 안내 예시 화면의 '예시' — 실제 데이터로 보이지 않게) */
  badge?: string;

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
  onSpentAction?: (a: 'credit' | 'plan' | 'choice') => void;
}

/** 근거 상세 (원본 memo.html 13.1 공시 · 13.2 뉴스 · 13.3 가격 조건) */
export interface EvidenceProps {
  item: MemoFeedItem;
  memo: Memo;
  /** 이 소식이 붙을 때의 메모 버전 */
  version?: MemoVersion;
  onBack: () => void;
  /** [메모 보기] — 메모 상세의 메모 탭으로 */
  onShowMemo: () => void;
  /** 원문 열기 (앱 안 브라우저는 연결 단계) */
  onOpenSource: (item: MemoFeedItem) => void;
  /** 연결된 내 메모를 누르면 그 버전 이력 */
  onOpenHistory: (version: number) => void;
}

/** 수정 이력 (원본 memo.html 10 · 근거 상세의 메모 카드에서 열림) */
export interface MemoHistoryProps {
  memo: Memo;
  /** 최신이 앞 */
  versions: MemoVersion[];
  /** 처음 펼칠 버전 */
  openVersion?: number;
  onBack: () => void;
}

/** 새 메모 (웹·앱 같은 props) */
export interface NewMemoProps {
  stockName: string;
  /** 빈 보드 예시 칩에서 오면 그 문장이 첫 줄 */
  initialText?: string;
  /** AI 연결 스위치 처음 값 (주간보고서 '메모에 추가'로 열면 켬, 2026-11-24) */
  initialAi?: boolean;
  /** AI 사용량(크레딧)을 다 씀 → AI 연결 스위치를 켤 수 없고 일반 메모로만 저장 (2026-11-24) */
  aiSpent?: boolean;
  onCancel: () => void;
  /** 빈 채로 완료 (원본: 닫고 '빈 메모는 저장하지 않았어요' 스낵바) */
  onEmpty?: () => void;
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
