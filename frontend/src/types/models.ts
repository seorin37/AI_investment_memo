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
  added_at: ISODate;
}

export interface Quote {
  code: string;
  price: number;
  change: number;
  change_pct: number;
  as_of: ISODate;
  spark: number[]; // 당일/최근 추이 (헤더 스파크라인)
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

export interface AnnualFinancial {
  period: string; // '2025-12'
  revenue: number; // 원
  operating_income: number;
  net_income: number;
  operating_margin: number; // %
  net_margin: number; // %
  roe: number; // %
}

export interface Stability {
  as_of: string; // '2026-06'
  debt_ratio: number; // 부채비율 %
  current_ratio: number; // 유동비율 %
  quick_ratio: number; // 당좌비율 %
  interest_coverage: number; // 이자보상배율 (배)
  reserve_ratio: number; // 유보율 %
}

export interface Financials {
  code: string;
  basis: string; // '2026년 06월 기준 · 연결재무제표'
  annual: AnnualFinancial[];
  stability: Stability;
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
}

export interface ChecklistItem {
  id: string;
  text: string;
  done: boolean;
}

export interface Checklist extends BoardItemBase {
  kind: 'checklist';
  items: ChecklistItem[];
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

// ─── 투자 기록 ───────────────────────────────────────────────
export type JournalBlock =
  | { id: string; type: 'paragraph'; text: string; highlight?: boolean }
  | { id: string; type: 'heading'; text: string; highlight?: boolean }
  | { id: string; type: 'checklist'; text: string; checked: boolean }
  | { id: string; type: 'table'; rows: string[][] }
  | { id: string; type: 'attachment'; name: string; url: string };

export interface JournalEntry {
  id: string;
  title: string;
  stock_code: string | null;
  stock_name: string | null;
  blocks: JournalBlock[];
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
export type TrashKind = 'memo' | 'checklist' | 'reference' | 'journal' | 'stock';

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
