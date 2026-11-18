import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { ALL_STOCKS, MEMOS, JOURNAL, TRASH, CHECKLIST, type Stock, type Memo, type Journal, type TrashItem } from "./data";
import { API_MODE } from "./api/config";
import { api, type ChecklistWire, type MemoWire, type UserWire } from "./api/client";
import { toChecklist, toMemo, toStock, toTimeline, type BoardChecklist } from "./api/map";
import { createSync, type Sync } from "./api/sync";
import { hasSessionCookie } from "./api/http";

export type Route =
  | { name: "intro" } | { name: "login" } | { name: "terms" } | { name: "pick" } | { name: "start" } | { name: "home" } | { name: "custom" }
  | { name: "updates"; code?: string } | { name: "journal" } | { name: "stock"; code: string; tab: "board" | "info" }
  | { name: "help" } | { name: "report" } | { name: "mine" };
export type Overlay = null | "addStock" | "settings" | "feedback" | "trash" | "audio" | "reportPick" | "credit" | "charge" | "logout";

export type SView = "home" | "gen" | "fail" | "ranOut" | "player" | "quiz" | "report" | "lab" | "labResult";
export type JobKind = "audio" | "report" | "lab";
export type Made = { id: number; kind: JobKind; title: string; meta: string; when: string; left: string };
export type Studio = {
  open: boolean; view: SView; dir: "push" | "pop";
  job: null | { kind: JobKind; title: string; meta: string; step: number; pct: number };
  lastJob?: { title: string; meta: string }; failKind?: JobKind; done?: JobKind | null; badge?: string | null;
  made: Made[]; creditOut: boolean; mini: boolean; playing: boolean; t: number; speed: number;
  quizDone: null | { correct: boolean; picked: string }; labStock: string; labVars: Record<string, string>;
};
/* v2 (11.14 멘토링 반영): 첫 진입 코치마크 · 스튜디오 넛지 · 팝업 미리 고르기 */
export type Coach = null | { step: number };
export type NudgeId = "memo" | "updates" | "info" | "lab" | "home";
export type Preset = null | { codes?: string[]; newMemo?: string };
export type WItem = { id: string; x: number; y: number; w: number; h: number };
/* 11.16 앱 통일: 앱에 있던 상태들 (알림함 · 읽음 · 수정 이력 · 끊김 · 사용량 등) */
export type Notif = { id: number; kind: "upd" | "studio"; t: string; s: string; when: string; read: boolean; code?: string; memo?: number; view?: SView };
export type Hist = { at: string; title: string; body: string };
export type Ext = {
  offline: boolean; widgetFail: boolean; usage: number; noti: { upd: boolean; studio: boolean };
  notifs: Notif[]; inbox: boolean; read: Record<string, boolean>; hist: Record<number, Hist[]>;
  recent: string[]; seen: Record<string, boolean>; homeEdit: boolean; market: string | null; first: boolean; memoTab: number; homeW: string[]; loginFail: boolean; firstStep: number;
};
export const INITIAL_EXT: Ext = {
  offline: false, widgetFail: false, usage: 62, noti: { upd: true, studio: true }, inbox: false, read: {}, hist: {}, recent: ["SK하이닉스", "삼성전자"], seen: {}, homeEdit: false, market: null, first: false, memoTab: 0, loginFail: false, firstStep: 0, homeW: ["market", "updates", "news"],
  notifs: [
    { id: 1, kind: "upd", t: "SK하이닉스 · 실적 나오면 다시 보기", s: "메모에 새 소식이 연결됐어요 · HBM4 공급 확대", when: "10분 전", read: false, code: "000660", memo: 1 },
    { id: 2, kind: "studio", t: "내 종목 라디오가 다 만들어졌어요", s: "오디오 · 6:42 · 눌러서 듣기", when: "1시간 전", read: false, view: "player" },
    { id: 3, kind: "upd", t: "SK하이닉스 · 15만원 밑으로 오면 다시 생각", s: "가격 조건 소식이 연결됐어요 · 전일 확정 종가 기준", when: "장 마감 후", read: false, code: "000660", memo: 3 },
    { id: 4, kind: "upd", t: "삼성전자 · 자사주 매입 나오면 다시 보기", s: "메모에 새 공시가 연결됐어요 · 자기주식 취득 결정", when: "어제", read: true, code: "005930", memo: 6 },
    { id: 5, kind: "studio", t: "이번 주 내 종목 보고서가 다 만들어졌어요", s: "주간보고서 · 3종목", when: "11.02", read: true, view: "report" },
  ],
};
export type Demo = { fail: boolean; ranOut: boolean; quizLocked: boolean; quiz4: boolean; noNews: boolean; short: boolean; speed: "1" | "2.5" | ".01" };

