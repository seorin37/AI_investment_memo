/* API 모드(VITE_USE_API=true) 구현 — 실제 FastAPI(/api/v1)에 있는 것만 서버로, 나머지는 이 기기에 저장.
   서버: 로그인 세션(/auth) · 내 종목(/stocks) · 메모·체크리스트(/stocks/{code}/board, /board-items) · AI 연결(/memos/{id}/ai-link)
         · AI 업데이트 타임라인·읽음(/memos/{id}/timeline, /ai-updates/{id}/read)
   이 기기(localStorage, 사용자 id별): 투자 기록 · 휴지통 · 만든 항목 · 퀴즈 · 알림 · 설정 · 홈 위젯 · 프로필 수정 · 종목 순서 · 보드 카드 순서·메모 칸
   팀원 web/API.md의 /api/me/state · /api/market/* · /api/ai/* 는 백엔드에 없어 쓰지 않는다. */
import type { Checklist, Market, Memo, MyStock, Profile, StockInfo, TrackItem, UserState } from "./types";
import type { TLItem } from "./mock/ai";
import { emptyState } from "./mock/db";
import { api as server, type ChecklistWire, type MemoWire, type TimelineWire, type TrackingItemWire, type UserWire } from "./client";
import { ApiError, hasSessionCookie } from "./http";
import { createSync } from "./sync";
import { API_MODE } from "./config";

/* ---------- 화면에 알릴 일 (apimode.tsx ApiBridge가 받음) ---------- */
type Ev = { note: (text: string) => void; reload: () => void; change: () => void };
const subs: { [K in keyof Ev]: Set<Ev[K]> } = { note: new Set(), reload: new Set(), change: new Set() };
const pendingNotes: string[] = [];
export function onRemote<K extends keyof Ev>(k: K, f: Ev[K]) {
  (subs[k] as Set<Ev[K]>).add(f);
  if (k === "note") pendingNotes.splice(0).forEach((t) => (f as Ev["note"])(t));
  return () => { (subs[k] as Set<Ev[K]>).delete(f); };
}
const note = (text: string) => { if (subs.note.size) subs.note.forEach((f) => f(text)); else pendingNotes.push(text); };
const emit = (k: "reload" | "change") => subs[k].forEach((f) => f());

/* ---------- AI 업데이트 타임라인 캐시 (로컬 메모 id별) ---------- */
type TLCache = { items: TLItem[]; unread: string[]; tracks: TrackItem[] };
const tl = new Map<number, TLCache>();
const fmt = (iso: string) => { const d = new Date(iso), p = (n: number) => String(n).padStart(2, "0"); return `${d.getFullYear()}. ${p(d.getMonth() + 1)}. ${p(d.getDate())}. ${p(d.getHours())}:${p(d.getMinutes())}`; };
const KIND: Record<string, "공시" | "뉴스" | "주가"> = { news: "뉴스", disclosure: "공시", price: "주가" };
const rank = (x: TLItem) => (x.kind === "edit" ? 1 : x.kind === "start" ? 2 : x.kind === "first" ? 3 : 0);
export const toTrack = (i: TrackingItemWire): TrackItem => {
  const price = i.type === "price_below" || i.type === "price_above";
  return { k: i.id, t: i.description, d: price ? "가격 조건 · 전일 확정 종가로 확인해요" : "공시·뉴스에서 확인해요", tags: [i.type] };
};
function toCache(w: TimelineWire): TLCache {
  const items: TLItem[] = [], unread: string[] = [];
  for (const e of w.entries) {
    if (e.kind === "update") {
      const u = e.update, kind = KIND[u.type] ?? "뉴스";
      if (!u.read) unread.push(u.id);
      items.push({ kind, at: e.at, id: u.id, title: u.headline || u.title, body: u.summary ?? "", src: `${kind === "주가" ? "시세" : "출처"}  ${u.source || "—"} · ${fmt(u.published_at || e.at)}`, url: u.url ?? undefined });
    } else if (e.kind === "memo_created" || e.kind === "memo_edit") {
      items.push({ kind: e.kind === "memo_created" ? "first" : "edit", at: e.at, old: { title: e.version.title, body: e.version.body } });
    } else if (e.kind === "ai_linked") items.push({ kind: "start", at: e.at });
  }
  items.sort((a, b) => rank(a) - rank(b) || b.at.localeCompare(a.at));
  return { items, unread, tracks: (w.tracking_items ?? []).filter((i) => i.status === "active" || !i.status).map(toTrack) };
}
async function loadTimeline(localId: number, sid: string) {
  try { tl.set(localId, toCache(await server.timeline(sid))); } catch { /* 타임라인만 못 불러오면 기본 이력만 보여 줌 */ }
}

