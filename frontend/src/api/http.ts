/**
 * FastAPI HTTP 클라이언트 (fetch 기반).
 * - Authorization: Bearer <JWT>
 * - FastAPI 기본 에러 형식 { detail: string | [{msg}] } 파싱
 * - 401 → 세션 만료 처리(onUnauthorized 콜백)
 */
import { env } from '@/config/env';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

type Query = Record<string, string | number | boolean | undefined | null>;

let accessToken: string | null = null;
let refreshSession: (() => Promise<boolean>) | null = null;

export const httpAuth = {
  setToken(token: string | null) {
    accessToken = token;
  },
  getToken() {
    return accessToken;
  },
  setRefreshHandler(fn: () => Promise<boolean>) {
    refreshSession = fn;
  },
};

function buildUrl(path: string, query?: Query) {
  const url = `${env.apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}`;
  if (!query) return url;
  const qs = Object.entries(query)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&');
  return qs ? `${url}?${qs}` : url;
}

function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d) && d[0] && typeof d[0] === 'object' && 'msg' in d[0]) return String((d[0] as { msg: unknown }).msg);
  }
  return fallback;
}

export async function request<T>(
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  opts: { query?: Query; body?: unknown; form?: FormData; timeoutMs?: number; authRetried?: boolean } = {},
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs ?? 15_000);
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (method !== 'GET' && typeof document !== 'undefined') {
    const csrf = document.cookie
      .split('; ')
      .find((part) => part.startsWith('memos_csrf='))
      ?.split('=', 2)[1];
    if (csrf) headers['X-CSRF-Token'] = decodeURIComponent(csrf);
  }
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }

  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method,
      headers,
      body,
      signal: controller.signal,
      credentials: 'include',
    });
  } catch (e) {
    clearTimeout(timer);
    const aborted = e instanceof Error && e.name === 'AbortError';
    throw new ApiError(0, aborted ? '서버 응답이 늦어요. 잠시 후 다시 시도해 주세요.' : '서버에 연결할 수 없어요. API 주소와 네트워크를 확인해 주세요.');
  }
  clearTimeout(timer);

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const parsed = text ? safeJson(text) : undefined;

  if (!res.ok) {
    const isAuthEndpoint = path === '/auth/refresh' || path === '/auth/mobile/exchange';
    if (res.status === 401 && !opts.authRetried && !isAuthEndpoint && refreshSession && (await refreshSession())) {
      return request<T>(method, path, { ...opts, authRetried: true });
    }
    throw new ApiError(res.status, errorMessage(parsed, `요청을 처리하지 못했어요 (${res.status})`), parsed);
  }
  return parsed as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export const http = {
  get: <T>(path: string, query?: Query) => request<T>('GET', path, { query }),
  post: <T>(path: string, body?: unknown, opts?: { timeoutMs?: number }) => request<T>('POST', path, { body, ...opts }),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, { body }),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, { body }),
  del: <T = void>(path: string) => request<T>('DELETE', path),
  upload: <T>(path: string, form: FormData) => request<T>('POST', path, { form, timeoutMs: 60_000 }),
};