type Ctx = {
  route: Route; go: (r: Route) => void; nav: number;
  stocks: Stock[]; setStocks: React.Dispatch<React.SetStateAction<Stock[]>>;
  memos: Memo[]; setMemos: React.Dispatch<React.SetStateAction<Memo[]>>;
  journal: Journal[]; setJournal: React.Dispatch<React.SetStateAction<Journal[]>>;
  trash: TrashItem[]; setTrash: React.Dispatch<React.SetStateAction<TrashItem[]>>;
  checklist: typeof CHECKLIST; setChecklist: React.Dispatch<React.SetStateAction<typeof CHECKLIST>>; clTitle: string; setClTitle: (v: string) => void;
  overlay: Overlay; setOverlay: (o: Overlay) => void; settingsTab: string; openSettings: (tab?: string) => void;
  homeMode: "template" | "custom"; setHomeMode: (m: "template" | "custom") => void;
  widgets: string[]; setWidgets: React.Dispatch<React.SetStateAction<string[]>>;
  board: WItem[]; setBoard: React.Dispatch<React.SetStateAction<WItem[]>>;
  newsCount: number; setNewsCount: React.Dispatch<React.SetStateAction<number>>;
  studio: Studio; setStudio: React.Dispatch<React.SetStateAction<Studio>>; sgo: (v: SView, dir?: "push" | "pop") => void;
  demo: Demo; setDemo: React.Dispatch<React.SetStateAction<Demo>>;
  sideOpen: boolean; setSideOpen: (v: boolean) => void;
  memoOpen: number | null; setMemoOpen: (v: number | null) => void;
  flash: number | null; setFlash: (v: number | null) => void;
  coach: Coach; setCoach: React.Dispatch<React.SetStateAction<Coach>>; coachPending: boolean; setCoachPending: (v: boolean) => void; coachDone: boolean; setCoachDone: (v: boolean) => void;
  nudgeOff: Partial<Record<NudgeId, boolean>>; hideNudge: (id: NudgeId) => void; resetNudges: () => void; nudgeAsk: NudgeId | null; askNudge: (id: NudgeId | null) => void;
  preset: Preset; setPreset: (p: Preset) => void;
  planOpen: boolean; setPlanOpen: (v: boolean) => void;
  x: Ext; setX: React.Dispatch<React.SetStateAction<Ext>>;
  reset: () => void;
  /* API 모드 (VITE_USE_API=true) 전용. 시연 모드에서는 auth="demo"이고 나머지는 쓰지 않는다 */
  auth: AuthState; user: UserWire | null; authError: string | null;
  checks: Record<string, BoardChecklist>; setChecks: React.Dispatch<React.SetStateAction<Record<string, BoardChecklist>>>;
  loadTimeline: (memoId: number) => void;
  apiNote: ApiNote; reload: () => void;
};
export type AuthState = "demo" | "checking" | "loading" | "out" | "in";
export type ApiNote = null | { key: number; text: string };
const C = createContext<Ctx>(null as unknown as Ctx);
export const useApp = () => useContext(C);

/* 프로필 표시: 시연 모드는 Figma 예시(김나라), API 모드는 로그인한 사용자 (/auth/me) */
export function useProfile() {
  const { user } = useApp();
  if (!API_MODE) return { name: "김나라", sub: "대학생", email: "nara@gmail.com" };
  const s = (k: string) => (typeof user?.[k] === "string" ? (user[k] as string).trim() : "");
  return { name: s("name") || s("display_name") || s("email").split("@")[0] || "내 계정", sub: s("bio"), email: s("email") };
}

