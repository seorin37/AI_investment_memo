import { create } from 'zustand';
import { useUI } from '@/store/ui';
import { mockAudioEpisode, mockAudioGen, mockLabStocks, mockLabVars, mockMade, mockReport, type LabDir } from '@/ui/screens/studio/Studio.mock';
import type { MadeItem, StudioKind } from '@/ui/screens/studio/Studio.types';
import { registerUserReset } from '@/lib/sessionReset';
import { env } from '@/config/env';

/**
 * 스튜디오 만들기 · 재생 mock 상태 (앱·웹 같이 씀, 메모리에만).
 * - 만들기: 크레딧 차감 없이 단계만 진행 (원본 runGen 시각) → 완료 / 실패
 * - 재생: 소리 없이 시간만 흐르는 타이머 (원본 tick). 미니 플레이어는 앱 탭 레이아웃 · 웹 스튜디오 열에서 이 상태를 읽음
 */
export type StepState = 'wait' | 'run' | 'done' | 'bad';
export interface GenJob {
  kind: 'audio' | 'report';
  sub: string;
  n: number;
  codes: string[];
  market: boolean;
  pct: number;
  steps: StepState[];
  status: 'run' | 'fail' | 'done';
  fail: boolean;
}
export type WebStudioView = 'home' | 'gen' | 'fail' | 'player' | 'report' | 'quiz' | 'lab' | 'labResult';
const KIND_T = {
  audio: { bad: '오디오를 만들지 못했어요', done: '오디오가 완성됐어요' },
  report: { bad: '보고서를 만들지 못했어요', done: '주간보고서가 완성됐어요' },
};

interface StudioPlayerState {
  made: MadeItem[];
  job: GenJob | null;
  /** 앱 만드는 중 화면이 보이는 중 (끝나면 그 화면이 플레이어로 넘어감) */
  genVisible: boolean;
  webView: WebStudioView;
  cur: string | null;
  playing: boolean;
  t: number;
  speed: number;
  mini: boolean;
  /** 앱: 완성되면 결과 화면(플레이어 · 보고서)으로 넘어가라는 신호 */
  openPlayer: number;
  /** 지금 보는 주간보고서 */
  curReport: string | null;
  /** 방금 완성된 결과 종류 (openPlayer 신호와 같이) */
  openKind: 'audio' | 'report';
  startAudio(p: { sub: string; n: number; codes?: string[]; market?: boolean }, fail?: boolean): void;
  /** server를 주면(실제 모드) 단계 표시는 그대로 하고 완성은 서버 결과를 기다린다 (2026-11-23) */
  startReport(p: { sub: string; codes: string[]; market: boolean }, fail?: boolean, server?: () => Promise<MadeItem>): void;
  openReport(id: string): void;
  /** 투자 실험실: 지금 보는 결과 · 실험 실행(크레딧 차감 없음)으로 만든 항목에 추가 */
  curLab: string | null;
  addLab(item: MadeItem): void;
  openLab(id: string): void;
  /** 서버 만든 항목으로 바꾸기. 이번 세션에서 만든 mock 오디오·보고서(server 아님)는 위에 남긴다 (2026-11-23) */
  setServerMade(items: MadeItem[]): void;
  /** 만든 항목 목록에서 빼기 (삭제 = 휴지통, 2026-11-24). 서버 호출은 studioItems.useRemoveMade */
  removeMade(id: string): void;
  /** 실험실 화면에서 고른 종목 · 조건 (원본 labStk · lab) */
  labCode: string;
  labDirs: LabDir[];
  setLab(p: { code?: string; dirs?: LabDir[] }): void;
  /** 넛지 → 스튜디오 기능 열기 요청 (원본 nudge.tsx useStudioOpen). codes: 보고서·오디오 창에서 미리 고를 종목. _layout 이 받아서 처리 후 비움 */
  ask: { kind: StudioKind; codes?: string[] } | null;
  askStudio(kind: StudioKind, codes?: string[]): void;
  clearAsk(): void;
  /** 오늘의 퀴즈 제출 (화면 상태만) */
  retry(): void;
  dropFailed(): void;
  setGenVisible(v: boolean): void;
  setWebView(v: WebStudioView): void;
  /** 플레이어 열기 전 항목 고르기 (다른 항목이면 처음부터, 재생은 멈춤) */
  select(id: string): void;
  /** 플레이어에서 나갈 때: 듣던 중이면 미니로 */
  leavePlayer(): void;
  play(id: string, from0?: boolean): void;
  toggle(): void;
  seek(t: number): void;
  nextSpeed(steps: number[]): void;
  setMini(v: boolean): void;
  closeMini(): void;
  /** 로그아웃 · 계정 전환: 만드는 중 · 재생 타이머를 먼저 멈추고 처음 만들어졌을 때 상태로 */
  reset(): void;
}

