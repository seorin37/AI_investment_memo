/**
 * React Query 훅 — 화면은 api 를 직접 부르지 않고 이 훅만 사용합니다.
 * 캐시 키를 한곳에서 관리해 변경(mutation) 후 무효화 범위를 일관되게 유지합니다.
 */
import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { api } from '@/api';
import type { BoardItemPatch, ChecklistInput, DeepPartial, JournalInput, MemoInput, ReferenceInput } from '@/api';
import type { BoardItem, ChartRange, FeedbackPayload, HomeLayout, Settings, StockStatus, User } from '@/types/models';

export const qk = {
  stocks: ['stocks'] as const,
  stockSearch: (q: string) => ['stockSearch', q] as const,
  popularStocks: (limit: number) => ['popularStocks', limit] as const,
  stock: (code: string) => ['stock', code] as const,
  quote: (code: string) => ['quote', code] as const,
  quotes: (codes: string) => ['quotes', codes] as const,
  macro: ['macro'] as const,
  candles: (code: string, range: ChartRange) => ['candles', code, range] as const,
  profile: (code: string) => ['profile', code] as const,
  financials: (code: string) => ['financials', code] as const,
  board: (code: string) => ['board', code] as const,
  boardItem: (id: string) => ['boardItem', id] as const,
  timeline: (memoId: string) => ['timeline', memoId] as const,
  answers: (memoId: string) => ['answers', memoId] as const,
  stockAiUpdates: (code: string) => ['stockAiUpdates', code] as const,
  updates: (code?: string) => ['updates', code ?? 'all'] as const,
  journal: ['journal'] as const,
  homeLayout: ['homeLayout'] as const,
  market: ['market'] as const,
  calendar: (month: string) => ['calendar', month] as const,
  news: ['news'] as const,
  homeNews: ['homeNews'] as const,
  pinned: ['pinned'] as const,
  homeChecklist: ['homeChecklist'] as const,
  priceConditions: ['priceConditions'] as const,
  memoUpdateSummary: ['memoUpdateSummary'] as const,
  backtests: ['backtests'] as const,
  compare: ['compare'] as const,
  conclude: ['conclude'] as const,
  trash: ['trash'] as const,
  settings: ['settings'] as const,
  aiStats: ['aiStats'] as const,
  aiTracking: ['aiTracking'] as const,
  todayQuiz: ['todayQuiz'] as const,
  studioItems: ['studioItems'] as const,
  usage: ['usage'] as const,
  dataStats: ['dataStats'] as const,
};

/** 메모/보드가 바뀌면 함께 갱신해야 하는 홈 위젯 키 */
const memoDependents = [qk.aiTracking, qk.pinned, qk.homeChecklist, qk.priceConditions, qk.memoUpdateSummary, qk.backtests, qk.compare, qk.conclude, qk.aiStats, qk.dataStats];

function useInvalidate() {
  const qc = useQueryClient();
  return (...keys: readonly (readonly unknown[])[]) => Promise.all(keys.map((queryKey) => qc.invalidateQueries({ queryKey })));
}

// ─── 종목 ────────────────────────────────────────────────────
export const useMyStocks = () => useQuery({ queryKey: qk.stocks, queryFn: api.listMyStocks });

/** 많이 찾는 종목 (온보딩). 자주 바뀌지 않아 10분 동안은 다시 묻지 않음. enabled=false 면 부르지 않음(mock 화면) */
export const usePopularStocks = (limit = 12, enabled = true) =>
  useQuery({ queryKey: qk.popularStocks(limit), queryFn: () => api.getPopularStocks(limit), staleTime: 10 * 60_000, enabled });

export const useStockSearch = (q: string) =>
  useQuery({ queryKey: qk.stockSearch(q), queryFn: () => api.searchStocks(q), enabled: q.trim().length > 0, placeholderData: keepPreviousData });

export const useStock = (code: string) =>
  useQuery({ queryKey: qk.stock(code), queryFn: () => api.getStock(code), enabled: code.length > 0 });

/** enabled: 기본 true (기업정보처럼 늘 읽음). mock 화면을 그대로 두는 곳은 false 로 끈다 */
export const useQuote = (code: string, enabled = true) =>
  useQuery({ queryKey: qk.quote(code), queryFn: () => api.getQuote(code), refetchInterval: 60_000, enabled: enabled && code.length > 0 });