/* 보드 체크리스트: 시연 모드는 지금처럼 하나(전역), API 모드는 종목마다 서버 체크리스트 하나 */
type CheckRow = { t: string; d: boolean };
export function useChecklist(code: string) {
  const app = useApp();
  if (!API_MODE) return { checklist: app.checklist, setChecklist: app.setChecklist, clTitle: app.clTitle, setClTitle: app.setClTitle, has: code === "000660" };
  const c = app.checks[code];
  const setChecklist = (v: React.SetStateAction<CheckRow[]>) => app.setChecks((all) => {
    const cur = all[code] ?? { title: "체크리스트", items: [] };
    return { ...all, [code]: { ...cur, items: typeof v === "function" ? v(cur.items) : v } };
  });
  const setClTitle = (title: string) => app.setChecks((all) => ({ ...all, [code]: { ...(all[code] ?? { items: [] }), title } }));
  return { checklist: c?.items ?? [], setChecklist, clTitle: c?.title ?? "체크리스트", setClTitle, has: !!c };
}

export const INITIAL_STUDIO: Studio = {
  open: true, view: "home", dir: "push", job: null, badge: null, done: null,
  made: [{ id: 2, kind: "audio", title: "11.06 내 종목 라디오", meta: "오디오 · 3종목 · 6:42", when: "11.06", left: "27일 뒤 삭제" }, { id: 1, kind: "report", title: "이번 주 내 종목 보고서", meta: "주간보고서 · 3종목 · 11.02", when: "11.02", left: "23일 뒤 삭제" }],
  creditOut: false, mini: false, playing: false, t: 141, speed: 1, quizDone: null,
  labStock: "SK하이닉스", labVars: { "원/달러 환율": "하락", "미국 10년물 국채금리": "상승" },
};

