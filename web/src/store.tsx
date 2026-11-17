import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { ALL_STOCKS, MEMOS, JOURNAL, TRASH, CHECKLIST, type Stock, type Memo, type Journal } from "./data";

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
  trash: typeof TRASH; setTrash: React.Dispatch<React.SetStateAction<typeof TRASH>>;
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
};
const C = createContext<Ctx>(null as unknown as Ctx);
export const useApp = () => useContext(C);

export const INITIAL_STUDIO: Studio = {
  open: true, view: "home", dir: "push", job: null, badge: null, done: null,
  made: [{ id: 2, kind: "audio", title: "11.06 내 종목 라디오", meta: "오디오 · 3종목 · 6:42", when: "11.06", left: "27일 뒤 삭제" }, { id: 1, kind: "report", title: "이번 주 내 종목 보고서", meta: "주간보고서 · 3종목 · 11.02", when: "11.02", left: "23일 뒤 삭제" }],
  creditOut: false, mini: false, playing: false, t: 141, speed: 1, quizDone: null,
  labStock: "SK하이닉스", labVars: { "원/달러 환율": "하락", "미국 10년물 국채금리": "상승" },
};

export function AppProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState<Route>({ name: "intro" });
  const [nav, setNav] = useState(0);
  const [stocks, setStocks] = useState<Stock[]>(ALL_STOCKS);
  const [memos, setMemos] = useState<Memo[]>(MEMOS);
  const [journal, setJournal] = useState<Journal[]>(JOURNAL);
  const [trash, setTrash] = useState(TRASH);
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
  const [x, setX] = useState<Ext>(INITIAL_EXT);
  const last = useRef<string>("");
  const go = useCallback((r: Route) => {
    const k = JSON.stringify(r); if (k === last.current) return; last.current = k;
    setRoute(r); setNav((n) => n + 1);
  }, []);
  const sgo = useCallback((v: SView, dir: "push" | "pop" = "push") => setStudio((s) => ({ ...s, view: v, dir, open: true })), []);
  const openSettings = (tab = "내 프로필") => { setSettingsTab(tab); setOverlay("settings"); };
  const reset = () => {
    setStocks(ALL_STOCKS); setMemos(MEMOS); setJournal(JOURNAL); setTrash(TRASH); setChecklist(CHECKLIST); setClTitle("체크리스트"); setOverlay(null);
    setHomeMode("template"); setWidgets(["market"]); setBoard([]); setNewsCount(5); setStudio(INITIAL_STUDIO); setMemoOpen(null); setSideOpen(true);
    setCoach(null); setCoachPending(false); setCoachDone(false); setNudgeOff({}); askNudge(null); setPreset(null); setPlanOpen(false); setX(INITIAL_EXT);
    last.current = ""; setRoute({ name: "login" }); setNav((n) => n + 1);
  };
  return (
    <C.Provider value={{ route, go, nav, stocks, setStocks, memos, setMemos, journal, setJournal, trash, setTrash, checklist, setChecklist, clTitle, setClTitle, overlay, setOverlay, settingsTab, openSettings, homeMode, setHomeMode, widgets, setWidgets, board, setBoard, newsCount, setNewsCount, studio, setStudio, sgo, demo, setDemo, sideOpen, setSideOpen, memoOpen, setMemoOpen, flash, setFlash, coach, setCoach, coachPending, setCoachPending, coachDone, setCoachDone, nudgeOff, hideNudge, resetNudges, nudgeAsk, askNudge, preset, setPreset, planOpen, setPlanOpen, x, setX, reset }}>
      {children}
    </C.Provider>
  );
}
