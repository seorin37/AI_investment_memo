import { useEffect, useState } from "react";
import { Wand2, X, LogIn, Home as HomeIcon, LayoutGrid, RefreshCw, FileText, StickyNote, Building2, FileBarChart, RotateCcw, Sparkles, Compass, BellRing } from "lucide-react";
import "./motion.css";
import "./v2.css";
import "./x.css";
import { OfflineBand, InboxPanel } from "./x";
import { AppProvider, useApp, INITIAL_STUDIO, type Demo } from "./store";
import { SnackHost, Seg, Toggle, cx } from "./kit";
import { Sidebar, Main } from "./shell";
import { Login, Start } from "./screens/login";
import { Terms, Pick } from "./screens/onboard";
import { Intro } from "./screens/intro";
import { Coach } from "./coach";
import { NudgeHost } from "./nudge";
import { HomePage, MarketDetailHost } from "./screens/home";
import { CustomPage } from "./screens/custom";
import { UpdatesPage } from "./screens/updates";
import { StockPage } from "./screens/stock";
import { JournalPage } from "./screens/journal";
import { AddStock, Settings, Feedback, Trash, HelpPage, LogoutConfirm } from "./screens/overlays";
import { ReportPage } from "./screens/report";
import { MinePage } from "./screens/mine";
import { StudioColumn, AudioPopup, ReportPopup, CreditPopup, ChargePopup } from "./studio";
import { API_MODE } from "./api/config";
import { ApiNotes, SampleNotice } from "./apimode";

function Screen() {
  const { route } = useApp();
  switch (route.name) {
    case "home": return <HomePage />;
    case "start": return <Start />;
    case "custom": return <CustomPage />;
    case "updates": return <UpdatesPage code={route.code} />;
    case "journal": return <JournalPage />;
    case "stock": return <StockPage code={route.code} tab={route.tab} />;
    case "help": return <HelpPage />;
    case "report": return <ReportPage />;
    case "mine": return <MinePage />;
    default: return <HomePage />;
  }
}

