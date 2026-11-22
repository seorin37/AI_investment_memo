/**
 * 실제 FastAPI 호출 구현. 경로는 docs/API_CONTRACT.md 와 동일합니다.
 * Base URL: EXPO_PUBLIC_API_BASE_URL (예: http://localhost:8000/api/v1)
 */
import { Platform } from 'react-native';
import { http } from './http';
import { createRealBoardApi } from './board';
import { createRealStockApi } from './stocks';
import type { Api } from './types';

export const realStockApi = createRealStockApi(http);
export const realBoardApi = createRealBoardApi(http);

export const realApi: Api = {
  // 인증
  refreshAuth: (refreshToken) => http.post('/auth/refresh', { refresh_token: refreshToken }),
  exchangeMobileAuth: (code, codeVerifier) =>
    http.post('/auth/mobile/exchange', { code, code_verifier: codeVerifier }),
  me: () => http.get('/auth/me'),
  updateMe: (patch) => http.patch('/me', patch),
  logout: (refreshToken) => http.post('/auth/logout', refreshToken ? { refresh_token: refreshToken } : undefined),
  getPopularStocks: (limit) => http.get('/stocks/popular', { limit }),
  getTerms: () => http.get('/me/terms'),
  agreeTerms: (items) => http.post('/me/terms', { items }),

  // 종목
  ...realStockApi,
  getQuote: (code) => http.get(`/stocks/${code}/quote`),
  getQuotes: (codes) => http.get('/quotes', { codes: codes.join(',') }),
  getCandles: (code, range) => http.get(`/stocks/${code}/candles`, { range }),
  getProfile: (code) => http.get(`/stocks/${code}/profile`),
  getFinancials: (code) => http.get(`/stocks/${code}/financials`),

  // 메모 보드
  ...realBoardApi,
  getMemoTimeline: (memoId) => http.get(`/memos/${memoId}/timeline`),
  listMemoAnswers: (memoId) => http.get(`/memos/${memoId}/answers`),
  listStockAiUpdates: (code) => http.get(`/stocks/${code}/ai-updates`),
  markAiUpdateRead: (id) => http.post(`/ai-updates/${id}/read`),
  async uploadFile(file) {
    const form = new FormData();
    if (Platform.OS === 'web' && file.file) form.append('file', file.file, file.name);
    else form.append('file', { uri: file.uri, name: file.name, type: file.mimeType ?? 'application/octet-stream' } as unknown as Blob);
    return http.upload('/files', form);
  },

  // 최신 업데이트
  listUpdates: (params) => http.get('/updates', params),

  // 투자 기록
  listJournal: () => http.get('/journal'),
  createJournal: (input) => http.post('/journal', input),
  updateJournal: (id, patch) => http.patch(`/journal/${id}`, patch),
  deleteJournal: (id) => http.del(`/journal/${id}`),

  // 홈
  getHomeLayout: () => http.get('/home/layout'),
  saveHomeLayout: (layout) => http.put('/home/layout', layout),
  getMarketOverview: () => http.get('/market/overview'),
  getMacro: () => http.get('/market/macro'),
  runLab: (input) => http.post('/studio/lab', input, { timeoutMs: 70_000 }),
  listCalendar: (month) => http.get('/calendar', { month }),
  createCalendarEvent: (input) => http.post('/calendar', input),
  listNews: () => http.get('/news/headlines'),
  getHomeNews: (limit) => http.get('/news/home', { limit }),
  listPinnedMemos: () => http.get('/memos/pinned'),
  listHomeChecklist: () => http.get('/checklist-items'),
  setChecklistItem: (checklistId, itemId, done) =>
    realBoardApi.setBoardChecklistItem(checklistId, itemId, done),
  addChecklistItem: (stockCode, text) => http.post('/checklist-items', { stock_code: stockCode, text }),
  listPriceConditions: () => http.get('/price-conditions'),
  setPriceConditionTracking: (memoId, conditionId, tracking) =>
    http.patch(`/memos/${memoId}/price-conditions/${conditionId}`, { tracking }),
  listMemoUpdateSummary: () => http.get('/ai-updates/summary'),
  listMemoBacktests: () => http.get('/insights/memo-backtest'),
  listCompareMemos: () => http.get('/insights/compare-memos'),
  listConcludeCandidates: () => http.get('/insights/conclude-candidates'),
  concludeMemo: (memoId, conclusion) => http.post(`/memos/${memoId}/conclude`, { conclusion }),

  // 휴지통 · 설정 · 데이터 · 피드백
  listTrash: () => http.get('/trash'),
  restoreTrash: (id) => http.post(`/trash/${id}/restore`),
  purgeTrash: (id) => http.del(`/trash/${id}`),
  getSettings: () => http.get('/settings'),
  updateSettings: (patch) => http.patch('/settings', patch),
  disconnectMcpApp: (appId) => http.del(`/mcp/apps/${appId}`),
  getAiStats: () => http.get('/ai/stats'),
  getUsage: () => http.get('/me/usage'),
  getTodayQuiz: () => http.get('/quiz/today'),
  getDataStats: () => http.get('/data/stats'),
  exportData: (format) => http.post('/data/export', { format }),
  deleteAllData: () => http.del('/data'),
  sendFeedback: (payload) => http.post('/feedback', payload),
};