/** 여러 종목 시세 한 번에 (GET /quotes). 받은 값은 종목별 useQuote 캐시에도 넣어 같은 값을 쓰게 한다 */
export function useQuotes(codes: string[], enabled = true) {
  const qc = useQueryClient();
  const sorted = [...new Set(codes)].sort();
  return useQuery({
    queryKey: qk.quotes(sorted.join(',')),
    queryFn: async () => {
      const res = await api.getQuotes(sorted);
      for (const q of res.quotes) qc.setQueryData(qk.quote(q.code), q);
      return res;
    },
    enabled: enabled && sorted.length > 0,
    staleTime: 60_000,
  });
}

export const useCandles = (code: string, range: ChartRange) =>
  useQuery({ queryKey: qk.candles(code, range), queryFn: () => api.getCandles(code, range), placeholderData: keepPreviousData });

export const useProfile = (code: string) => useQuery({ queryKey: qk.profile(code), queryFn: () => api.getProfile(code) });
export const useFinancials = (code: string) => useQuery({ queryKey: qk.financials(code), queryFn: () => api.getFinancials(code) });

export function useAddStock() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ code, status }: { code: string; status: StockStatus }) => api.addStock(code, status),
    onSuccess: () => inv(qk.stocks, qk.updates(), qk.dataStats),
  });
}

export function useUpdateStock() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ code, patch }: { code: string; patch: { status?: StockStatus; tags?: string[] } }) => api.updateStock(code, patch),
    onSuccess: () => inv(qk.stocks),
  });
}

export function useRemoveStock() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (code: string) => api.removeStock(code), onSuccess: () => inv(qk.stocks, qk.trash, qk.updates(), ...memoDependents) });
}

// ─── 메모 보드 ───────────────────────────────────────────────
export const useBoard = (code: string) => useQuery({ queryKey: qk.board(code), queryFn: () => api.listBoard(code) });
export const useBoardItem = (id: string, enabled = true) =>
  useQuery({ queryKey: qk.boardItem(id), queryFn: () => api.getBoardItem(id), enabled: enabled && id.length > 0 });
export const useMemoTimeline = (memoId: string, enabled = true) =>
  useQuery({ queryKey: qk.timeline(memoId), queryFn: () => api.getMemoTimeline(memoId), enabled });
export const useStockAiUpdates = (code: string) => useQuery({ queryKey: qk.stockAiUpdates(code), queryFn: () => api.listStockAiUpdates(code) });

export function useCreateBoardItem(code: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (
      v: { kind: 'memo'; input: MemoInput } | { kind: 'checklist'; input: ChecklistInput } | { kind: 'reference'; input: ReferenceInput },
    ): Promise<BoardItem> => {
      if (v.kind === 'memo') return api.createMemo(code, v.input);
      if (v.kind === 'checklist') return api.createChecklist(code, v.input);
      return api.createReference(code, v.input);
    },
    onSuccess: () => inv(qk.board(code), ...memoDependents),
  });
}

export function useUpdateBoardItem(code: string) {
  const qc = useQueryClient();
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: BoardItemPatch }) => api.updateBoardItem(id, patch),
    onSuccess: (item) => {
      qc.setQueryData(qk.boardItem(item.id), item);
      void qc.invalidateQueries({ queryKey: qk.timeline(item.id) });
      return inv(qk.board(code), ...memoDependents);
    },
  });
}

/** 홈 위젯처럼 종목이 고정되지 않은 곳에서 메모 생성 */
export function useCreateMemoFor() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ code, input }: { code: string; input: MemoInput }) => api.createMemo(code, input),
    onSuccess: (_m, v) => inv(qk.board(v.code), ...memoDependents),
  });
}

/** 홈 위젯에서 메모 수정(고정 해제 등) */
export function usePatchMemoFor() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; code: string; patch: BoardItemPatch }) => api.updateBoardItem(id, patch),
    onSuccess: (_m, v) => inv(qk.board(v.code), qk.timeline(v.id), ...memoDependents),
  });
}

export function useDeleteBoardItem(code: string) {
  const qc = useQueryClient();
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api.deleteBoardItem(id),
    onSuccess: (_data, id) => {
      qc.removeQueries({ queryKey: qk.boardItem(id) });
      return inv(qk.board(code), qk.trash, ...memoDependents);
    },
  });
}

