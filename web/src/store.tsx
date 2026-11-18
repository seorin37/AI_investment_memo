/* 앱 상태 — 화면 이동·팝업 같은 UI 상태 + 내 데이터(UserState, 서버에 저장) + 데이터를 바꾸는 동작(act)
   내 데이터는 바뀔 때마다 api.me.save 로 저장돼요. 화면 코드는 act.* 만 부르면 돼요. */
import { flatRows } from "./screens/boardDrag";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, clearQ } from "./api";
import type { Checklist, ColorKey, Hold, JobKind, LabDir, Made, MemoEdit, Memo as MemoRaw, Profile, Settings, TrackItem, TrashItem, UserState, Journal as JournalRaw } from "./api/types";
import { emptyState } from "./api/mock/db";
import type { Journal, Memo, Stock, TL } from "./data";

export type Route =
  | { name: "intro" } | { name: "login" } | { name: "terms" } | { name: "pick" } | { name: "start" } | { name: "home" } | { name: "custom" }
  | { name: "updates"; code?: string } | { name: "journal" } | { name: "stock"; code: string; tab: "board" | "info" }
  | { name: "help" } | { name: "report"; id?: number } | { name: "mine" };
export type Overlay = null | "addStock" | "settings" | "feedback" | "trash" | "audio" | "reportPick" | "credit" | "charge" | "logout";

export type SView = "home" | "gen" | "fail" | "ranOut" | "player" | "quiz" | "report" | "lab" | "labResult";
export type { JobKind };
export type Job = { kind: JobKind; title: string; codes: string[]; step: number; pct: number; params: { days?: 1 | 3 | 7; summary?: boolean; market?: boolean; code?: string; vars?: [string, LabDir][] } };
export type Studio = {
  open: boolean; view: SView; dir: "push" | "pop";
  job: null | Job; lastJob?: Job; failKind?: JobKind; done?: JobKind | null; badge?: string | null;
  cur: number | null;            // 보고 있는 만든 항목 id (플레이어·보고서·실험 결과)
  mini: boolean; playing: boolean; t: number; speed: number;
  labCode: string | null; labVars: Record<string, LabDir>;
};
export type Coach = null | { step: number };
export type NudgeId = "memo" | "updates" | "info" | "lab" | "home";
export type Preset = null | { codes?: string[]; newMemo?: string };
export type WItem = { id: string; x: number; y: number; w: number; h: number };
export type Notif = { id: string; kind: "upd" | "studio"; t: string; s: string; at: string; when: string; read: boolean; stock_code?: string; memo?: number; made?: number; view?: SView };
/* 화면에만 쓰는 임시 상태 (저장 안 함) */
export type Ext = { read: Record<string, boolean>; offline: boolean; widgetFail: boolean; inbox: boolean; seen: Record<string, boolean>; homeEdit: boolean; market: string | null; first: boolean; memoTab: number; loginFail: boolean; firstStep: number };
export const INITIAL_EXT: Ext = { read: {}, offline: false, widgetFail: false, inbox: false, seen: {}, homeEdit: false, market: null, first: false, memoTab: 0, loginFail: false, firstStep: 0 };
export type Demo = { fail: boolean; ranOut: boolean; quizLocked: boolean; quiz4: boolean; noNews: boolean; short: boolean; speed: "1" | "2.5" | ".01" };
export const INITIAL_STUDIO: Studio = { open: true, view: "home", dir: "push", job: null, badge: null, done: null, cur: null, mini: false, playing: false, t: 0, speed: 1, labCode: null, labVars: {} };

