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
  quote: (code: string) => ['quote', code] as const,
  candles: (code: string, range: ChartRange) => ['candles', code, range] as const,
  profile: (code: string) => ['profile', code] as const,
  financials: (code: string) => ['financials', code] as const,
  board: (code: string) => ['board', code] as const,
  timeline: (memoId: string) => ['timeline', memoId] as const,
  stockAiUpdates: (code: string) => ['stockAiUpdates', code] as const,
  updates: (code?: string) => ['updates', code ?? 'all'] as const,
  journal: ['journal'] as const,
  homeLayout: ['homeLayout'] as const,
  market: ['market'] as const,
  calendar: (month: string) => ['calendar', month] as const,
  news: ['news'] as const,
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
  dataStats: ['dataStats'] as const,
};

/** 메모/보드가 바뀌면 함께 갱신해야 하는 홈 위젯 키 */
const memoDependents = [qk.pinned, qk.homeChecklist, qk.priceConditions, qk.memoUpdateSummary, qk.backtests, qk.compare, qk.conclude, qk.aiStats, qk.dataStats];

function useInvalidate() {
  const qc = useQueryClient();
  return (...keys: readonly (readonly unknown[])[]) => Promise.all(keys.map((queryKey) => qc.invalidateQueries({ queryKey })));
}

// ─── 종목 ────────────────────────────────────────────────────
export const useMyStocks = () => useQuery({ queryKey: qk.stocks, queryFn: api.listMyStocks });

export const useStockSearch = (q: string) =>
  useQuery({ queryKey: qk.stockSearch(q), queryFn: () => api.searchStocks(q), enabled: q.trim().length > 0, placeholderData: keepPreviousData });

export const useQuote = (code: string) => useQuery({ queryKey: qk.quote(code), queryFn: () => api.getQuote(code), refetchInterval: 60_000 });

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
  const inv = useInvalidate();
  return useMutation({ mutationFn: (id: string) => api.deleteBoardItem(id), onSuccess: () => inv(qk.board(code), qk.trash, ...memoDependents) });
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
    onSettled: (_d, _e, v) => inv(qk.board(code), qk.timeline(v.memoId), qk.stockAiUpdates(code), ...memoDependents),
  });
}

export function useMarkAiUpdateRead(code?: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api.markAiUpdateRead(id),
    onSuccess: () => inv(qk.stocks, qk.memoUpdateSummary, ...(code ? [qk.stockAiUpdates(code), qk.board(code)] : [])),
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

export const useMarketOverview = () => useQuery({ queryKey: qk.market, queryFn: api.getMarketOverview, refetchInterval: 60_000 });
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
export const useDataStats = () => useQuery({ queryKey: qk.dataStats, queryFn: api.getDataStats });

export function useUpdateMe() {
  return useMutation({ mutationFn: (patch: Partial<Pick<User, 'name' | 'bio'>>) => api.updateMe(patch) });
}

export function useSendFeedback() {
  return useMutation({ mutationFn: (p: FeedbackPayload) => api.sendFeedback(p) });
}