export function useSetAiLink(code: string) {
  const qc = useQueryClient();
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ memoId, enabled }: { memoId: string; enabled: boolean }) => api.setAiLink(memoId, enabled),
    // 토글은 즉시 반영(낙관적 업데이트)
    onMutate: async ({ memoId, enabled }) => {
      await qc.cancelQueries({ queryKey: qk.board(code) });
      const prev = qc.getQueryData(qk.board(code));
      qc.setQueryData(qk.board(code), (old: Awaited<ReturnType<typeof api.listBoard>> | undefined) =>
        old?.map((b) => (b.id === memoId && b.kind === 'memo' ? { ...b, ai_linked: enabled } : b)),
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => ctx?.prev && qc.setQueryData(qk.board(code), ctx.prev),
    onSettled: (_d, _e, v) => inv(qk.board(code), qk.boardItem(v.memoId), qk.timeline(v.memoId), qk.stockAiUpdates(code), ...memoDependents),
  });
}

export function useSetBoardChecklistItem() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (v: { checklistId: string; itemId: string; done: boolean; stockCode: string }) =>
      api.setBoardChecklistItem(v.checklistId, v.itemId, v.done),
    onSuccess: (_data, value) => inv(qk.board(value.stockCode)),
  });
}

/** 사이드바 내 종목 순서 저장 (PUT /stocks/order). 화면 순서를 먼저 바꾸고, 실패하면 되돌린다 */
export function useReorderStocks() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (codes: string[]) => api.reorderStocks(codes),
    onMutate: async (codes) => {
      await qc.cancelQueries({ queryKey: qk.stocks });
      const prev = qc.getQueryData<Awaited<ReturnType<typeof api.listMyStocks>>>(qk.stocks);
      if (prev) qc.setQueryData(qk.stocks, [...prev].sort((a, b) => codes.indexOf(a.code) - codes.indexOf(b.code)));
      return { prev };
    },
    onError: (_e, _v, ctx) => ctx?.prev && qc.setQueryData(qk.stocks, ctx.prev),
    onSuccess: (rows) => qc.setQueryData(qk.stocks, rows),
  });
}

/** 보드 카드 순서 저장 (PUT /stocks/{code}/board-order). 화면 순서를 먼저 바꾸고, 실패하면 되돌린다 */
export function useReorderBoard(code: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => api.reorderBoard(code, ids),
    onMutate: async (ids) => {
      await qc.cancelQueries({ queryKey: qk.board(code) });
      const prev = qc.getQueryData<BoardItem[]>(qk.board(code));
      if (prev) qc.setQueryData(qk.board(code), ids.map((id) => prev.find((b) => b.id === id)).filter(Boolean).map((b, i) => ({ ...(b as BoardItem), position: i })));
      return { prev };
    },
    onError: (_e, _v, ctx) => ctx?.prev && qc.setQueryData(qk.board(code), ctx.prev),
    onSuccess: (rows) => qc.setQueryData(qk.board(code), rows),
  });
}

/** AI 확인 질문 답 (POST /memos/{id}/confirmations) */
export function useAnswerConfirmation(code: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (v: { memoId: string; optionId: string }) => api.answerConfirmation(v.memoId, v.optionId),
    onSuccess: (_d, v) => inv(qk.board(code), qk.boardItem(v.memoId), qk.timeline(v.memoId), qk.answers(v.memoId)),
  });
}

/** 메모 질문과 답 (GET /memos/{id}/answers) */
export const useMemoAnswers = (memoId: string, enabled = true) =>
  useQuery({ queryKey: qk.answers(memoId), queryFn: () => api.listMemoAnswers(memoId), enabled: enabled && memoId.length > 0 });

/**
 * 읽음 처리 뒤 빨간 점·숫자를 다시 읽을 곳 (2026-11-23).
 * 종목 숫자(stocks) · 홈 업데이트 위젯(memoUpdateSummary · updates) · 업데이트 화면(updates 모든 종목) · 메모 보드 배지(board 모든 종목) · 보드 패널(stockAiUpdates)
 * 열려 있는 메모 창의 소식(timeline · boardItem)은 '새 소식' 표시가 바로 사라지지 않게 다시 부르지 않고 '오래됨'만 표시 → 다음에 열 때 새로 받음
 */
function useInvalidateRead() {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      ...[qk.stocks, qk.memoUpdateSummary, ['updates'], ['board'], ['stockAiUpdates']].map((queryKey) => qc.invalidateQueries({ queryKey })),
      ...[['timeline'], ['boardItem']].map((queryKey) => qc.invalidateQueries({ queryKey, refetchType: 'none' })),
    ]);
}