/* ---------- 날짜 표시 ---------- */
const D = (iso: string) => new Date(iso);
export const mmdd = (iso: string) => { const d = D(iso); return `${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`; };
export const md = (iso: string) => { const d = D(iso); return `${d.getMonth() + 1}월 ${d.getDate()}일`; };
export const hm = (iso: string) => { const d = D(iso); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
export function ago(iso: string) {
  const s = (Date.now() - D(iso).getTime()) / 1000;
  if (s < 60) return "방금"; if (s < 3600) return `${Math.floor(s / 60)}분 전`; if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  if (s < 86400 * 2) return "어제"; if (s < 86400 * 7) return `${Math.floor(s / 86400)}일 전`; return mmdd(iso);
}
export const full = (iso: string) => { const d = D(iso), h = d.getHours(); return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 ${h < 12 ? "오전" : "오후"} ${h % 12 || 12}:${String(d.getMinutes()).padStart(2, "0")}`; };
const nowIso = () => new Date().toISOString();

/* ---------- 뷰 변환 ---------- */
export function toStock(code: string, hold: Hold): Stock | null {
  const i = api.market.info(code); if (!i) return null;
  const q = api.market.quote(code) as ReturnType<typeof import("./api/mock/market").quote>;
  return { stock_code: code, name: i.name, short: i.logo, logo: i.logo, logo_bg: i.logo_bg, logo_ink: i.logo_ink, hold, market: i.market, sector: i.sector, financial: i.financial, price: q.price, chg: q.chg, pct: q.pct, as_of: q.as_of, seed: Number(code.slice(-2)) || 5 };
}
function toTL(m: MemoRaw): TL[] {
  return api.ai.timeline(m).map((x) => {
    if (x.kind === "start") return { kind: "start", at: x.at, date: md(x.at) };
    if (x.kind === "first") return { kind: "first", at: x.at, date: mmdd(x.at), old: { when: `${md(x.at)} · 처음 작성한 메모`, title: x.old.title, body: x.old.body.replace(/\n/g, " ") } };
    if (x.kind === "edit") return { kind: "edit", at: x.at, date: mmdd(x.at), old: { when: `${md(x.at)} ${hm(x.at)} · 수정 당시 메모`, title: x.old.title, body: x.old.body.replace(/\n/g, " ") } };
    const u = x as Extract<typeof x, { id: string }>;
    return { kind: u.kind, at: u.at, date: md(u.at), title: u.title, body: u.body, src: u.src, url: u.url };
  });
}
export const trackLabel = (t?: TrackItem[]) => (t?.length ? t.map((x) => x.t).join(" · ") : undefined);
function toMemo(m: MemoRaw): Memo {
  const tl = toTL(m);
  return { id: m.id, stock_code: m.stock_code, date: mmdd(m.created_at), created_at: m.created_at, title: m.title, body: m.body, color: m.color, ai: m.ai, pinned: m.pinned, pinned_at: m.pinned_at, col: m.col, badge: m.ai ? api.ai.unseen(m) : 0, tracks: trackLabel(m.tracks), track_items: m.tracks, timeline: tl, news: tl.filter((x) => x.kind === "공시" || x.kind === "뉴스" || x.kind === "주가").length };
}
const toJournal = (j: JournalRaw): Journal => ({ ...j, date: md(j.created_at), full: full(j.created_at) });

type Act = ReturnType<typeof useActs>;
type Ctx = {
  ready: boolean; route: Route; go: (r: Route) => void; nav: number;
  ud: UserState; setUd: React.Dispatch<React.SetStateAction<UserState>>; act: Act;
  stocks: Stock[]; memos: Memo[]; memoRaw: MemoRaw[]; journal: Journal[]; trash: TrashItem[]; newN: Record<string, number>; checklists: Record<string, Checklist>; made: Made[]; notifs: Notif[];
  overlay: Overlay; setOverlay: (o: Overlay) => void; settingsTab: string; openSettings: (tab?: string) => void;
  studio: Studio; setStudio: React.Dispatch<React.SetStateAction<Studio>>; sgo: (v: SView, dir?: "push" | "pop") => void;
  demo: Demo; setDemo: React.Dispatch<React.SetStateAction<Demo>>; creditOut: boolean;
  sideOpen: boolean; setSideOpen: (v: boolean) => void;
  memoOpen: number | null; setMemoOpen: (v: number | null) => void;
  coach: Coach; setCoach: React.Dispatch<React.SetStateAction<Coach>>; coachPending: boolean; setCoachPending: (v: boolean) => void;
  nudgeOff: Partial<Record<NudgeId, boolean>>; hideNudge: (id: NudgeId) => void; resetNudges: () => void; nudgeAsk: NudgeId | null; askNudge: (id: NudgeId | null) => void;
  preset: Preset; setPreset: (p: Preset) => void;
  planOpen: boolean; setPlanOpen: (v: boolean) => void;
  x: Ext; setX: React.Dispatch<React.SetStateAction<Ext>>;
};
const C = createContext<Ctx>(null as unknown as Ctx);
export const useApp = () => useContext(C);

/* ---------- 데이터를 바꾸는 동작 ---------- */
function useActs(setUd: React.Dispatch<React.SetStateAction<UserState>>, udRef: React.MutableRefObject<UserState>) {
  const idRef = useRef(1);
  return useMemo(() => {
    const up = (f: (s: UserState) => UserState) => setUd(f);
    const nid = () => { const s = udRef.current; const id = Math.max(idRef.current, Math.max(0, ...s.memos.map((m) => m.id), ...s.journal.map((j) => j.id), ...s.made.map((m) => m.id), ...s.trash.map((t) => (t.data as { id?: number })?.id ?? 0)) + 1); idRef.current = id + 1; return id; };
    const tr = (kind: TrashItem["kind"], title: string, sub: string, data: unknown): TrashItem => ({ id: `${kind}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, kind, title, sub, deleted_at: nowIso(), data });
    const nameOf = (code: string) => api.market.info(code)?.name ?? code;
    return {
      /* 종목 */
      setStocks(list: { stock_code: string; hold: Hold }[]) { up((s) => ({ ...s, stocks: list.map((x, i) => ({ stock_code: x.stock_code, hold: x.hold, added_at: s.stocks.find((y) => y.stock_code === x.stock_code)?.added_at ?? nowIso(), order: i })) })); },
      addStock(code: string, hold: Hold) { up((s) => (s.stocks.some((x) => x.stock_code === code) ? { ...s, stocks: s.stocks.map((x) => (x.stock_code === code ? { ...x, hold } : x)) } : { ...s, stocks: [...s.stocks, { stock_code: code, hold, added_at: nowIso(), order: s.stocks.length }], trash: s.trash.filter((t) => !(t.kind === "종목" && (t.data as { stock_code: string }).stock_code === code)) })); },
      setHold(codes: string[], hold: Hold) { up((s) => ({ ...s, stocks: s.stocks.map((x) => (codes.includes(x.stock_code) ? { ...x, hold } : x)) })); },
      reorder(codes: string[]) { up((s) => ({ ...s, stocks: s.stocks.map((x) => ({ ...x, order: codes.indexOf(x.stock_code) < 0 ? 999 : codes.indexOf(x.stock_code) })).sort((a, b) => a.order - b.order) })); },
      removeStocks(codes: string[]) { up((s) => ({ ...s, stocks: s.stocks.filter((x) => !codes.includes(x.stock_code)), trash: [...s.stocks.filter((x) => codes.includes(x.stock_code)).map((x) => tr("종목", nameOf(x.stock_code), `종목 · 메모 ${s.memos.filter((m) => m.stock_code === x.stock_code).length}개는 그대로 보관`, x)), ...s.trash] })); },
      /* 메모 */
      addMemo(code: string, p: { title: string; body: string; color: ColorKey }): number {
        const id = nid();
        up((s) => { const t = nowIso(); const m: MemoRaw = { id, stock_code: code, title: p.title, body: p.body, color: p.color, created_at: t, updated_at: t, ai: false, pinned: false, col: 0, edits: [] };
          const same = s.memos.filter((x) => x.stock_code === code); const counts = [0, 1, 2].map((c) => same.filter((x) => x.col % 3 === c).length); m.col = counts.indexOf(Math.min(...counts));
          return { ...s, memos: [m, ...s.memos] }; });
        return id;
      },
      updateMemo(id: number, p: { title?: string; body?: string; color?: ColorKey }) {
        up((s) => ({ ...s, memos: s.memos.map((m) => { if (m.id !== id) return m; const changed = (p.title !== undefined && p.title !== m.title) || (p.body !== undefined && p.body !== m.body); const e: MemoEdit[] = changed ? [...m.edits, { at: nowIso(), title: m.title, body: m.body }] : m.edits; return { ...m, ...p, edits: e, updated_at: changed ? nowIso() : m.updated_at }; }) }));
      },
      memoAi(id: number, tracks: TrackItem[] | false) { up((s) => ({ ...s, memos: s.memos.map((m) => (m.id !== id ? m : tracks ? { ...m, ai: true, tracks, ai_since: m.ai && m.ai_since ? m.ai_since : nowIso(), seen_at: m.seen_at } : { ...m, ai: false, ai_since: undefined, tracks: undefined })) })); },
      pinMemos(ids: number[], on: boolean) {
        const t = Date.now();
        up((s) => {
          /* 테이프를 붙이면 보드 맨 앞(왼쪽 위)으로 올려요. 그 뒤로는 끌어서 자유롭게 옮길 수 있어요 */
          let boards = s.boards;
          if (on && boards) {
            boards = { ...boards };
            for (const m of s.memos) if (ids.includes(m.id) && boards[m.stock_code]) {
              const k = "m" + m.id, cur = boards[m.stock_code] as unknown as string[] | string[][];
              const list = Array.isArray(cur[0]) ? flatRows(cur as string[][]) : (cur as string[]);
              boards[m.stock_code] = [k, ...list.filter((x) => x !== k)];
            }
          }
          return { ...s, boards, memos: s.memos.map((m) => (ids.includes(m.id) ? { ...m, pinned: on, pinned_at: on ? t : undefined } : m)) };
        });
      },
      /* 보드 카드 순서 저장 (끌어서 옮긴 뒤). 메모의 col도 격자 열에 맞춰요 */
      arrangeBoard(code: string, order: string[]) {
        up((s) => {
          const at = new Map(order.map((k, i) => [k, i] as const));
          return { ...s, boards: { ...(s.boards ?? {}), [code]: order }, memos: s.memos.map((m) => (m.stock_code === code && at.has("m" + m.id) ? { ...m, col: at.get("m" + m.id)! % 3 } : m)) };
        });
      },
      seeMemo(id: number) { up((s) => ({ ...s, memos: s.memos.map((m) => (m.id === id ? { ...m, seen_at: nowIso() } : m)) })); },
      trashMemos(ids: number[]) { up((s) => ({ ...s, memos: s.memos.filter((m) => !ids.includes(m.id)), trash: [...s.memos.filter((m) => ids.includes(m.id)).map((m) => tr("메모", m.title, `${nameOf(m.stock_code)} / 메모`, m)), ...s.trash] })); },
      /* 체크리스트 (종목마다 하나) */
      saveChecklist(code: string, title: string, items: { id?: number; t: string; d: boolean }[]) {
        up((s) => { if (!items.length) { const c = { ...s.checklists }; delete c[code]; return { ...s, checklists: c }; } let n = Math.max(0, ...items.map((x) => x.id ?? 0)); return { ...s, checklists: { ...s.checklists, [code]: { stock_code: code, title: title.trim() || "체크리스트", items: items.map((x) => ({ id: x.id ?? ++n, t: x.t, d: x.d })), updated_at: nowIso() } } }; });
      },
      toggleCheck(code: string, itemId: number) { up((s) => { const c = s.checklists[code]; if (!c) return s; return { ...s, checklists: { ...s.checklists, [code]: { ...c, items: c.items.map((x) => (x.id === itemId ? { ...x, d: !x.d } : x)), updated_at: nowIso() } } }; }); },
      addCheck(code: string, t: string) { up((s) => { const c = s.checklists[code] ?? { stock_code: code, title: "체크리스트", items: [], updated_at: nowIso() }; const id = Math.max(0, ...c.items.map((x) => x.id)) + 1; return { ...s, checklists: { ...s.checklists, [code]: { ...c, items: [...c.items, { id, t, d: false }], updated_at: nowIso() } } }; }); },
      trashChecklist(code: string) { up((s) => { const c = s.checklists[code]; if (!c) return s; const cl = { ...s.checklists }; delete cl[code]; return { ...s, checklists: cl, trash: [tr("체크리스트 항목", c.title, `${nameOf(code)} / 체크리스트 · ${c.items.length}개 항목`, c), ...s.trash] }; }); },
      /* 투자 기록 */
      addJournal(): number { const id = nid(); up((s) => { const t = nowIso(); return { ...s, journal: [{ id, title: "", created_at: t, updated_at: t, body: [""], todo: [] }, ...s.journal] }; }); return id; },
      updateJournal(id: number, p: Partial<JournalRaw>) { up((s) => ({ ...s, journal: s.journal.map((j) => (j.id === id ? { ...j, ...p, updated_at: nowIso() } : j)) })); },
      pinJournal(ids: number[], on: boolean) { up((s) => ({ ...s, journal: s.journal.map((j) => (ids.includes(j.id) ? { ...j, pinned: on } : j)) })); },
      trashJournal(ids: number[]) { up((s) => ({ ...s, journal: s.journal.filter((j) => !ids.includes(j.id)), trash: [...s.journal.filter((j) => ids.includes(j.id)).map((j) => tr("투자 기록", j.title || "제목 없음", "투자 기록", j)), ...s.trash] })); },
      dropEmptyJournal(id: number) { up((s) => ({ ...s, journal: s.journal.filter((j) => !(j.id === id && !j.title.trim() && !j.body.join("").trim() && !(j.html ?? "").replace(/<[^>]+>|&nbsp;/g, "").trim() && !j.todo.length)) })); },
      /* 휴지통 */
      restore(id: string) {
        up((s) => { const t = s.trash.find((x) => x.id === id); if (!t) return s; const rest = s.trash.filter((x) => x.id !== id);
          if (t.kind === "메모") { const m = t.data as MemoRaw; return { ...s, trash: rest, memos: [m, ...s.memos.filter((x) => x.id !== m.id)], stocks: s.stocks.some((x) => x.stock_code === m.stock_code) ? s.stocks : [...s.stocks, { stock_code: m.stock_code, hold: "관심", added_at: nowIso(), order: s.stocks.length }] }; }
          if (t.kind === "투자 기록") { const j = t.data as JournalRaw; return { ...s, trash: rest, journal: [j, ...s.journal.filter((x) => x.id !== j.id)].sort((a, b) => b.created_at.localeCompare(a.created_at)) }; }
          if (t.kind === "종목") { const k = t.data as UserState["stocks"][number]; return { ...s, trash: rest, stocks: s.stocks.some((x) => x.stock_code === k.stock_code) ? s.stocks : [...s.stocks, { ...k, order: s.stocks.length }] }; }
          const c = t.data as Checklist; return { ...s, trash: rest, checklists: { ...s.checklists, [c.stock_code]: c } }; });
      },
      purge(id: string) { up((s) => ({ ...s, trash: s.trash.filter((x) => x.id !== id) })); },
      emptyTrash() { up((s) => ({ ...s, trash: [] })); },
      /* 스튜디오 · 퀴즈 · 알림 */
      addMade(m: Omit<Made, "id">): number { const id = nid(); up((s) => { return { ...s, made: [{ ...m, id }, ...s.made], usage: { ...s.usage, pct: Math.min(100, s.usage.pct + (m.kind === "lab" ? 4 : 8)) }, notifs: s.settings.noti_studio ? [{ id: Date.now(), kind: "studio" as const, t: m.title + (m.kind === "audio" ? "이(가) 다 만들어졌어요" : " 결과가 나왔어요"), s: m.meta, at: nowIso(), read: false, made: id }, ...s.notifs].slice(0, 30) : s.notifs }; }); return id; },
      removeMade(id: number) { up((s) => ({ ...s, made: s.made.filter((m) => m.id !== id) })); },
      submitQuiz(quizId: string, picked: number, correct: boolean) { up((s) => (s.quiz.some((q) => q.quiz_id === quizId) ? s : { ...s, quiz: [...s.quiz, { quiz_id: quizId, picked, correct, at: nowIso() }] })); },
      readNotif(id: number) { up((s) => ({ ...s, notifs: s.notifs.map((n) => (n.id === id ? { ...n, read: true } : n)) })); },
      readAll() { up((s) => ({ ...s, notifs: s.notifs.map((n) => ({ ...n, read: true })), memos: s.memos.map((m) => (m.ai ? { ...m, seen_at: nowIso() } : m)) })); },
      setUsage(pct: number) { up((s) => ({ ...s, usage: { ...s.usage, pct } })); },
      /* 되돌리기: 바로 전 상태로 (토스트의 '되돌리기') */
      snapshot: (): UserState => udRef.current,
      rollback(snap: UserState) { setUd((s) => ({ ...snap, settings: s.settings, profile: s.profile })); },
      /* 설정 · 프로필 · 홈 */
      settings(p: Partial<Settings>) { up((s) => ({ ...s, settings: { ...s.settings, ...p } })); },
      profile(p: Partial<Profile>) { up((s) => (s.profile ? { ...s, profile: { ...s.profile, ...p } } : s)); },
      home(p: Partial<UserState["home"]>) { up((s) => ({ ...s, home: { ...s.home, ...p } })); },
      recent(name: string) { up((s) => ({ ...s, recent: [name, ...s.recent.filter((r) => r !== name)].slice(0, 5) })); },
      onboarded() { up((s) => ({ ...s, onboarded: true })); },
      coachDone(v = true) { up((s) => ({ ...s, coach_done: v })); },
      wipeData() { up((s) => ({ ...emptyState(s.profile), onboarded: true, coach_done: true, settings: s.settings })); },
    };
  }, [setUd]); // eslint-disable-line react-hooks/exhaustive-deps
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [route, setRoute] = useState<Route>({ name: "intro" });
  const [nav, setNav] = useState(0);
  const [ud, setUd] = useState<UserState>(() => emptyState(null));
  const [overlay, setOverlay] = useState<Overlay>(null);
  const [settingsTab, setSettingsTab] = useState("내 프로필");
  const [studio, setStudio] = useState<Studio>(INITIAL_STUDIO);
  const [demo, setDemo] = useState<Demo>({ fail: false, ranOut: false, quizLocked: false, quiz4: false, noNews: false, short: false, speed: "1" });
  const [sideOpen, setSideOpen] = useState(true);
  const [memoOpen, setMemoOpen] = useState<number | null>(null);
  const [coach, setCoach] = useState<Coach>(null);
  const [coachPending, setCoachPending] = useState(false);
  const [nudgeOff, setNudgeOff] = useState<Partial<Record<NudgeId, boolean>>>({});
  const hideNudge = useCallback((id: NudgeId) => setNudgeOff((o) => ({ ...o, [id]: true })), []);
  const resetNudges = useCallback(() => setNudgeOff({}), []);
  const [nudgeAsk, askNudge] = useState<NudgeId | null>(null);
  const [preset, setPreset] = useState<Preset>(null);
  const [planOpen, setPlanOpen] = useState(false);
  const [x, setX] = useState<Ext>(INITIAL_EXT);
  const udRef = useRef(ud); udRef.current = ud;
  const act = useActs(setUd, udRef);
  const last = useRef<string>("");
  const go = useCallback((r: Route) => {
    const k = JSON.stringify(r); if (k === last.current) return; last.current = k;
    setRoute(r); setNav((n) => n + 1);
  }, []);
  const sgo = useCallback((v: SView, dir: "push" | "pop" = "push") => setStudio((s) => ({ ...s, view: v, dir, open: true })), []);
  const openSettings = (tab = "내 프로필") => { setSettingsTab(tab); setOverlay("settings"); };

  /* 처음 열 때: 로그인돼 있으면 이어서 */
  useEffect(() => {
    void Promise.resolve(api.auth.session()).then((s) => {
      if (s?.profile) { setUd(s); last.current = ""; setRoute(s.onboarded ? { name: "home" } : { name: "pick" }); }
      else { let seen = false; try { seen = localStorage.getItem("memos.introSeen") === "1"; } catch { /* 무시 */ } setRoute(seen ? { name: "login" } : { name: "intro" }); }
      setReady(true);
    });
  }, []);
  /* 내 데이터 저장 (0.3초 모아서) */
  const saveT = useRef(0);
  useEffect(() => {
    if (!ready || !ud.profile) return;
    window.clearTimeout(saveT.current);
    saveT.current = window.setTimeout(() => { void api.me.save(ud); }, 300);
  }, [ud, ready]);

  /* 파생 데이터 */
  const day = api.market.lastClose();
  const stocks = useMemo(() => [...ud.stocks].sort((a, b) => a.order - b.order).map((s) => toStock(s.stock_code, s.hold)).filter(Boolean) as Stock[], [ud.stocks, day]); // eslint-disable-line react-hooks/exhaustive-deps
  const mine = useMemo(() => new Set(ud.stocks.map((s) => s.stock_code)), [ud.stocks]);
  const memos = useMemo(() => ud.memos.filter((m) => mine.has(m.stock_code)).map(toMemo), [ud.memos, mine, day]); // eslint-disable-line react-hooks/exhaustive-deps
  const journal = useMemo(() => ud.journal.map(toJournal), [ud.journal]);
  const made = useMemo(() => { const cut = Date.now() - 30 * 864e5; return ud.made.filter((m) => new Date(m.created_at).getTime() > cut); }, [ud.made]);
  const notifs = useMemo<Notif[]>(() => {
    const out: Notif[] = [];
    if (ud.settings.noti_upd) for (const m of memos) {
      if (!m.ai) continue; const raw = ud.memos.find((r) => r.id === m.id);
      const news = (m.timeline ?? []).filter((t) => t.kind === "공시" || t.kind === "뉴스" || t.kind === "주가").slice(0, 3);
      news.forEach((t) => out.push({ id: `u${m.id}-${t.at}`, kind: "upd", t: `${stocks.find((s) => s.stock_code === m.stock_code)?.name ?? ""} · ${m.title}`, s: `메모에 새 ${t.kind === "주가" ? "가격 소식" : t.kind}가 연결됐어요 · ${t.title}`, at: t.at, when: ago(t.at), read: !!raw?.seen_at && t.at <= raw.seen_at, stock_code: m.stock_code, memo: m.id }));
    }
    if (ud.settings.noti_studio) for (const n of ud.notifs) { const mm = ud.made.find((x) => x.id === n.made); out.push({ id: "s" + n.id, kind: "studio", t: n.t, s: n.s, at: n.at, when: ago(n.at), read: n.read, made: n.made, view: mm ? (mm.kind === "audio" ? "player" : mm.kind === "report" ? "report" : "labResult") : undefined }); }
    return out.sort((a, b) => b.at.localeCompare(a.at)).slice(0, 20);
  }, [memos, ud.notifs, ud.memos, ud.made, ud.settings, stocks]);
  const creditOut = ud.usage.pct >= 100;
  const newN = useMemo(() => { const o: Record<string, number> = {}; memos.forEach((m) => { o[m.stock_code] = (o[m.stock_code] ?? 0) + m.badge; }); return o; }, [memos]);

  const value: Ctx = {
    ready, route, go, nav, ud, setUd, act, stocks, memos, memoRaw: ud.memos, journal, trash: ud.trash, newN, checklists: ud.checklists, made, notifs,
    overlay, setOverlay, settingsTab, openSettings, studio, setStudio, sgo, demo, setDemo, creditOut, sideOpen, setSideOpen, memoOpen, setMemoOpen,
    coach, setCoach, coachPending, setCoachPending, nudgeOff, hideNudge, resetNudges, nudgeAsk, askNudge, preset, setPreset, planOpen, setPlanOpen, x, setX,
  };
  return <C.Provider value={value}>{children}</C.Provider>;
}