/* 발표용 시연 도구 (` 키 또는 왼쪽 아래 버튼) */
function DemoTools() {
  const app = useApp();
  const { demo, setDemo, studio, setStudio, go, reset, sideOpen, route, setCoach, setCoachPending, resetNudges, setOverlay } = app;
  const inApp = !["intro", "login", "terms", "pick"].includes(route.name);
  const [open, setOpen] = useState(false);
  useEffect(() => { const f = (e: KeyboardEvent) => { const t = e.target as HTMLElement; if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable) return; if (e.key === "`") setOpen((o) => !o); }; window.addEventListener("keydown", f); return () => window.removeEventListener("keydown", f); }, []);
  const flag = (k: keyof Omit<Demo, "speed">, l: string, d: string) => (
    <label className="flex items-center gap-3 py-2"><span className="flex-1"><b className="block text-[13px]">{l}</b><span className="text-[13px] text-zinc-500">{d}</span></span><Toggle on={demo[k]} onChange={(v) => setDemo((x) => ({ ...x, [k]: v }))} label={l} /></label>
  );
  const J = [[Sparkles, "서비스 소개", () => { reset(); go({ name: "intro" }); }], [LogIn, "로그인", () => reset()], [LayoutGrid, "시작 설정", () => go({ name: "start" })], [HomeIcon, "홈", () => go({ name: "home" })], [LayoutGrid, "직접 사용자화", () => go({ name: "custom" })], [RefreshCw, "최신 업데이트", () => go({ name: "updates" })], [FileText, "투자 기록", () => go({ name: "journal" })], [StickyNote, "기업 메모장", () => go({ name: "stock", code: "000660", tab: "board" })], [Building2, "기업 정보", () => go({ name: "stock", code: "000660", tab: "info" })], [FileBarChart, "주간보고서", () => { go({ name: "report" }); setStudio((s) => ({ ...s, view: "report", dir: "push", open: true })); }]] as const;
  return (
    <>
      <button onClick={() => setOpen(!open)} title="시연 도구 ( ` 키 )" className={cx("m-press fixed bottom-3 z-[80] flex h-8 items-center gap-1 rounded-full bg-white/80 px-2.5 text-[13px] font-bold text-zinc-400 opacity-70 shadow-[0_0_0_1px_#e4e4e7] backdrop-blur transition-opacity hover:text-zinc-900 hover:opacity-100", sideOpen ? "left-[266px]" : "left-[88px]")}><Wand2 className="h-3.5 w-3.5" />시연</button>
      {open && (
        <div className={cx("m-pop fixed bottom-16 z-[85] max-h-[calc(100vh-90px)] w-[320px] overflow-y-auto rounded-[22px] border border-zinc-100 bg-white p-4 shadow-[0_24px_60px_-18px_rgba(17,17,17,.35)]", sideOpen ? "left-[266px]" : "left-[84px]")}>
          <div className="flex items-center"><b className="flex-1 text-[15px]">시연 도구</b><button aria-label="닫기" onClick={() => setOpen(false)} className="grid h-8 w-8 place-items-center rounded-full hover:bg-zinc-100"><X className="h-4 w-4" /></button></div>
          <p className="text-[13px] text-zinc-500">발표 중 상황을 바로 바꿔 볼 수 있어요. ` 키로 열고 닫아요.</p>
          <p className="mb-1.5 mt-4 text-[13px] font-bold text-zinc-500">움직임 속도</p>
          <Seg full size="sm" value={demo.speed} onChange={(v) => setDemo((d) => ({ ...d, speed: v }))} options={[["1", "기본"], ["2.5", "느리게"], [".01", "줄이기"]] as const} />
          <p className="mb-0.5 mt-4 text-[13px] font-bold text-zinc-500">스튜디오 상황</p>
          {flag("fail", "만들기 실패", "진행 중에 실패 → 크레딧 돌려드림 (08)")}
          {flag("ranOut", "만들다가 크레딧 다 씀", "중간에 멈춤 (22)")}
          {flag("quizLocked", "퀴즈 공개 전", "오전 10시 전 화면 (15)")}
          {flag("quiz4", "4지선다 퀴즈", "O/X 대신 4지선다 (12)")}
          {flag("noNews", "새 소식 없음", "오디오 · 업데이트 빈 화면 (10)")}
          <p className="mb-0.5 mt-4 text-[13px] font-bold text-zinc-500">앱 공통 상황</p>
          <label className="flex items-center gap-3 py-2"><span className="flex-1"><b className="block text-[13px]">로그인 실패</b><span className="text-[13px] text-zinc-500">소셜 로그인 버튼을 누르면 실패 안내</span></span><Toggle on={app.x.loginFail} onChange={(v) => app.setX((x) => ({ ...x, loginFail: v }))} label="로그인 실패" /></label>
          <label className="flex items-center gap-3 py-2"><span className="flex-1"><b className="block text-[13px]">인터넷 끊김 띠</b><span className="text-[13px] text-zinc-500">가운데 화면 위에 띠</span></span><Toggle on={app.x.offline} onChange={(v) => app.setX((x) => ({ ...x, offline: v }))} label="인터넷 끊김 띠" /></label>
          <label className="flex items-center gap-3 py-2"><span className="flex-1"><b className="block text-[13px]">시장 위젯 불러오기 실패</b><span className="text-[13px] text-zinc-500">위젯 안에서만 · 5초 뒤 자동</span></span><Toggle on={app.x.widgetFail} onChange={(v) => app.setX((x) => ({ ...x, widgetFail: v }))} label="시장 위젯 불러오기 실패" /></label>
          <label className="flex items-center gap-3 py-2"><span className="flex-1"><b className="block text-[13px]">AI 사용량 다 씀</b><span className="text-[13px] text-zinc-500">메모 · 업데이트 · 스튜디오 안내</span></span><Toggle on={studio.creditOut} onChange={(v) => setStudio((s) => ({ ...s, creditOut: v }))} label="AI 사용량 다 씀" /></label>
          <p className="mb-1.5 mt-4 text-[13px] font-bold text-zinc-500">빠른 이동</p>
          <div className="grid grid-cols-3 gap-1.5">{J.map(([I, l, f]) => <button key={l} onClick={() => { f(); }} className="m-press flex flex-col items-center gap-1 rounded-xl bg-zinc-50 px-1 py-2.5 text-[13px] font-bold hover:bg-zinc-100"><I className="h-4 w-4" />{l}</button>)}</div>
          <p className="mb-1.5 mt-4 text-[13px] font-bold text-zinc-500">처음 안내 · 넛지</p>
          <div className="grid grid-cols-2 gap-1.5">
            <button disabled={!inApp} onClick={() => { setOpen(false); setOverlay(null); setCoachPending(false); setCoach({ step: -1 }); }} className="m-press flex h-10 items-center justify-center gap-1.5 rounded-xl bg-zinc-50 text-[13px] font-bold hover:bg-zinc-100 disabled:opacity-40"><Compass className="h-4 w-4" />코치마크 보기</button>
            <button onClick={() => resetNudges()} className="m-press flex h-10 items-center justify-center gap-1.5 rounded-xl bg-zinc-50 text-[13px] font-bold hover:bg-zinc-100"><BellRing className="h-4 w-4" />넛지 다시 띄우기</button>
          </div>
          <button onClick={() => { setStudio((s) => ({ ...s, quizDone: null, made: INITIAL_STUDIO.made, job: null, view: "home", mini: false, playing: false, t: 141, badge: null })); }} className="mt-3 flex h-9 w-full items-center justify-center gap-1.5 rounded-xl text-[13px] font-bold text-zinc-500 hover:bg-zinc-50"><RotateCcw className="h-3.5 w-3.5" />스튜디오 기록 초기화</button>
        </div>
      )}
    </>
  );
}

function Shell() {
  const app = useApp();
  const { route, nav, demo, sideOpen, coach, coachPending, setCoachPending, setCoach } = app;
  (window as unknown as { __app: typeof app }).__app = app;
  useEffect(() => { document.documentElement.style.setProperty("--k", demo.speed); }, [demo.speed]);
  useEffect(() => { document.documentElement.style.setProperty("--side", ["intro", "login", "terms", "pick"].includes(route.name) ? "0px" : sideOpen ? "250px" : "72px"); }, [sideOpen, route.name]);
  /* v2: 종목 고르기를 마치고 처음 홈에 오면 코치마크를 시작 */
  useEffect(() => {
    if (!coachPending || coach || route.name !== "home") return;
    const t = window.setTimeout(() => { setCoachPending(false); setCoach({ step: -1 }); }, 600);
    return () => window.clearTimeout(t);
  }, [coachPending, coach, route.name, setCoachPending, setCoach]);
  if (route.name === "intro") return <div key="intro" className="m-in h-full"><Intro />{!API_MODE && <DemoTools />}</div>;
  if (route.name === "login") return <div key="login" className="m-in h-full"><Login />{!API_MODE && <DemoTools />}</div>;
  if (route.name === "terms" || route.name === "pick") return <div key={route.name} className="m-in h-full">{route.name === "terms" ? <Terms /> : <Pick />}{!API_MODE && <DemoTools />}</div>;
  return (
    <div key="app" className="m-in flex h-full bg-[#f3f4f6]">
      <Sidebar />
      <Main navKey={nav}><Screen /></Main>
      <StudioColumn />
      <AddStock /><Settings /><Feedback /><Trash /><LogoutConfirm /><AudioPopup /><ReportPopup /><CreditPopup /><ChargePopup />
      <NudgeHost />
      <InboxPanel />
      <MarketDetailHost />
      <OfflineBand />
      <SampleNotice />
      <Coach />
      {!API_MODE && <DemoTools />}
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <SnackHost>
        <ApiNotes />
        <Shell />
      </SnackHost>
    </AppProvider>
  );
}