/** 카드 여러 개 읽음 (업데이트 화면 · 모두 읽음). 다 보낸 뒤 한 번만 다시 읽음 */
export function useMarkAiUpdateRead() {
  const refresh = useInvalidateRead();
  return useMutation({
    mutationFn: (ids: string[]) => Promise.all(ids.map((id) => api.markAiUpdateRead(id))),
    onSettled: refresh,
  });
}

/** 메모 하나의 소식을 모두 읽음 (메모 창에서 AI 업데이트를 봤을 때) */
export function useMarkMemoUpdatesRead() {
  const refresh = useInvalidateRead();
  return useMutation({
    mutationFn: (memoId: string) => api.markMemoUpdatesRead(memoId),
    onSettled: refresh,
  });
}

// ─── 업데이트 ────────────────────────────────────────────────
export const useUpdates = (code?: string) =>
  useQuery({ queryKey: qk.updates(code), queryFn: () => api.listUpdates(code ? { stock_code: code } : undefined) });

// ─── 투자 기록 ───────────────────────────────────────────────
export const useJournal = () => useQuery({ queryKey: qk.journal, queryFn: api.listJournal });

export function useCreateJournal() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (input: JournalInput) => api.createJournal(input), onSuccess: () => inv(qk.journal, qk.dataStats) });
}

export function useUpdateJournal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<JournalInput> }) => api.updateJournal(id, patch),
    onSuccess: (entry) =>
      qc.setQueryData(qk.journal, (old: Awaited<ReturnType<typeof api.listJournal>> | undefined) => old?.map((j) => (j.id === entry.id ? entry : j))),
  });
}

export function useDeleteJournal() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (id: string) => api.deleteJournal(id), onSuccess: () => inv(qk.journal, qk.trash, qk.dataStats) });
}

// ─── 홈 ──────────────────────────────────────────────────────
export const useHomeLayout = () => useQuery({ queryKey: qk.homeLayout, queryFn: api.getHomeLayout });

export function useSaveHomeLayout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (layout: HomeLayout) => api.saveHomeLayout(layout),
    onMutate: (layout) => qc.setQueryData(qk.homeLayout, layout),
  });
}

export const useMarketOverview = (enabled = true) =>
  useQuery({ queryKey: qk.market, queryFn: api.getMarketOverview, refetchInterval: 60_000, enabled });
/** 거시 지표 (GET /market/macro). 관측값은 하루 한 번 바뀌어 5분 동안 다시 읽지 않는다 */
export const useMacro = (enabled = true) => useQuery({ queryKey: qk.macro, queryFn: api.getMacro, staleTime: 5 * 60_000, enabled });
export const useCalendar = (month: string) =>
  useQuery({ queryKey: qk.calendar(month), queryFn: () => api.listCalendar(month), placeholderData: keepPreviousData });

export function useCreateCalendarEvent() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (input: { date: string; title: string }) => api.createCalendarEvent(input),
    onSuccess: (e) => inv(qk.calendar(e.date.slice(0, 7))),
  });
}

export const useNews = () => useQuery({ queryKey: qk.news, queryFn: api.listNews, refetchInterval: 5 * 60_000 });
/** 홈 뉴스 위젯 (웹 9개 · 앱 5개만 그림). 수집이 30분마다라 5분마다 다시 받는다 */
export const useHomeNews = () => useQuery({ queryKey: qk.homeNews, queryFn: () => api.getHomeNews(9), refetchInterval: 5 * 60_000 });
export const usePinnedMemos = () => useQuery({ queryKey: qk.pinned, queryFn: api.listPinnedMemos });
export const useHomeChecklist = () => useQuery({ queryKey: qk.homeChecklist, queryFn: api.listHomeChecklist });
export const usePriceConditions = () => useQuery({ queryKey: qk.priceConditions, queryFn: api.listPriceConditions });
export const useMemoUpdateSummary = () => useQuery({ queryKey: qk.memoUpdateSummary, queryFn: api.listMemoUpdateSummary });
export const useMemoBacktests = () => useQuery({ queryKey: qk.backtests, queryFn: api.listMemoBacktests });
export const useCompareMemos = () => useQuery({ queryKey: qk.compare, queryFn: api.listCompareMemos });
export const useConcludeCandidates = () => useQuery({ queryKey: qk.conclude, queryFn: api.listConcludeCandidates });