/* 로그인 · 로그아웃 · 탈퇴 · 예시 계정 */
export function useSession() {
  const app = useApp();
  const reset = (to: Route) => {
    app.setOverlay(null); app.setStudio(INITIAL_STUDIO); app.setMemoOpen(null); app.setSideOpen(true); app.setCoach(null); app.setCoachPending(false);
    app.resetNudges(); app.askNudge(null); app.setPreset(null); app.setPlanOpen(false); app.setX((v) => ({ ...INITIAL_EXT, loginFail: v.loginFail, offline: v.offline }));
    clearQ(); app.go(to);
  };
  return {
    async login(p: Profile["provider"]) { const { state, is_new } = await api.auth.login(p); app.setUd(state); reset(is_new || !state.onboarded ? { name: "terms" } : { name: "home" }); return is_new; },
    async logout() { await api.me.save(app.ud); await api.auth.logout(); app.setUd(emptyState(null)); reset({ name: "login" }); },
    async withdraw() { await api.auth.withdraw(); app.setUd(emptyState(null)); reset({ name: "login" }); },
    async demoAccount() { const s = await api.me.demoAccount(app.ud.profile ? app.ud : emptyState({ name: "김나라", job: "대학생", email: "nara.kim@kakao.example", provider: "kakao", joined_at: new Date().toISOString() })); app.setUd(s); await api.me.save(s); reset({ name: "home" }); },
    async freshStart() { api._mock.wipe(); try { localStorage.removeItem("memos.introSeen"); } catch { /* 무시 */ } app.setUd(emptyState(null)); reset({ name: "intro" }); },
  };
}
