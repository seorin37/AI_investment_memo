/**
 * MEMO'S 도메인 타입 — FastAPI(Pydantic) 응답과 1:1로 맞춘 계약.
 * 백엔드와 동일하게 snake_case 를 그대로 사용합니다. (변환 레이어 없음)
 * 변경 시 docs/API_CONTRACT.md 도 함께 수정하세요.
 */

export type ISODate = string; // '2026-10-21T09:30:00+09:00'

// ─── 사용자 · 인증 ───────────────────────────────────────────
export type AuthProvider = 'kakao' | 'naver' | 'google';

export interface User {
  id: string;
  name: string;
  bio: string; // 한 줄 소개 (예: 대학생)
  avatar_url: string | null;
  email: string | null;
  providers: { provider: AuthProvider; email: string | null; connected: boolean; current: boolean }[];
  /** 요금제 (users.plan). 없으면 무료로 본다 (mock 사용자 등) */
  plan?: 'free' | 'plus' | 'pro';
}

/** 약관 하나 (kind: age·service·invest …, version: 서버가 정한 현재 버전 — 프론트에 두지 않는다) */
export interface TermsItem {
  kind: string;
  version: string;
}

/** GET · POST /me/terms 응답 (backend/app/account · 0022 user_terms_consents) */
export interface TermsStatus {
  /** 지금 동의해야 하는 필수 약관 (서버 값 그대로 POST 에 보낸다) */
  required: TermsItem[];
  /** 철회하지 않은 동의 (옛 버전 포함) */
  agreed: (TermsItem & { agreed_at: ISODate })[];
  /** 현재 버전 필수 약관을 모두 동의했는지 */
  complete: boolean;
}

export interface AuthToken {
  access_token: string | null;
  refresh_token?: string | null;
  token_type: 'bearer';
  expires_in: number;
  user: User;
}

// ─── 종목 ────────────────────────────────────────────────────
export type Market = 'KOSPI' | 'KOSDAQ' | 'KONEX';
export type StockStatus = 'holding' | 'watching';

export interface StockMaster {
  code: string; // '000660'
  name: string; // 'SK하이닉스'
  market: Market;
}

export interface MyStock extends StockMaster {
  status: StockStatus;
  tags: string[];
  unread_updates: number;
  /** 휴지통 제외 일반 메모 수 (GET /stocks · 2026-11-22). 서버는 늘 줌 — 옛 응답 · mock 대비 선택 칸 */
  memo_count?: number;
  /** AI 연결 메모 수 (GET /ai/stats linked_memos 와 같은 조건을 이 종목만) */
  ai_count?: number;
  added_at: ISODate;
}

export interface Quote {
  code: string;
  price: number;
  change: number;
  change_pct: number;
  as_of: ISODate;
  /** 종가 거래일 YYYY-MM-DD (2026-11-21 백엔드 추가) */
  trade_date?: string;
  spark: number[]; // 당일/최근 추이 (헤더 스파크라인)
}

/** GET /quotes?codes= — 여러 종목 시세 한 번에. 시세가 없는 종목은 missing */
export interface QuotesResponse {
  quotes: Quote[];
  missing: string[];
}

