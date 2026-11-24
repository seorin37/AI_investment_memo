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
  /* 인증이 실제면 로그인 뒤 판별(약관 동의)도 실제 서버 기준 */
  getTerms: realApi.getTerms,
  agreeTerms: realApi.agreeTerms,
  ...(env.useRealStocks ? realStockApi : {}),
  ...(env.useRealBoard ? realBoardApi : {}),
};

/**
 * 백엔드 API를 아직 만들지 않은 기능(C그룹). USE_MOCK=false 여도 이 함수들만 mock 응답을 쓴다.
 * 백엔드에 생기면 여기서 빼면 real.ts 구현으로 바뀐다.
 */
const MOCK_ONLY = [
  // /insights/*
  'listMemoBacktests',
  'listCompareMemos',
  'listConcludeCandidates',
  // /memos/{id}/conclude — 결론을 저장할 칸이 아직 없다 (후보도 mock 이라 가짜 메모 id 로 불린다)
  'concludeMemo',
  // /calendar
  'listCalendar',
  'createCalendarEvent',
  // /data/* (getDataStats는 백엔드 있음, 2026-11-20)
  'exportData',
  'deleteAllData',
  // /mcp/*
  'disconnectMcpApp',
  // /files
  'uploadFile',
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