const DUR = mockAudioEpisode.dur;
let genT: ReturnType<typeof setTimeout>[] = [];
let playT: ReturnType<typeof setInterval> | null = null;
/* 실제 모드 보고서 다시 시도에 쓸 서버 호출 */
let lastServer: (() => Promise<MadeItem>) | null = null;

export const useStudioPlayer = create<StudioPlayerState>((set, get) => {
  const step = (i: number, s: StepState, pct?: number) =>
    set((st) => (st.job ? { job: { ...st.job, steps: st.job.steps.map((x, j) => (j === i ? s : x)), pct: pct ?? st.job.pct } } : st));
  const runPlay = (on: boolean) => {
    if (playT) clearInterval(playT);
    playT = null;
    if (!on) return;
    playT = setInterval(() => {
      const { t, speed } = get();
      const nt = Math.min(DUR, t + 0.25 * speed);
      set({ t: nt });
      if (nt >= DUR) { set({ playing: false }); runPlay(false); }
    }, 250);
  };
  /* 실제 모드 주간보고서: 앞 단계는 시간으로 진행하고, 마지막 단계는 서버 완성(또는 실패)을 기다린다 */
  const runServer = (server: () => Promise<MadeItem>) => {
    genT.forEach(clearTimeout);
    genT = [];
    const T = (fn: () => void, ms: number) => genT.push(setTimeout(fn, ms));
    T(() => step(0, 'run', 8), 300);
    T(() => { step(0, 'done'); step(1, 'run', 35); }, 2500);
    T(() => { step(1, 'done'); step(2, 'run', 70); }, 9000);
    server().then(
      (item) => {
        genT.forEach(clearTimeout);
        genT = [];
        const s = get();
        if (s.job?.kind !== 'report') return;
        const here = s.genVisible || s.webView === 'gen';
        set({ made: [item, ...s.made.filter((m) => m.id !== item.id)], job: null, curReport: item.id, openKind: 'report',
          webView: s.webView === 'gen' ? 'report' : s.webView, openPlayer: s.genVisible ? s.openPlayer + 1 : s.openPlayer });
        if (!here) useUI.getState().showToast(KIND_T.report.done);
      },
      (err: unknown) => {
        genT.forEach(clearTimeout);
        genT = [];
        const s = get();
        if (!s.job) return;
        const at = s.job.steps.findIndex((x) => x !== 'done');
        step(at < 0 ? 2 : at, 'bad');
        set({ job: get().job && { ...get().job!, status: 'fail' }, webView: s.webView === 'gen' ? 'fail' : s.webView });
        useUI.getState().showToast(err instanceof Error ? err.message : KIND_T.report.bad);
      },
    );
  };
  const run = (fail: boolean) => {
    genT.forEach(clearTimeout);
    genT = [];
    const T = (fn: () => void, ms: number) => genT.push(setTimeout(fn, ms));
    T(() => step(0, 'run', 8), 300);
    T(() => { step(0, 'done'); step(1, 'run', 35); }, 1500);
    if (fail) {
      T(() => {
        step(1, 'bad');
        const s = get();
        set({ job: s.job && { ...s.job, status: 'fail' }, webView: s.webView === 'gen' ? 'fail' : s.webView });
        if (s.job && !s.genVisible && s.webView !== 'gen') useUI.getState().showToast(KIND_T[s.job.kind].bad);
      }, 3000);
      return;
    }
    T(() => step(1, 'run', 60), 2400);
    T(() => { step(1, 'done'); step(2, 'run', 78); }, 3300);
    T(() => step(2, 'run', 92), 4300);
    T(() => step(2, 'done', 100), 5000);
    T(() => {
      const s = get();
      if (!s.job) return;
      const id = `m${Date.now()}`;
      const here = s.genVisible || s.webView === 'gen';
      if (s.job.kind === 'report') {
        const sub = `주간보고서 · ${s.job.n}종목 · ${mockReport.made_label}`;
        const rep: MadeItem = { id, kind: 'report', title: mockReport.title, sub, meta: sub, left: '30일 뒤 삭제', codes: s.job.codes, market: s.job.market };
        set({ made: [rep, ...s.made], job: null, curReport: id, openKind: 'report', webView: s.webView === 'gen' ? 'report' : s.webView, openPlayer: s.genVisible ? s.openPlayer + 1 : s.openPlayer });
        if (!here) useUI.getState().showToast(KIND_T.report.done);
        return;
      }
      const item: MadeItem = { id, kind: 'audio', title: mockAudioGen.result_title, sub: `오디오 · ${s.job.n}종목 · ${fmt(DUR)}`, meta: `오디오 · ${s.job.n}종목 · ${fmt(DUR)}`, left: '30일 뒤 삭제', dur: fmt(DUR), foot: s.job.sub };
      set({ made: [item, ...s.made], job: null, cur: id, openKind: 'audio', t: 0, mini: !here, playing: here, webView: s.webView === 'gen' ? 'player' : s.webView, openPlayer: s.genVisible ? s.openPlayer + 1 : s.openPlayer });
      runPlay(here);
      if (!here) useUI.getState().showToast(KIND_T.audio.done);
    }, 5500);
  };
  return {
    /* 실제 모드는 서버 목록(useStudioItemsSync)으로 채운다. 가짜 3개는 mock 모드에서만 */
    made: env.useMock ? mockMade : [],
    job: null,
    genVisible: false,
    webView: 'home',
    cur: null,
    playing: false,
    t: 0,
    speed: 1,
    mini: false,
    openPlayer: 0,
    curReport: null,
    openKind: 'audio',
    startAudio: (p, fail = false) => {
      set({ job: { kind: 'audio', sub: p.sub, n: p.n, codes: p.codes ?? [], market: !!p.market, pct: 0, steps: mockAudioGen.steps.map(() => 'wait'), status: 'run', fail } });
      run(fail);
    },
    startReport: (p, fail = false, server) => {
      set({ job: { kind: 'report', sub: p.sub, n: p.codes.length, codes: p.codes, market: p.market, pct: 0, steps: mockReport.steps.map(() => 'wait'), status: 'run', fail } });
      lastServer = server ?? null;
      if (server) runServer(server);
      else run(fail);
    },
    openReport: (id) => set({ curReport: id }),
    curLab: null,
    addLab: (item) => set((s) => ({ made: [item, ...s.made], curLab: item.id })),
    openLab: (id) => set({ curLab: id }),
    setServerMade: (items) =>
      set((s) => {
        const ids = new Set(items.map((m) => m.id));
        return { made: [...s.made.filter((m) => !m.server && !ids.has(m.id)), ...items] };
      }),
    removeMade: (id) => set((s) => ({ made: s.made.filter((m) => m.id !== id) })),
    labCode: mockLabStocks[0].stock_code,
    labDirs: mockLabVars.map((v) => v.def),
    setLab: (p) => set((s) => ({ labCode: p.code ?? s.labCode, labDirs: p.dirs ?? s.labDirs })),
    ask: null,
    askStudio: (kind, codes) => set({ ask: { kind, codes } }),
    clearAsk: () => set({ ask: null }),
    retry: () => {
      const j = get().job;
      if (!j) return;
      set({ job: { ...j, pct: 0, steps: j.steps.map(() => 'wait'), status: 'run', fail: false } });
      if (j.kind === 'report' && lastServer) runServer(lastServer);
      else run(false);
    },
    dropFailed: () => set((s) => (s.job?.status === 'fail' ? { job: null } : s)),
    setGenVisible: (v) => set({ genVisible: v }),
    setWebView: (v) => set({ webView: v }),
    select: (id) => set((s) => (s.cur === id ? { mini: true } : { cur: id, t: 0, playing: false, mini: true })),
    leavePlayer: () => set((s) => ({ mini: s.playing || s.t > 0 })),
    play: (id, from0 = false) => {
      const s = get();
      const same = s.cur === id && !from0;
      set({ cur: id, t: same ? s.t : 0, playing: true });
      runPlay(true);
    },
    toggle: () => {
      const s = get();
      const on = !s.playing;
      set({ playing: on, t: on && s.t >= DUR ? 0 : s.t });
      runPlay(on);
    },
    seek: (t) => set({ t: Math.max(0, Math.min(DUR, t)) }),
    nextSpeed: (steps) => set((s) => ({ speed: steps[(steps.indexOf(s.speed) + 1) % steps.length] })),
    setMini: (v) => set({ mini: v }),
    closeMini: () => { set({ mini: false, playing: false }); runPlay(false); },
    reset: () => {
      genT.forEach(clearTimeout);
      genT = [];
      runPlay(false);
      set(useStudioPlayer.getInitialState(), true);
    },
  };
});

/* 로그아웃 · 계정 전환 때 처음 상태로 (lib/sessionReset · store/auth.ts 가 실행) */
registerUserReset('studioPlayer', () => useStudioPlayer.getState().reset());

export const fmt = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
/** 지금 챕터 · 대본 줄 */
export const chapterAt = (t: number) => mockAudioEpisode.chapters.reduce((a, c, i) => (t >= c[0] ? i : a), 0);
export const lineAt = (t: number) => mockAudioEpisode.script.reduce((a, c, i) => (t >= c[0] ? i : a), 0);