/* 서버에서 내 종목 · 종목별 보드(메모 · 체크리스트)를 불러와 화면 모양으로 */
async function loadAll() {
  const stocks = (await api.myStocks()).map(toStock);
  const boards = await Promise.all(stocks.map((s) => api.board(s.code)));
  const memos: Memo[] = [], checks: Record<string, BoardChecklist> = {};
  const memoIds = new Map<number, string>(), checkIds = new Map<string, ChecklistWire>();
  stocks.forEach((s, i) => {
    const rows = boards[i];
    const notes = rows.filter((r): r is MemoWire => r.kind === "memo")
      .sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.created_at.localeCompare(a.created_at));
    notes.forEach((w, j) => { const m = toMemo(w, j % 3); memos.push(m); memoIds.set(m.id, w.id); });
    const cl = rows.find((r): r is ChecklistWire => r.kind === "checklist"); // 보드에는 체크리스트 카드 하나만 보여 줌
    if (cl) { checks[s.code] = toChecklist(cl); checkIds.set(s.code, cl); }
  });
  return { stocks, memos, checks, ids: { memos: memoIds, checks: checkIds } };
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState<Route>(API_MODE ? { name: "login" } : { name: "intro" });
  const [nav, setNav] = useState(0);
  /* API 모드: 내 종목 · 메모는 서버에서 채운다 (처음엔 비어 있음). 휴지통 · 알림함 예시 항목은 실제 데이터로 오인되지 않게 비움 */
  const [stocks, setStocks] = useState<Stock[]>(API_MODE ? [] : ALL_STOCKS);
  const [memos, setMemos] = useState<Memo[]>(API_MODE ? [] : MEMOS);
  const [journal, setJournal] = useState<Journal[]>(JOURNAL);
  const [trash, setTrash] = useState<TrashItem[]>(API_MODE ? [] : TRASH);
  const [checks, setChecks] = useState<Record<string, BoardChecklist>>({});
  /* 세션 쿠키 흔적이 없으면 확인 요청 없이 바로 '로그인 안 됨' (소셜 로그인 취소로 돌아온 경우 안내) */
  const [auth, setAuth] = useState<AuthState>(() => (API_MODE ? (hasSessionCookie() ? "checking" : "out") : "demo"));
  const [user, setUser] = useState<UserWire | null>(null);
  const [authError, setAuthError] = useState<string | null>(() => (API_MODE && !hasSessionCookie() && new URLSearchParams(window.location.search).has("error") ? "로그인을 마치지 못했어요. 다시 시도해 주세요." : null));
  const [apiNote, setApiNote] = useState<ApiNote>(null);
  const [checklist, setChecklist] = useState(CHECKLIST);
  const [clTitle, setClTitle] = useState("체크리스트");
  const [overlay, setOverlay] = useState<Overlay>(null);
  const [settingsTab, setSettingsTab] = useState("내 프로필");
  const [homeMode, setHomeMode] = useState<"template" | "custom">("template");
  const [widgets, setWidgets] = useState<string[]>(["market"]);
  const [board, setBoard] = useState<WItem[]>([]);
  const [newsCount, setNewsCount] = useState(5);
  const [studio, setStudio] = useState<Studio>(INITIAL_STUDIO);
  const [demo, setDemo] = useState<Demo>({ fail: false, ranOut: false, quizLocked: false, quiz4: false, noNews: false, short: false, speed: "1" });
  const [sideOpen, setSideOpen] = useState(true);
  const [memoOpen, setMemoOpen] = useState<number | null>(null);
  const [flash, setFlash] = useState<number | null>(null);
  const [coach, setCoach] = useState<Coach>(null);
  const [coachPending, setCoachPending] = useState(false);
  const [coachDone, setCoachDone] = useState(false);
  const [nudgeOff, setNudgeOff] = useState<Partial<Record<NudgeId, boolean>>>({});
  const hideNudge = useCallback((id: NudgeId) => setNudgeOff((o) => ({ ...o, [id]: true })), []);
  const resetNudges = useCallback(() => setNudgeOff({}), []);
  const [nudgeAsk, askNudge] = useState<NudgeId | null>(null);
  const [preset, setPreset] = useState<Preset>(null);
  const [planOpen, setPlanOpen] = useState(false);
  const [x, setX] = useState<Ext>(API_MODE ? { ...INITIAL_EXT, notifs: [] } : INITIAL_EXT);
  const last = useRef<string>("");
  const go = useCallback((r: Route) => {
    const k = JSON.stringify(r); if (k === last.current) return; last.current = k;
    setRoute(r); setNav((n) => n + 1);
  }, []);

  /* ---------- API 모드: 로그인 확인 → 서버 데이터 불러오기 → 바뀐 상태를 서버에 저장 ---------- */
  const note = useCallback((text: string) => setApiNote((n) => ({ key: (n?.key ?? 0) + 1, text })), []);
  /* 동기화 실패 → 알림 + 서버 상태 다시 불러오기 (hydrate가 아래에 있어 ref로 연결) */
  const onSyncError = useRef<(msg: string) => void>(() => {});
  const [sync] = useState<Sync | null>(() => (API_MODE ? createSync((msg) => onSyncError.current(msg)) : null));
  const hydrate = useCallback(async (after?: (n: number) => void) => {
    setAuth("loading");
    try {
      const d = await loadAll();
      sync?.reset({ stocks: d.stocks, memos: d.memos, checks: d.checks }, d.ids);
      setStocks(d.stocks); setMemos(d.memos); setChecks(d.checks);
      setAuth("in");
      after?.(d.stocks.length);
    } catch (e) {
      const status = (e as { status?: number }).status;
      if (status === 401) { setAuth("out"); setUser(null); last.current = ""; setRoute({ name: "login" }); setNav((n) => n + 1); return; }
      setAuth("in");
      note(`서버에서 불러오지 못했어요 · ${e instanceof Error ? e.message : ""}`);
    }
  }, [note, sync]);
  const reload = useCallback(() => { void hydrate(); }, [hydrate]);
  useEffect(() => { onSyncError.current = (msg) => { note(`저장하지 못했어요 · ${msg} · 서버에 있는 내용으로 다시 불러왔어요`); void hydrate(); }; }, [note, hydrate]);
  useEffect(() => {
    if (!API_MODE) return;
    const q = new URLSearchParams(window.location.search);
    const cancelled = q.get("error");
    if (q.has("status") || q.has("error")) window.history.replaceState(null, "", window.location.pathname);
    let alive = true;
    if (!hasSessionCookie()) return; // 초기값에서 이미 'out' (위 useState)
    api.me().then(
      (u) => {
        if (!alive) return;
        setUser(u);
        void hydrate((n) => { last.current = ""; setRoute(n ? { name: "home" } : { name: "terms" }); setNav((k) => k + 1); });
      },
      (e) => {
        if (!alive) return;
        setAuth("out");
        const status = (e as { status?: number }).status;
        if (cancelled) setAuthError("로그인을 마치지 못했어요. 다시 시도해 주세요.");
        else if (status !== 401) setAuthError(e instanceof Error ? e.message : "서버에 연결할 수 없어요.");
      },
    );
    return () => { alive = false; };
  }, [hydrate]);
  useEffect(() => { if (API_MODE && auth === "in") sync?.apply({ stocks, memos, checks }); }, [sync, auth, stocks, memos, checks]);
  useEffect(() => {
    if (!API_MODE) return;
    const f = () => sync?.flush();
    window.addEventListener("pagehide", f);
    return () => window.removeEventListener("pagehide", f);
  }, [sync]);
  /* 메모 팝업을 열 때 서버의 AI 업데이트 타임라인을 불러와 붙인다 (화면 표시용, 저장 대상 아님) */
  const loadTimeline = useCallback((id: number) => {
    const sid = sync?.memoSid(id);
    if (!API_MODE || !sid) return;
    api.timeline(sid).then((w) => {
      const t = toTimeline(w);
      sync?.setUnread(id, t.unread);
      setMemos((a) => a.map((m) => (m.id === id ? { ...m, timeline: t.timeline, tracks: t.tracks ?? m.tracks } : m)));
    }, (e) => note(`AI 업데이트를 불러오지 못했어요 · ${e instanceof Error ? e.message : ""}`));
  }, [note, sync]);
  const sgo = useCallback((v: SView, dir: "push" | "pop" = "push") => setStudio((s) => ({ ...s, view: v, dir, open: true })), []);
  const openSettings = (tab = "내 프로필") => { setSettingsTab(tab); setOverlay("settings"); };
  const reset = () => {
    if (API_MODE) {
      /* 로그아웃: 기다리던 삭제를 먼저 보내고 서버 세션을 끝낸 뒤 화면 데이터를 비운다 */
      sync?.flush();
      sync?.reset({ stocks: [], memos: [], checks: {} }, { memos: new Map(), checks: new Map() });
      if (auth === "in") void api.logout().catch(() => {});
      setAuth("out"); setUser(null); setAuthError(null);
      setStocks([]); setMemos([]); setChecks({}); setTrash([]); setJournal(JOURNAL); setChecklist(CHECKLIST); setClTitle("체크리스트"); setOverlay(null);
      setHomeMode("template"); setWidgets(["market"]); setBoard([]); setNewsCount(5); setStudio(INITIAL_STUDIO); setMemoOpen(null); setSideOpen(true);
      setCoach(null); setCoachPending(false); setCoachDone(false); setNudgeOff({}); askNudge(null); setPreset(null); setPlanOpen(false); setX({ ...INITIAL_EXT, notifs: [] });
      last.current = ""; setRoute({ name: "login" }); setNav((n) => n + 1);
      return;
    }
    setStocks(ALL_STOCKS); setMemos(MEMOS); setJournal(JOURNAL); setTrash(TRASH); setChecklist(CHECKLIST); setClTitle("체크리스트"); setOverlay(null);
    setHomeMode("template"); setWidgets(["market"]); setBoard([]); setNewsCount(5); setStudio(INITIAL_STUDIO); setMemoOpen(null); setSideOpen(true);
    setCoach(null); setCoachPending(false); setCoachDone(false); setNudgeOff({}); askNudge(null); setPreset(null); setPlanOpen(false); setX(INITIAL_EXT);
    last.current = ""; setRoute({ name: "login" }); setNav((n) => n + 1);
  };
  return (
    <C.Provider value={{ route, go, nav, stocks, setStocks, memos, setMemos, journal, setJournal, trash, setTrash, checklist, setChecklist, clTitle, setClTitle, overlay, setOverlay, settingsTab, openSettings, homeMode, setHomeMode, widgets, setWidgets, board, setBoard, newsCount, setNewsCount, studio, setStudio, sgo, demo, setDemo, sideOpen, setSideOpen, memoOpen, setMemoOpen, flash, setFlash, coach, setCoach, coachPending, setCoachPending, coachDone, setCoachDone, nudgeOff, hideNudge, resetNudges, nudgeAsk, askNudge, preset, setPreset, planOpen, setPlanOpen, x, setX, reset, auth, user, authError, checks, setChecks, loadTimeline, apiNote, reload }}>
      {children}
    </C.Provider>
  );
}
