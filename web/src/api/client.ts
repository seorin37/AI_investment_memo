/* 실제로 구현된 FastAPI 엔드포인트만 (backend/app/{auth,stocks,board,updates}/routes.py). 없는 API는 여기 두지 않는다. */
import { http, apiUrl } from "./http";

/* ---------- 응답 모양 (backend …/schemas.py · updates/service.py 그대로) ---------- */
export type StockStatus = "holding" | "watching";
export type StockMasterWire = { code: string; name: string; market: "KOSPI" | "KOSDAQ" | "KONEX" };
export type MyStockWire = StockMasterWire & { status: StockStatus; tags: string[] | null; unread_updates: number | null; added_at: string };
export type MemoColorWire = "yellow" | "blue" | "pink" | "green" | "purple";
type BoardBase = { id: string; stock_code: string; title: string; position: number; created_at: string; updated_at: string };
export type MemoWire = BoardBase & { kind: "memo"; body: string; tags: string[]; color: MemoColorWire; pinned: boolean; ai_linked: boolean; ai_linked_at: string | null; unread_updates: number };
export type ChecklistWire = BoardBase & { kind: "checklist"; items: { id: string; text: string; done: boolean }[] };
export type ReferenceWire = BoardBase & { kind: "reference"; links: { id: string; title: string; url: string; ref_type: string; source: string }[] };
export type BoardWire = MemoWire | ChecklistWire | ReferenceWire;
export type AiUpdateWire = {
  id: string; stock_code: string; type: "news" | "disclosure" | "price" | string; title: string; headline?: string | null; summary?: string | null;
  source: string; url: string | null; published_at: string | null; created_at: string; memo_id: string; read: boolean;
};
export type TimelineEntryWire =
  | { kind: "update"; at: string; update: AiUpdateWire }
  | { kind: "memo_created" | "memo_edit"; at: string; version: { version: number; title: string; body: string; saved_at: string } }
  | { kind: "ai_linked"; at: string };
export type TimelineWire = { memo_id: string; entries: TimelineEntryWire[]; tracking_items: { id: string; type: string; description: string; status: string }[] };
/* /auth/me 실제 응답: { id, name, bio, avatar_url, email, providers: [{ provider, email, connected, current }], … } */
export type UserWire = { id: number | string; name?: string | null; bio?: string | null; email?: string | null; [k: string]: unknown };
export type Provider = "kakao" | "naver" | "google";

export const api = {
  /* 인증 (쿠키 세션) */
  loginUrl: (p: Provider, returnTo: string) => apiUrl(`/auth/${p}/start`, { client: "web", return_to: returnTo }),
  me: () => http.get<UserWire>("/auth/me"),
  logout: () => http.post<void>("/auth/logout"),

  /* 종목 */
  myStocks: () => http.get<MyStockWire[]>("/stocks"),
  searchStocks: (q: string) => http.get<StockMasterWire[]>("/stocks/search", { q }),
  addStock: (code: string, status: StockStatus) => http.post<MyStockWire>("/stocks", { code, status }),
  setStockStatus: (code: string, status: StockStatus) => http.patch<MyStockWire>(`/stocks/${code}`, { status }),
  removeStock: (code: string, keepalive = false) => http.del(`/stocks/${code}`, keepalive),

  /* 메모 보드 (메모 · 체크리스트) */
  board: (code: string) => http.get<BoardWire[]>(`/stocks/${code}/board`),
  createMemo: (code: string, b: { title: string; body: string; color: MemoColorWire; pinned: boolean; ai_linked: boolean }) => http.post<MemoWire>(`/stocks/${code}/memos`, b),
  createChecklist: (code: string, b: { title: string; items: { text: string; done: boolean }[] }) => http.post<ChecklistWire>(`/stocks/${code}/checklists`, b),
  patchItem: <T extends BoardWire>(id: string, b: Record<string, unknown>) => http.patch<T>(`/board-items/${id}`, b),
  patchChecklistItem: (id: string, itemId: string, done: boolean) => http.patch<ChecklistWire>(`/checklists/${id}/items/${itemId}`, { done }),
  setAiLink: (id: string, enabled: boolean) => http.put<MemoWire>(`/memos/${id}/ai-link`, { enabled }),
  deleteItem: (id: string, keepalive = false) => http.del(`/board-items/${id}`, keepalive),

  /* AI 업데이트 */
  timeline: (memoId: string) => http.get<TimelineWire>(`/memos/${memoId}/timeline`),
  markRead: (updateId: string) => http.post<void>(`/ai-updates/${updateId}/read`),
};