/* ---------- 종목 기본 정보 (서버 종목 마스터) — 가상 50종목 밖이면 이걸로 기본 로고 ---------- */
const masters = new Map<string, { name: string; market: string }>();
export function serverInfo(code: string): StockInfo | undefined {
  const m = masters.get(code); if (!m) return undefined;
  return { stock_code: code, name: m.name, market: (m.market === "KOSDAQ" ? "KOSDAQ" : "KOSPI") as Market, sector: "", logo: m.name.slice(0, 1) || "?", logo_bg: "#15171A", logo_ink: "#FFFFFF", financial: false, overview: "" };
}

/* ---------- 이 기기 저장 (사용자 id별) ---------- */
type Blob = { state: UserState; sids: Record<string, string> };
const KEY = (uid: string) => `memos.api.v1.u${uid}`;
const readBlob = (uid: string): Blob | null => { try { const v = localStorage.getItem(KEY(uid)); return v ? (JSON.parse(v) as Blob) : null; } catch { return null; } };
const writeBlob = (uid: string, b: Blob) => { try { localStorage.setItem(KEY(uid), JSON.stringify(b)); } catch { /* 가득 참 — 이번 저장만 건너뜀 */ } };

let uid: string | null = null;
const starting = new Map<number, Promise<unknown>>();
const sync = createSync({
  onError: (msg) => { note(`저장하지 못했어요 · ${msg} · 서버에 있는 내용으로 다시 불러올게요`); emit("reload"); },
  unreadOf: (id) => tl.get(id)?.unread ?? [],
  markedRead: (id) => { const c = tl.get(id); if (c) c.unread = []; },
});
if (API_MODE && typeof window !== "undefined") window.addEventListener("pagehide", () => sync.flush());

const providerOf = (u: UserWire): Profile["provider"] | null => {
  const list = Array.isArray(u.providers) ? (u.providers as { provider?: string; current?: boolean }[]) : [];
  const p = (list.find((x) => x.current) ?? list[0])?.provider;
  return p === "kakao" || p === "naver" || p === "google" ? p : null;
};
const str = (v: unknown) => (typeof v === "string" ? v.trim() : "");

/* 소셜 로그인에서 돌아온 주소(?status= · ?error=) 정리 + 실패 안내 */
function takeReturnParams() {
  const q = new URLSearchParams(window.location.search);
  if (!q.has("status") && !q.has("error")) return;
  if (q.get("error")) note("로그인하지 못했어요 · 다시 시도해 주세요");
  window.history.replaceState(null, "", window.location.pathname);
}

async function load(me: UserWire): Promise<UserState> {
  const id = String(me.id);
  const blob = readBlob(id);
  const base = blob?.state ?? emptyState(null);
  const oldBySid = new Map<string, Memo>();
  if (blob) for (const m of base.memos) { const s = blob.sids[String(m.id)]; if (s) oldBySid.set(s, m); }

  const mine = await server.myStocks();
  mine.forEach((s) => masters.set(s.code.trim(), { name: s.name, market: s.market }));
  const boards = await Promise.all(mine.map((s) => server.board(s.code.trim())));
  const order = new Map(base.stocks.map((s) => [s.stock_code, s.order] as const));
  const stocks: MyStock[] = mine.map((s, i): MyStock => ({ stock_code: s.code.trim(), hold: s.status === "holding" ? "보유" : "관심", added_at: s.added_at, order: order.get(s.code.trim()) ?? 1000 + i }))
    .sort((a, b) => a.order - b.order).map((s, i) => ({ ...s, order: i }));

  const memos: Memo[] = [], checklists: Record<string, Checklist> = {};
  const ids = { memos: new Map<number, string>(), checks: new Map<string, ChecklistWire>() };
  const remap = new Map<string, string>(); // 보드 카드 순서의 이전 로컬 id → 서버 id
  boards.forEach((rows, si) => {
    const code = mine[si].code.trim();
    rows.filter((r): r is MemoWire => r.kind === "memo").forEach((w, j) => {
      const nid = Number(w.id), old = oldBySid.get(w.id);
      if (old) remap.set("m" + old.id, "m" + nid);
      memos.push({ id: nid, stock_code: code, title: w.title, body: w.body, color: w.color, created_at: w.created_at, updated_at: w.updated_at,
        ai: w.ai_linked, ai_since: w.ai_linked_at ?? undefined, pinned: w.pinned, pinned_at: old?.pinned_at, col: old?.col ?? j % 3, seen_at: old?.seen_at, edits: [] });
      ids.memos.set(nid, w.id);
    });
    const cl = rows.find((r): r is ChecklistWire => r.kind === "checklist"); // 보드에는 체크리스트 하나만 (종목마다)
    if (cl) { checklists[code] = { stock_code: code, title: cl.title, items: cl.items.map((x, n) => ({ id: n + 1, t: x.text, d: x.done })), updated_at: cl.updated_at }; ids.checks.set(code, cl); }
  });
  tl.clear();
  await Promise.all(memos.filter((m) => m.ai).map((m) => loadTimeline(m.id, ids.memos.get(m.id)!)));
  for (const m of memos) { const c = tl.get(m.id); if (c?.tracks.length) m.tracks = c.tracks; }

  const boardsOrder: Record<string, string[]> = {};
  for (const [code, list] of Object.entries(base.boards ?? {})) boardsOrder[code] = (list as string[]).map((k) => (k === "cl" ? k : remap.get(k) ?? "")).filter(Boolean);

  const prev = base.profile;
  const profile: Profile = {
    name: prev?.name || str(me.name) || str(me.email).split("@")[0] || "내 계정",
    job: prev?.job ?? str(me.bio), email: str(me.email) || prev?.email || "",
    provider: providerOf(me) ?? prev?.provider ?? "kakao", photo: prev?.photo ?? (str(me.avatar_url) || undefined),
    joined_at: prev?.joined_at ?? new Date().toISOString(),
  };
  const state: UserState = { ...base, profile, stocks, memos, checklists, boards: boardsOrder, onboarded: base.onboarded || stocks.length > 0 };
  uid = id;
  sync.reset(state, ids);
  return state;
}

