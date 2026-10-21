/**
 * 실제 FastAPI 호출 구현. 경로는 docs/API_CONTRACT.md 와 동일합니다.
 * Base URL: EXPO_PUBLIC_API_BASE_URL (예: http://localhost:8000/api/v1)
 */
import { Platform } from 'react-native';
import { http } from './http';
import type { Api } from './types';

export const realApi: Api = {
  // 인증
  loginEmail: (email, password) => http.post('/auth/email/login', { email, password }),
  signupEmail: (name, email, password) => http.post('/auth/email/signup', { name, email, password }),
  me: () => http.get('/me'),
  updateMe: (patch) => http.patch('/me', patch),
  logout: () => http.post('/auth/logout'),

  // 종목
  listMyStocks: () => http.get('/stocks'),
  searchStocks: (q) => http.get('/stocks/search', { q }),
  addStock: (code, status) => http.post('/stocks', { code, status }),
  updateStock: (code, patch) => http.patch(`/stocks/${code}`, patch),
  removeStock: (code) => http.del(`/stocks/${code}`),
  getQuote: (code) => http.get(`/stocks/${code}/quote`),
  getCandles: (code, range) => http.get(`/stocks/${code}/candles`, { range }),
  getProfile: (code) => http.get(`/stocks/${code}/profile`),
  getFinancials: (code) => http.get(`/stocks/${code}/financials`),

  // 메모 보드
  listBoard: (code) => http.get(`/stocks/${code}/board`),
  createMemo: (code, input) => http.post(`/stocks/${code}/memos`, input),
  createChecklist: (code, input) => http.post(`/stocks/${code}/checklists`, input),
  createReference: (code, input) => http.post(`/stocks/${code}/references`, input),
  updateBoardItem: (id, patch) => http.patch(`/board-items/${id}`, patch),
  deleteBoardItem: (id) => http.del(`/board-items/${id}`),
  setAiLink: (memoId, enabled) => http.put(`/memos/${memoId}/ai-link`, { enabled }),
  getMemoTimeline: (memoId) => http.get(`/memos/${memoId}/timeline`),
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
  listCalendar: (month) => http.get('/calendar', { month }),
  createCalendarEvent: (input) => http.post('/calendar', input),
  listNews: () => http.get('/news/headlines'),
  listPinnedMemos: () => http.get('/memos/pinned'),
  listHomeChecklist: () => http.get('/checklist-items'),
  setChecklistItem: (checklistId, itemId, done) => http.patch(`/checklists/${checklistId}/items/${itemId}`, { done }),
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
  getDataStats: () => http.get('/data/stats'),
  exportData: (format) => http.post('/data/export', { format }),
  deleteAllData: () => http.del('/data'),
  sendFeedback: (payload) => http.post('/feedback', payload),
};