export interface Candle {
  date: string; // 'YYYY-MM-DD'
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type ChartRange = '1W' | '1M' | '3M' | '1Y';

export interface StockProfile {
  code: string;
  name: string;
  market: Market;
  overview: string;
  prev_close: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  trading_value: number; // 원
  per: number | null;
  pbr: number | null;
  eps: number | null;
  bps: number | null;
  market_cap: number; // 원
  shares_outstanding: number;
  week52_low: number;
  week52_high: number;
}

/**
 * 기업정보 재무 (GET /stocks/{code}/financials, 2026-11-21 UI v2 · docs/company-page-data-gaps-plan.md 11-21 결정).
 * 분기 단독 최대 12개(화면 8 + 전년 동기 4), 금액은 억원, 비율은 %. 값이 없으면 null → 화면에서 '—' 또는 그 항목을 뺀다.
 */
export interface FinancialQuarter {
  period_end: string; // '2026-09-30'
  q: string; // '26.3Q' (period_end 의 달력 분기)
  label: string; // '2026년 3분기'
  revenue: number | null; // 억원. 금융사 null
  op: number | null; // 영업이익 (금융사도 보냄)
  net: number | null;
  op_margin: number | null; // %. 금융사 null
  net_margin: number | null;
  roe: number | null; // % (TTM). 자본잠식 분기 null
}

export interface FinancialHealth {
  debt: number | null; // 부채비율 %
  current: number | null; // 유동비율 %. 금융사 null
  quick: number | null; // 당좌비율 %. 금융사 null
  interest: number | null; // 이자보상배율 (배). 금융사 null
  reserve: number | null; // 유보율 %
}

export interface Financials {
  code: string;
  source_code: string; // 우선주면 재무를 읽은 본주
  sector: 'general' | 'financial';
  fin_type: string | null;
  financial: boolean;
  preparing: boolean; // 분기 재무가 하나도 없음 (리츠·인프라펀드 등)
  basis: string; // '2026년 09월 기준 · 연결재무제표'
  quarters: FinancialQuarter[];
  health: FinancialHealth;
  health_as_of: string | null;
  interest_coverage_basis: string | null;
}

// ─── 메모 보드 ───────────────────────────────────────────────
export type MemoColor = 'yellow' | 'blue' | 'pink' | 'green' | 'purple';
export type BoardItemKind = 'memo' | 'checklist' | 'reference';

export interface PriceCondition {
  id: string;
  direction: 'below' | 'above';
  price: number;
  tracking: boolean; // 추적 ON/OFF (일시 중지)
  status: 'waiting' | 'reached' | 'paused';
  reached_at: ISODate | null;
}

export interface BoardItemBase {
  id: string;
  kind: BoardItemKind;
  stock_code: string;
  title: string;
  position: number;
  created_at: ISODate;
  updated_at: ISODate;
}

export interface Memo extends BoardItemBase {
  kind: 'memo';
  body: string;
  tags: string[];
  color: MemoColor;
  pinned: boolean; // 보드 상단 고정 + 홈 '고정한 메모'
  ai_linked: boolean;
  ai_linked_at: ISODate | null;
  price_conditions: PriceCondition[]; // 백엔드가 본문에서 코드로 파싱 (LLM 미사용)
  unread_updates: number;
  /** 저장·AI 연결 응답에만: 메모 분석 결과 (be/app/board/service.py, 목록 응답에는 null) */
  analysis?: MemoAnalysis | null;
}

/** 메모 분석 결과 — 추적 항목 · 확인 질문 (C-8) */
export interface MemoAnalysis {
  /** confirmed · unchanged · skipped(AI 끔) · failed */
  status: string;
  items: { id: string; type: string; description: string; price_threshold: number | null; status: string }[];
  confirmations: unknown[];
  out_of_scope?: boolean;
  error?: string | null;
  next_update_at?: string | null;
}

export interface ChecklistItem {
  id: string;
  text: string;
  done: boolean;
}

export interface Checklist extends BoardItemBase {
  kind: 'checklist';
  items: ChecklistItem[];
  pinned?: boolean; // 보드 고정(테이프). mock 시드에는 없음
}

export type ReferenceType = 'ir' | 'news' | 'report' | 'disclosure' | 'etc';

export interface ReferenceLink {
  id: string;
  title: string;
  url: string;
  ref_type: ReferenceType;
  source: 'link' | 'file';
}

export interface ReferenceBoard extends BoardItemBase {
  kind: 'reference';
  links: ReferenceLink[];
}

export type BoardItem = Memo | Checklist | ReferenceBoard;

export interface MemoVersion {
  version: number;
  title: string;
  body: string;
  saved_at: ISODate;
}

// ─── 시장 데이터 업데이트 (공시 · 뉴스 · 주가) ────────────────────
export type UpdateType = 'disclosure' | 'news' | 'price';

export interface MarketUpdate {
  id: string;
  stock_code: string;
  stock_name: string;
  type: UpdateType;
  title: string;
  source: string; // 'DART' | '연합뉴스' | '한국투자증권 KIS' ...
  url: string | null;
  published_at: ISODate;
}

/** AI가 메모와 연결한 업데이트 (임베딩 1차 필터 → LLM 최종 판단) */
export interface AiUpdate extends MarketUpdate {
  memo_id: string;
  memo_title: string;
  memo_version: number;
  summary: string; // LLM 요약 (짧은 사실 중심)
  headline: string; // 타임라인 제목: 'HBM4 공급 확대 소식이 나왔어요'
  read: boolean;
  relevance: number; // 0~1
  // ─ 백엔드가 덧붙이는 값 (be/app/updates/service.py · mock 에는 없을 수 있음)
  created_at?: ISODate;
  /** 메모와 연결되는 이유 (카드 문장) */
  reason?: string;
  /** DB 원래 종류 (answer = 질문 답) — type 은 계약 3종으로 바뀌어 옴 */
  card_type?: string;
  answer_status?: string | null;
  memo_color?: MemoColor;
  sources?: UpdateSourceRef[];
  price?: {
    state: string | null;
    observed_value: number | null;
    observed_trade_date: string | null;
    threshold: number | null;
    direction: 'above' | 'below' | null;
    /** 관측 거래일까지 최근 10거래일 종가 (오래된 → 최근) · 첫 종가의 거래일 */
    closes: number[];
    closes_from: string | null;
  } | null;
}

/** 카드 근거 한 건 (뉴스 · 공시) */
export interface UpdateSourceRef {
  kind: 'news' | 'disclosure';
  ref: string;
  title: string;
  source: string;
  url: string | null;
  published_at: string | null;
  quote: string | null;
}

export type TimelineEntry =
  | { kind: 'update'; at: ISODate; update: AiUpdate; memo_snapshot: MemoVersion }
  | { kind: 'memo_edit'; at: ISODate; version: MemoVersion }
  | { kind: 'memo_created'; at: ISODate; version: MemoVersion }
  | { kind: 'ai_linked'; at: ISODate };

export interface MemoTimeline {
  memo_id: string;
  entries: TimelineEntry[];
  price_condition_count: number;
}

/** 메모 질문 하나와 그 답 (GET /memos/{id}/answers, be/app/answers/routes.py) */
export interface MemoAnswer {
  id: string;
  question: string;
  asked_at: ISODate;
  /** pending = 다음 매일 실행에서 답함 · answered · no_answer = 자료에서 확인되지 않음 */
  status: 'pending' | 'answered' | 'no_answer';
  answer: {
    id: string;
    headline: string;
    summary: string;
    text: string;
    calculations: unknown[];
    sources: { kind: 'news' | 'disclosure'; title: string; source: string; date: string | null; url: string | null }[];
    answered_at: ISODate;
    read: boolean;
  } | null;
}

// ─── 투자 기록 ───────────────────────────────────────────────
/** 줄 전체 서식 (투자 기록 화면 JBlock 의 l · b · i · u · x). 모두 선택 */
export interface JournalLineFormat {
  list_style?: 'dot' | 'dash' | 'num' | 'quote';
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  strike?: boolean;
}

export type JournalBlock =
  | ({ id: string; type: 'paragraph'; text: string; highlight?: boolean } & JournalLineFormat)
  /** level 2 = 작은 제목 (없거나 1 = 제목) */
  | ({ id: string; type: 'heading'; text: string; highlight?: boolean; level?: 1 | 2 } & JournalLineFormat)
  | ({ id: string; type: 'checklist'; text: string; checked: boolean } & JournalLineFormat)
  | { id: string; type: 'table'; rows: string[][] }
  | { id: string; type: 'attachment'; name: string; url: string };

export interface JournalEntry {
  id: string;
  title: string;
  stock_code: string | null;
  stock_name: string | null;
  blocks: JournalBlock[];
  /** 고정 (journal_entries.is_pinned). 고정만 바꾸면 updated_at 은 그대로 */
  pinned: boolean;
  created_at: ISODate;
  updated_at: ISODate;
}

// ─── 홈 ──────────────────────────────────────────────────────
export type IndexRange = '1D' | '1W' | '1M' | '1Y';

export interface MarketIndex {
  key: 'KOSPI' | 'KOSDAQ' | 'USDKRW';
  label: string;
  flag: 'kr' | 'us';
  value: number;
  change: number;
  change_pct: number;
  series: Record<IndexRange, number[]>;
  /** 기준 거래일(관측일) YYYY-MM-DD (C-16, 2026-11-21) */
  trade_date?: string;
  /** series['1Y'] 와 같은 길이의 날짜 (다른 기간은 뒤에서 같은 개수) */
  dates?: string[];
}

/** GET /market/macro 지표 하나 (ECOS·FRED·KRX 금 원천값) */
export interface MacroIndicator {
  key: string; // 'USD_KRW' | 'KR_POLICY_RATE' | 'KR_GOV_3Y' | … | 'WTI_SPOT' | 'GOLD'
  label: string;
  unit: string; // '원' | '%' | '달러/배럴' | '원/g'
  value: number;
  prev_value: number | null;
  /** 최신 − 직전 (단위가 % 면 %p) */
  change: number | null;
  change_pct: number | null;
  observed_date: string; // YYYY-MM-DD
  prev_date: string | null;
  source: string | null; // 'ECOS' | 'FRED' | 'KRX'
  series_code: string | null;
}

export interface MacroOverview {
  indicators: MacroIndicator[];
  /** 관측값이 없는 지표 키 */
  missing: string[];
  as_of: string | null;
}

export interface MacroItem {
  key: string; // 'KR3Y' | 'US10Y' | 'GOLD' | 'WTI' | 'BASE_RATE'
  label: string;
  value: number;
  unit: string; // '%' | '$' | '원'
  change: number;
}

export interface MarketOverview {
  indices: MarketIndex[];
  macro: MacroItem[];
  as_of: ISODate;
}

export type CalendarCategory = 'holiday' | 'market' | 'mine';

export interface CalendarEvent {
  id: string;
  date: string; // 'YYYY-MM-DD'
  title: string;
  category: CalendarCategory;
  stock_code: string | null;
}

export type NewsSource = '매일경제' | '한국경제' | '서울경제' | '연합뉴스';

/** 홈 뉴스 위젯 기사 한 건 (GET /news/home · UI v2 HomeNewsItem 과 같은 모양) */
export interface HomeNewsArticle {
  id: string;
  title: string;
  /** 언론사 */
  src: string;
  /** 한국 시간 ISO (+09:00) */
  at: ISODate;
  url: string;
  /** 연결된 종목 코드 (관련성 높은 순) */
  stock_codes?: string[];
}

/** GET /news/home: 최신 기사 + 가장 새 기사 날짜(KST)의 종목 연결 기사 수 */
export interface HomeNews {
  /** YYYY-MM-DD (KST). 기사가 없으면 null */
  day: string | null;
  day_total: number;
  items: HomeNewsArticle[];
}

export interface NewsHeadline {
  id: string;
  title: string;
  source: NewsSource;
  url: string;
  published_at: ISODate;
}

export type WidgetType =
  | 'market'
  | 'updates'
  | 'calendar'
  | 'news'
  | 'pinned_memos'
  | 'checklist'
  | 'quick_memo'
  | 'price_conditions'
  | 'recent_journal'
  | 'memo_updates'
  | 'memo_backtest'
  | 'compare_memo'
  | 'conclude_memo';

export interface WidgetInstance {
  id: string;
  type: WidgetType;
  span: 1 | 2 | 3 | 4; // 4열 그리드 기준 너비
}

export interface HomeLayout {
  mode: 'unset' | 'template' | 'custom';
  widgets: WidgetInstance[];
}

export interface HomeChecklistItem {
  id: string;
  checklist_id: string;
  text: string;
  done: boolean;
  stock_code: string;
  stock_name: string;
}

export interface PriceConditionRow {
  memo_id: string;
  memo_title: string;
  stock_code: string;
  stock_name: string;
  condition: PriceCondition;
  current_price: number;
}

export interface MemoUpdateSummary {
  stock_code: string;
  stock_name: string;
  new_count: number;
  memos: { memo_id: string; title: string; color: MemoColor; updates: AiUpdate[] }[];
}

/** '메모대로 했다면' — 행동 조건 메모를 실제 주가로 검증 */
export interface MemoBacktest {
  memo_id: string;
  memo_title: string;
  stock_code: string;
  stock_name: string;
  condition: PriceCondition;
  triggered_at: ISODate | null;
  trigger_price: number | null;
  current_price: number;
  return_pct: number | null; // 조건 도달가 대비 현재 수익률
}

/** '비교 메모 자동 카드' — 'A랑 비교해보기' 메모에 두 기업 지표를 나란히 */
export interface CompareMemoCard {
  memo_id: string;
  memo_title: string;
  left: CompareSide;
  right: CompareSide;
}

export interface CompareSide {
  stock_code: string;
  stock_name: string;
  price: number;
  return_1m: number;
  per: number | null;
  pbr: number | null;
  operating_margin: number;
  roe: number;
  debt_ratio: number;
}

/** '결론 낼 메모' — 전제가 이미 일어난 메모 */
export interface ConcludeCandidate {
  memo_id: string;
  memo_title: string;
  memo_body: string;
  stock_code: string;
  stock_name: string;
  color: MemoColor;
  premise_event: string; // '3분기 실적이 발표됐어요'
  occurred_at: ISODate;
}

// ─── 휴지통 · 설정 · 피드백 ──────────────────────────────────
export type TrashKind = 'memo' | 'checklist' | 'reference' | 'journal' | 'stock' | 'studio';

export interface TrashItem {
  id: string;
  kind: TrashKind;
  title: string;
  context: string; // 'SK하이닉스 / 메모'
  deleted_at: ISODate;
}

export type ThemePref = 'system' | 'light' | 'dark';
export type UpDownColor = 'red_up' | 'green_up';

export interface Settings {
  theme: ThemePref;
  language: 'ko';
  updown_color: UpDownColor;
  notifications: {
    disclosure: boolean;
    news: boolean;
    price_condition: boolean;
    price_spike: boolean;
    price_spike_threshold: 3 | 5 | 10;
    channels: { in_app: boolean; email: boolean; push: boolean };
    frequency: 'realtime' | 'hourly' | 'daily';
    quiet_hours: { enabled: boolean; from: string; to: string };
  };
  ai: {
    default_link_new_memo: boolean;
    sources: { disclosure: boolean; news: boolean; price: boolean };
    sensitivity: 'strict' | 'balanced' | 'broad';
  };
  mcp: {
    enabled: boolean;
    server_url: string;
    scopes: { memo: boolean; journal: boolean; stock: boolean };
    access: 'read' | 'read_write';
    only_ai_linked: boolean;
    apps: { id: string; name: string; access: 'read' | 'read_write'; last_used_at: ISODate }[];
  };
}

export interface AiStats {
  linked_memos: number;
  updates_this_month: number;
  linked_stocks: number;
}

/** GET /ai/tracking — 설정 사용량 탭 '종목별 추적 현황' (내 종목마다 추적 항목이 있는 AI 연결 메모, 2026-11-23) */
export interface AiTrackingStock {
  stock_code: string;
  name: string;
  memos: { memo_id: string; title: string; chips: string[] }[];
}

/** 이번 기간 AI 크레딧 사용량 (GET /me/usage, backend/app/credits/ledger.py Usage). 화면에는 %만 보인다 */
export interface CreditUsage {
  usage_percent: number; // 0~100
  used: number;
  balance: number;
  period_start: string; // 'YYYY-MM-DD'
  renews_at: ISODate;
  renew_label: string; // '11.30 갱신'
  paused: boolean; // 남은 크레딧 0 → AI 업데이트 멈춤
}

/** 오늘의 퀴즈 (GET /quiz/today, backend/app/quiz, 문제 표 quiz_questions 0023) */
export interface TodayQuiz {
  slug: string;
  category: 'chart' | 'trading' | 'financials' | 'disclosure';
  quiz_type: 'four' | 'ox';
  label: string;
  question: string;
  options: string[];
  answer_index: number;
  explanation: string;
  concept: string;
  source: string;
  index: number;
  total: number;
}

export interface DataStats {
  memos: number;
  journals: number;
  stocks: number;
}

export interface FeedbackPayload {
  kind: 'general' | 'bug';
  rating?: number;
  screen?: string;
  categories?: string[];
  message: string;
}

/** POST /studio/lab — 투자 실험실 결과 (화면의 영향 경로 지도·항목별 설명) */
export type LabDirection = '상승' | '유지' | '하락';
export interface LabRunLeaf {
  t: string;
  ev: boolean;
  why: string;
  base: string;
  note?: string;
  check?: string;
  check_why?: string;
}
export interface LabRunGroup {
  i: number;
  d: LabDirection;
  leaves: LabRunLeaf[];
}
export interface LabRunResult {
  stock_code: string;
  name: string;
  groups: LabRunGroup[];
  source: 'llm' | 'rules';
  credits_used: number;
  /** 만든 항목으로 저장된 id (LLM 답일 때만, 저장 실패면 null) — studio_items (2026-11-23) */
  item_id?: string | null;
}

/** POST /studio/reports — 주간보고서 만들기 (같은 주·같은 조합이면 reused) */
export interface ReportCreateResult { item_id: string; status: 'generating' | 'ready' | 'queued'; reused: boolean }

/** GET /studio/items — 스튜디오 만든 항목 (studio_items, 30일 보관) */
export interface StudioItem {
  id: string;
  kind: 'report' | 'audio' | 'lab';
  status: 'queued' | 'generating' | 'ready' | 'failed';
  title: string;
  symbols: string[];
  /** lab: { stock_code, name, dirs, groups } */
  content: { stock_code?: string; name?: string; dirs?: LabDirection[]; groups?: LabRunGroup[] } & Record<string, unknown>;
  credits_used: number;
  created_at: ISODate;
  expires_at: ISODate;
  days_left: number;
}