/* ---------- api/index.ts가 쓰는 함수 ---------- */
export const remote = {
  async session(): Promise<UserState | null> {
    takeReturnParams();
    if (!hasSessionCookie()) { uid = null; return null; }
    try { return await load(await server.me()); }
    catch (e) {
      uid = null;
      if (!(e instanceof ApiError && e.status === 401)) note(`서버에서 불러오지 못했어요 · ${e instanceof Error ? e.message : ""}`);
      return null;
    }
  },
  /* 백엔드 소셜 로그인 페이지로 이동. 돌아오면 첫 실행의 session()이 이어받는다 */
  login(p: Profile["provider"]): Promise<{ state: UserState; is_new: boolean }> {
    window.location.assign(server.loginUrl(p, window.location.origin + window.location.pathname));
    return new Promise(() => {});
  },
  async logout() { sync.flush(); try { await server.logout(); } catch { /* 이미 끊긴 세션 */ } uid = null; tl.clear(); },
  save(s: UserState) {
    if (!uid || !s.profile) return;
    sync.apply(s);
    writeBlob(uid, { state: s, sids: Object.fromEntries([...sync.sids()].map(([k, v]) => [String(k), v])) });
  },
  async search(q: string): Promise<{ stock_code: string; name: string; market: string }[]> {
    const r = await server.searchStocks(q);
    r.forEach((x) => masters.set(x.code.trim(), { name: x.name, market: x.market }));
    return r.map((x) => ({ stock_code: x.code.trim(), name: x.name, market: x.market }));
  },
  /* AI 연결 창: 켜면 서버가 메모를 분석해 추적 항목을 만든다. 창이 닫힐 때 linkEnd(켜둠/끔) */
  linkStart(localId: number): Promise<{ status: string; items: TrackItem[]; error?: string | null }> {
    sync.hold(localId);
    const p = (async () => {
      try {
        const sid = await sync.waitSid(localId);
        const w = await server.setAiLink(sid, true);
        const a = w.analysis;
        return { status: a?.status ?? "done", items: (a?.items ?? []).map(toTrack), error: a?.error ?? null };
      } catch (e) { sync.release(localId, false); throw e; }
    })();
    starting.set(localId, p);
    return p;
  },
  async linkEnd(localId: number, keep: boolean) {
    /* 켜는 요청이 아직 가는 중이면 끝난 뒤에 끈다 (순서가 뒤집히지 않게) */
    const p = starting.get(localId); starting.delete(localId);
    if (p) { try { await p; } catch { return; /* 켜기 자체가 실패 → 이미 꺼진 상태 */ } }
    if (keep) {
      sync.release(localId, true);
      const sid = sync.memoSid(localId);
      if (sid) void loadTimeline(localId, sid).then(() => emit("change"));
      return;
    }
    try { const sid = sync.memoSid(localId); if (sid) await server.setAiLink(sid, false); }
    catch (e) { note(`AI 연결을 끄지 못했어요 · ${e instanceof Error ? e.message : ""}`); emit("reload"); }
    finally { sync.release(localId, false); }
  },
  timeline(m: Memo): TLItem[] {
    const c = tl.get(m.id);
    if (c && m.ai) return c.items;
    const out: TLItem[] = [{ kind: "first", at: m.created_at, old: { title: m.title, body: m.body } }];
    if (m.ai && m.ai_since) out.unshift({ kind: "start", at: m.ai_since });
    return out;
  },
  unseen: (m: Memo) => (m.ai ? tl.get(m.id)?.unread.length ?? 0 : 0),
};