export function useSetChecklistItem() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (v: { checklistId: string; itemId: string; done: boolean; stockCode: string }) => api.setChecklistItem(v.checklistId, v.itemId, v.done),
    onSuccess: (_d, v) => inv(qk.homeChecklist, qk.board(v.stockCode)),
  });
}

export function useAddChecklistItem() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (v: { stockCode: string; text: string }) => api.addChecklistItem(v.stockCode, v.text),
    onSuccess: (_d, v) => inv(qk.homeChecklist, qk.board(v.stockCode)),
  });
}

export function useSetPriceTracking() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (v: { memoId: string; conditionId: string; tracking: boolean }) => api.setPriceConditionTracking(v.memoId, v.conditionId, v.tracking),
    onSuccess: () => inv(qk.priceConditions, qk.backtests),
  });
}

export function useConcludeMemo() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (v: { memoId: string; stockCode: string; conclusion: string }) => api.concludeMemo(v.memoId, v.conclusion),
    onSuccess: (_d, v) => inv(qk.journal, qk.board(v.stockCode), ...memoDependents),
  });
}

// ─── 휴지통 · 설정 · 데이터 ─────────────────────────────────
export const useTrash = (enabled = true) => useQuery({ queryKey: qk.trash, queryFn: api.listTrash, enabled });

export function useRestoreTrash() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.restoreTrash(id),
    onSuccess: () => qc.invalidateQueries(), // 복원 대상이 어디든 될 수 있어 전체 갱신
  });
}

export function usePurgeTrash() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (id: string) => api.purgeTrash(id), onSuccess: () => inv(qk.trash) });
}

export const useSettings = () => useQuery({ queryKey: qk.settings, queryFn: api.getSettings, staleTime: 5 * 60_000 });

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: DeepPartial<Settings>) => api.updateSettings(patch),
    onSuccess: (s) => qc.setQueryData(qk.settings, s),
  });
}

export function useDisconnectMcpApp() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: string) => api.disconnectMcpApp(id), onSuccess: (s) => qc.setQueryData(qk.settings, s) });
}

export const useAiStats = () => useQuery({ queryKey: qk.aiStats, queryFn: api.getAiStats });
/** 오늘의 퀴즈 — 하루 한 문제라 10분 동안은 다시 묻지 않음. 404(문제 없음)는 재시도하지 않음 */
export const useTodayQuiz = (enabled = true) =>
  useQuery({ queryKey: qk.todayQuiz, queryFn: api.getTodayQuiz, staleTime: 10 * 60_000, retry: false, enabled });
export const useUsage = () => useQuery({ queryKey: qk.usage, queryFn: api.getUsage });
/** 크레딧을 다 쓴 뒤 'AI 연결 모두 끄기' (2026-11-24). 끈 뒤 보드·메모·사용량을 모두 다시 받는다 */
export function useAiOffAll() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => api.aiOffAll(), onSuccess: () => qc.invalidateQueries() });
}
/** '지난 기간 사용량을 다 써서 N개가 꺼졌어요' 안내 확인 (2026-11-24) */
export function useAiOffNoticeSeen() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => api.aiOffNoticeSeen(), onSuccess: () => qc.invalidateQueries({ queryKey: qk.usage }) });
}
export const useDataStats = () => useQuery({ queryKey: qk.dataStats, queryFn: api.getDataStats });

export function useUpdateMe() {
  return useMutation({ mutationFn: (patch: Partial<Pick<User, 'name' | 'bio'>>) => api.updateMe(patch) });
}

export function useSendFeedback() {
  return useMutation({ mutationFn: (p: FeedbackPayload) => api.sendFeedback(p) });
}

/** 스튜디오 만든 항목 (GET /studio/items, 2026-11-23). 실제 모드·로그인 뒤에만 */
export const useStudioItems = (enabled = true) =>
  useQuery({ queryKey: qk.studioItems, queryFn: api.listStudioItems, staleTime: 60_000, enabled });

export function useDeleteStudioItem() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (id: string) => api.deleteStudioItem(id), onSuccess: () => inv(qk.studioItems) });
}

/** 설정 사용량 탭 종목별 추적 현황 (GET /ai/tracking, 2026-11-23) */
export const useAiTracking = (enabled = true) => useQuery({ queryKey: qk.aiTracking, queryFn: api.getAiTracking, enabled });
