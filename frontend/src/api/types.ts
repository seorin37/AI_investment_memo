import type {
  AiStats,
  AiTrackingStock,
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
  TodayQuiz,
  DataStats,
  FeedbackPayload,
  Financials,
  HomeChecklistItem,
  HomeLayout,
  JournalBlock,
  JournalEntry,
  LabDirection,
  LabRunResult,
  StudioItem,
  ReportCreateResult,
  AudioItem,
  AudioOptions,
  AudioPeriod,
  MacroOverview,
  MarketOverview,
  MarketUpdate,
  Memo,
  MemoBacktest,
  MemoColor,
  MemoAnswer,
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
  TermsItem,
  TermsStatus,
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
  pinned?: boolean;
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
  /** 약관 동의 상태 (GET /me/terms) — 로그인 뒤 신규 판별 · 약관 화면 */
  getTerms(): Promise<TermsStatus>;
  /** 약관 동의 저장 (POST /me/terms). items 는 getTerms().required 그대로 */
  agreeTerms(items: TermsItem[]): Promise<TermsStatus>;

  // 종목
  listMyStocks(): Promise<MyStock[]>;
  searchStocks(q: string): Promise<StockMaster[]>;
  /** 많이 찾는 종목 (GET /stocks/popular · 온보딩). 담은 사람 3명 이상 → 모자라면 시총 순. 기본 12 · 최대 30 */
  getPopularStocks(limit?: number): Promise<StockMaster[]>;
  getStock(code: string): Promise<StockMaster>;
  addStock(code: string, status: StockStatus): Promise<MyStock>;
  updateStock(code: string, patch: Partial<Pick<MyStock, 'status' | 'tags'>>): Promise<MyStock>;
  removeStock(code: string): Promise<void>;
  /** 사이드바 내 종목 전체 순서 저장 (PUT /stocks/order) → 새 순서의 목록 */
  reorderStocks(codes: string[]): Promise<MyStock[]>;
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
  /** 보드 카드 전체 순서 저장 (PUT /stocks/{code}/board-order) → 새 순서의 보드 */
  reorderBoard(code: string, ids: string[]): Promise<BoardItem[]>;
  /** AI 확인 질문에 답하기 (POST /memos/{id}/confirmations) → 바뀐 메모 */
  answerConfirmation(memoId: string, optionId: string): Promise<Memo>;
  /** 메모 질문과 답 (GET /memos/{id}/answers) */
  listMemoAnswers(memoId: string): Promise<MemoAnswer[]>;
  listStockAiUpdates(code: string): Promise<AiUpdate[]>;
  markAiUpdateRead(id: string): Promise<void>;
  /** 메모 하나의 안 읽은 AI 업데이트를 모두 읽음으로 (POST /memos/{id}/ai-updates/read) — 메모 창에서 소식을 봤을 때 */
  markMemoUpdatesRead(memoId: string): Promise<void>;
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
  /** 투자 실험실 실행 (LLM) */
  runLab(input: { stock_code: string; dirs: LabDirection[] }, opts?: { timeoutMs?: number }): Promise<LabRunResult>;
  /** 스튜디오 만든 항목 (studio_items, 내 것·만료 전) */
  listStudioItems(): Promise<StudioItem[]>;
  deleteStudioItem(id: string): Promise<void>;
  /** 주간보고서 제안으로 메모를 저장했음을 기록 (key = '종목코드:sid', 2026-11-24) */
  markReportWatch(itemId: string, key: string, memoId: string): Promise<void>;
  /** 주간보고서 만들기 (백그라운드, 완성은 listStudioItems로 확인) */
  createReport(input: { codes: string[]; market: boolean }): Promise<ReportCreateResult>;
  /** AI 오디오 (2026-11-24): 만들기 시트 값 · 만들기(백그라운드) · 상태와 결과 (파일은 GET /studio/audio/{id}/file) */
  getAudioOptions(): Promise<AudioOptions>;
  createAudio(input: { codes: string[]; period: AudioPeriod; market: boolean }): Promise<ReportCreateResult>;
  getAudio(id: string): Promise<AudioItem>;
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
  /** 설정 사용량 탭 종목별 추적 현황 */
  getAiTracking(): Promise<AiTrackingStock[]>;
  /** 이번 기간 AI 크레딧 사용량. 이번 달 기본량을 아직 안 받았으면 서버가 이 호출에서 지급한다 */
  getUsage(): Promise<CreditUsage>;
  /** 크레딧을 다 쓴 뒤 'AI 연결 모두 끄기' (POST /me/ai-off, 2026-11-24). 끈 메모 수 */
  aiOffAll(): Promise<{ turned_off: number }>;
  /** 자동 꺼짐 안내 확인 (POST /me/ai-off/notice-seen). 메모는 꺼진 채 표시만 지운다 */
  aiOffNoticeSeen(): Promise<{ cleared: number }>;
  /** 오늘의 퀴즈 1문제 (한국 시간 오전 10시마다 다음 문제). 문제가 없으면 404 */
  getTodayQuiz(): Promise<TodayQuiz>;
  getDataStats(): Promise<DataStats>;
  exportData(format: 'csv' | 'json'): Promise<{ url: string }>;
  deleteAllData(): Promise<void>;
  sendFeedback(payload: FeedbackPayload): Promise<void>;
}
