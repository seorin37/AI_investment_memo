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

export const api: Api = env.useMock
  ? env.useRealStocks || env.useRealBoard
    ? hybridApi
    : mockApi
  : realApi;

export { ApiError, httpAuth } from './http';
export type * from './types';
