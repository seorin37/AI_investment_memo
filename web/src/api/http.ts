/* FastAPI HTTP 클라이언트 — frontend/src/api/http.ts(Expo 앱)의 웹 쿠키 방식을 그대로 옮김.
   - 로그인 세션은 백엔드가 심은 httpOnly 쿠키(memos_access · memos_refresh)로만 다룬다. 토큰을 JS에 저장하지 않는다.
   - 쓰기 요청에는 memos_csrf 쿠키 값을 X-CSRF-Token 머리말로 같이 보낸다 (backend/app/main.py 이중 제출 검사).
   - 401이면 /auth/refresh 로 한 번만 세션을 이어 받고 다시 시도한다.
   - FastAPI 오류 형식 { detail: string | [{ msg }] } 를 읽어 ApiError로 던진다. */
import { API_BASE } from "./config";

export class ApiError extends Error {
  status: number;
  body?: unknown;
  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
type Query = Record<string, string | number | boolean | undefined | null>;

function url(path: string, query?: Query) {
  const u = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  if (!query) return u;
  const qs = Object.entries(query)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");
  return qs ? `${u}?${qs}` : u;
}

function csrf(): string | null {
  const part = document.cookie.split("; ").find((p) => p.startsWith("memos_csrf="));
  return part ? decodeURIComponent(part.slice("memos_csrf=".length)) : null;
}

function detail(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d[0] && typeof d[0] === "object" && "msg" in d[0]) return String((d[0] as { msg: unknown }).msg);
  }
  return fallback;
}

/* 로그인 세션 흔적: memos_csrf 는 세션 쿠키와 함께 심기고 refresh 토큰과 수명이 같은, JS가 읽을 수 있는 유일한 쿠키.
   없으면 로그인한 적이 없거나 세션이 끝난 것 → /auth/me · /auth/refresh 를 부르지 않는다 (불필요한 401 줄이기) */
export const hasSessionCookie = () => csrf() !== null;

let refreshing: Promise<boolean> | null = null;
/* 동시에 여러 요청이 401을 받아도 refresh는 한 번만 */
function refreshOnce(): Promise<boolean> {
  if (!hasSessionCookie()) return Promise.resolve(false);
  if (!refreshing) {
    refreshing = send("POST", "/auth/refresh", { body: {}, retried: true })
      .then(() => true, () => false)
      .finally(() => { refreshing = null; });
  }
  return refreshing;
}

async function send<T>(method: Method, path: string, opt: { query?: Query; body?: unknown; retried?: boolean; timeoutMs?: number; keepalive?: boolean } = {}): Promise<T> {
  const ctl = new AbortController();
  const timer = window.setTimeout(() => ctl.abort(), opt.timeoutMs ?? 15_000);
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") { const c = csrf(); if (c) headers["X-CSRF-Token"] = c; }
  let body: string | undefined;
  if (opt.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opt.body); }
  let res: Response;
  try {
    res = await fetch(url(path, opt.query), { method, headers, body, credentials: "include", signal: ctl.signal, keepalive: opt.keepalive });
  } catch (e) {
    const aborted = e instanceof Error && e.name === "AbortError";
    throw new ApiError(0, aborted ? "서버 응답이 늦어요. 잠시 후 다시 시도해 주세요." : "서버에 연결할 수 없어요. API 주소와 서버 실행 상태를 확인해 주세요.");
  } finally {
    window.clearTimeout(timer);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let parsed: unknown = undefined;
  if (text) { try { parsed = JSON.parse(text); } catch { parsed = text; } }
  if (!res.ok) {
    const isAuth = path.startsWith("/auth/refresh") || path.startsWith("/auth/logout");
    if (res.status === 401 && !opt.retried && !isAuth && (await refreshOnce())) return send<T>(method, path, { ...opt, retried: true });
    throw new ApiError(res.status, detail(parsed, `요청을 처리하지 못했어요 (${res.status})`), parsed);
  }
  return parsed as T;
}

export const http = {
  get: <T>(path: string, query?: Query) => send<T>("GET", path, { query }),
  post: <T>(path: string, body?: unknown) => send<T>("POST", path, { body }),
  put: <T>(path: string, body?: unknown) => send<T>("PUT", path, { body }),
  patch: <T>(path: string, body?: unknown) => send<T>("PATCH", path, { body }),
  /* keepalive: 페이지를 닫는 중에도 보내야 하는 삭제 */
  del: <T = void>(path: string, keepalive = false) => send<T>("DELETE", path, { keepalive }),
};
export const apiUrl = url;
