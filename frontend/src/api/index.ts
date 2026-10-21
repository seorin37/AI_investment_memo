import { env } from '@/config/env';
import { mockApi } from './mock';
import { realApi } from './real';
import type { Api } from './types';

/** EXPO_PUBLIC_USE_MOCK=true → 메모리 목업, false → FastAPI */
export const api: Api = env.useMock ? mockApi : realApi;

export { ApiError, httpAuth } from './http';
export type * from './types';
