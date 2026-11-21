import type {
  AiStats,
  AiUpdate,
  AuthToken,
  BoardItem,
  CalendarEvent,
  Candle,
  ChartRange,
  Checklist,
  ChecklistItem,
  CompareMemoCard,
  ConcludeCandidate,
  CreditUsage,
  DataStats,
  FeedbackPayload,
  Financials,
  HomeChecklistItem,
  HomeLayout,
  JournalBlock,
  JournalEntry,
  MacroOverview,
  MarketOverview,
  MarketUpdate,
  Memo,
  MemoBacktest,
  MemoColor,
  MemoTimeline,
  MemoUpdateSummary,
  MyStock,
  NewsHeadline,
  HomeNews,
  PriceConditionRow,
  Quote,
  QuotesResponse,
  ReferenceBoard,
  ReferenceLink,
  Settings,
  StockMaster,
  StockProfile,
  StockStatus,
  TrashItem,
  User,
} from '@/types/models';

export type DeepPartial<T> = { [K in keyof T]?: T[K] extends object ? (T[K] extends unknown[] ? T[K] : DeepPartial<T[K]>) : T[K] };

export type PinnedMemo = Memo & { stock_name: string };

export interface MemoInput {
  title: string;
  body: string;
  tags: string[];
  color: MemoColor;
  ai_linked: boolean;
  pinned?: boolean;
}

export interface ChecklistInput {
  title: string;
  items: Omit<ChecklistItem, 'id'>[] | ChecklistItem[];
}

export interface ReferenceInput {
  title: string;
  links: Omit<ReferenceLink, 'id'>[] | ReferenceLink[];
}

export type BoardItemPatch =
  | Partial<Pick<Memo, 'title' | 'body' | 'tags' | 'color' | 'pinned' | 'position'>>
  | Partial<Pick<Checklist, 'title' | 'items' | 'position' | 'pinned'>>
  | Partial<Pick<ReferenceBoard, 'title' | 'links' | 'position'>>;

export interface JournalInput {
  title: string;
  stock_code: string | null;
  blocks: JournalBlock[];
}

export interface UploadFile {
  uri: string;
  name: string;
  mimeType?: string | null;
  file?: Blob; // 웹: DocumentPicker 가 File 객체를 제공
}

/**
 * 프론트엔드가 FastAPI 에 기대하는 전체 계약.
 * real.ts(HTTP) 와 mock/index.ts(메모리) 가 동일 인터페이스를 구현합니다.
 */
export interface Api {
  // 인증
  refreshAuth(refreshToken?: string): Promise<AuthToken>;
  exchangeMobileAuth(code: string, codeVerifier: string): Promise<AuthToken>;
  me(): Promise<User>;
  updateMe(patch: Partial<Pick<User, 'name' | 'bio'>>): Promise<User>;
  logout(refreshToken?: string): Promise<void>;

  // 종목
  listMyStocks(): Promise<MyStock[]>;
  searchStocks(q: string): Promise<StockMaster[]>;
  getStock(code: string): Promise<StockMaster>;
  addStock(code: string, status: StockStatus): Promise<MyStock>;
  updateStock(code: string, patch: Partial<Pick<MyStock, 'status' | 'tags'>>): Promise<MyStock>;
  removeStock(code: string): Promise<void>;
  getQuote(code: string): Promise<Quote>;
  /** 여러 종목 시세 한 번에 (보드·내 종목 목록) */
  getQuotes(codes: string[]): Promise<QuotesResponse>;
  getCandles(code: string, range: ChartRange): Promise<Candle[]>;
  getProfile(code: string): Promise<StockProfile>;
  getFinancials(code: string): Promise<Financials>;

  // 메모 보드
  listBoard(code: string): Promise<BoardItem[]>;
  getBoardItem(id: string): Promise<BoardItem>;
  createMemo(code: string, input: MemoInput): Promise<Memo>;
  createChecklist(code: string, input: ChecklistInput): Promise<Checklist>;
  createReference(code: string, input: ReferenceInput): Promise<ReferenceBoard>;
  updateBoardItem(id: string, patch: BoardItemPatch): Promise<BoardItem>;
  deleteBoardItem(id: string): Promise<void>;
  setAiLink(memoId: string, enabled: boolean): Promise<Memo>;
  setBoardChecklistItem(checklistId: string, itemId: string, done: boolean): Promise<void>;
  getMemoTimeline(memoId: string): Promise<MemoTimeline>;
  listStockAiUpdates(code: string): Promise<AiUpdate[]>;
  markAiUpdateRead(id: string): Promise<void>;
  uploadFile(file: UploadFile): Promise<{ url: string; name: string }>;

  // 최신 업데이트
  listUpdates(params?: { stock_code?: string; limit?: number }): Promise<MarketUpdate[]>;

  // 투자 기록
  listJournal(): Promise<JournalEntry[]>;
  createJournal(input: JournalInput): Promise<JournalEntry>;
  updateJournal(id: string, patch: Partial<JournalInput>): Promise<JournalEntry>;
  deleteJournal(id: string): Promise<void>;

  // 홈
  getHomeLayout(): Promise<HomeLayout>;
  saveHomeLayout(layout: HomeLayout): Promise<HomeLayout>;
  getMarketOverview(): Promise<MarketOverview>;
  /** 거시 지표 (ECOS·FRED·KRX 금) */
  getMacro(): Promise<MacroOverview>;
  listCalendar(month: string): Promise<CalendarEvent[]>;
  createCalendarEvent(input: { date: string; title: string }): Promise<CalendarEvent>;
  listNews(): Promise<NewsHeadline[]>;
  /** 홈 뉴스 위젯 (UI v2) */
  getHomeNews(limit?: number): Promise<HomeNews>;
  listPinnedMemos(): Promise<PinnedMemo[]>;
  listHomeChecklist(): Promise<HomeChecklistItem[]>;
  setChecklistItem(checklistId: string, itemId: string, done: boolean): Promise<void>;
  addChecklistItem(stockCode: string, text: string): Promise<HomeChecklistItem>;
  listPriceConditions(): Promise<PriceConditionRow[]>;
  setPriceConditionTracking(memoId: string, conditionId: string, tracking: boolean): Promise<void>;
  listMemoUpdateSummary(): Promise<MemoUpdateSummary[]>;
  listMemoBacktests(): Promise<MemoBacktest[]>;
  listCompareMemos(): Promise<CompareMemoCard[]>;
  listConcludeCandidates(): Promise<ConcludeCandidate[]>;
  concludeMemo(memoId: string, conclusion: string): Promise<JournalEntry>;

  // 휴지통 · 설정 · 데이터 · 피드백
  listTrash(): Promise<TrashItem[]>;
  restoreTrash(id: string): Promise<void>;
  purgeTrash(id: string): Promise<void>;
  getSettings(): Promise<Settings>;
  updateSettings(patch: DeepPartial<Settings>): Promise<Settings>;
  disconnectMcpApp(appId: string): Promise<Settings>;
  getAiStats(): Promise<AiStats>;
  /** 이번 기간 AI 크레딧 사용량. 이번 달 기본량을 아직 안 받았으면 서버가 이 호출에서 지급한다 */
  getUsage(): Promise<CreditUsage>;
  getDataStats(): Promise<DataStats>;
  exportData(format: 'csv' | 'json'): Promise<{ url: string }>;
  deleteAllData(): Promise<void>;
  sendFeedback(payload: FeedbackPayload): Promise<void>;
}
