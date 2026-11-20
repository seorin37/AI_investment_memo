import { env } from '@/config/env';
import { mockApi } from './mock';
import { realApi, realBoardApi, realStockApi } from './real';
import type { Api } from './types';

/**
 * Full mock remains the default. For incremental integration,
 * EXPO_PUBLIC_USE_REAL_STOCKS=true keeps non-stock domains mocked while
 * authentication and the six stock CRUD endpoints use FastAPI.
 * EXPO_PUBLIC_USE_REAL_BOARD=true does the same for memo-board CRUD.
 */
const hybridApi: Api = {
  ...mockApi,
  refreshAuth: realApi.refreshAuth,
  exchangeMobileAuth: realApi.exchangeMobileAuth,
  me: realApi.me,
  logout: realApi.logout,
  ...(env.useRealStocks ? realStockApi : {}),
  ...(env.useRealBoard ? realBoardApi : {}),
};

/**
 * 백엔드 API를 아직 만들지 않은 기능(C그룹). USE_MOCK=false 여도 이 함수들만 mock 응답을 쓴다.
 * 백엔드에 생기면 여기서 빼면 real.ts 구현으로 바뀐다.
 */
const MOCK_ONLY = [
  // 투자 기록 /journal
  'listJournal',
  'createJournal',
  'updateJournal',
  'deleteJournal',
  // /insights/*
  'listMemoBacktests',
  'listCompareMemos',
  'listConcludeCandidates',
  // /calendar
  'listCalendar',
  'createCalendarEvent',
  // /data/*
  'getDataStats',
  'exportData',
  'deleteAllData',
  // /feedback
  'sendFeedback',
  // /mcp/*
  'disconnectMcpApp',
  // /files
  'uploadFile',
  // /price-conditions, /memos/{id}/price-conditions/{id}
  'listPriceConditions',
  'setPriceConditionTracking',
  // /checklist-items
  'listHomeChecklist',
  'addChecklistItem',
  // /updates
  'listUpdates',
  // /ai/stats
  'getAiStats',
] as const satisfies readonly (keyof Api)[];

type MockOnlyKey = (typeof MOCK_ONLY)[number];

const mockOnlyApi = Object.fromEntries(MOCK_ONLY.map((key) => [key, mockApi[key]])) as Pick<Api, MockOnlyKey>;

const realWithMockGapsApi: Api = { ...realApi, ...mockOnlyApi };

export const api: Api = env.useMock
  ? env.useRealStocks || env.useRealBoard
    ? hybridApi
    : mockApi
  : realWithMockGapsApi;

export { ApiError, httpAuth } from './http';
export type * from './types';
