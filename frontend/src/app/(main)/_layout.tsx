import React, { useEffect, useRef, useState } from 'react';
import { useCoach } from '@/store/coach';
import { View, useWindowDimensions } from 'react-native';
import { Redirect, Stack, useGlobalSearchParams, usePathname, useRouter } from 'expo-router';
import { env } from '@/config/env';
import { coachPlace } from '@/lib/coachTarget';
import { useIntroSeen } from '@/lib/introSeen';
import { useAuth } from '@/store/auth';
import { mockPopular, mockRecentSearches, mockSideProfile, mockStudioHead } from '@/ui/layout/web/WebShell.mock';
import { useSideStocks } from '@/ui/layout/web/useSideStocks';
import { WebShell } from '@/ui/layout/web/WebShell';
import type { SideKey, SideSearchHit } from '@/ui/layout/web/WebShell.types';
import { useAddStockSearch } from '@/ui/screens/stocks/useAddStockSearch';
import { WebAddStockDialog } from '@/ui/screens/stocks/web/AddStockDialog';
import { useMyMock } from '@/store/myMock';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';
import { planKey, withCurrentPlan } from '@/ui/screens/my/planLabel';
import { useUsageView } from '@/ui/screens/my/useUsageView';
import Constants from 'expo-constants';
import { legalDocument } from '@/ui/screens/auth/Auth.mock';
import { mockCreditDefault, mockCreditPacks, mockPayMethods, mockDataSources, mockInbox, mockOss, mockPlanCompare, mockPlanDefault, mockPlanNotes, mockPlans, mockReportKinds, mockTracked, mockWithdrawCounts } from '@/ui/screens/my/My.mock';
import { WebFeedback } from '@/ui/screens/my/web/Feedback';
import { WebInbox } from '@/ui/screens/my/web/Inbox';
import { WebSettings, type SettingsTab } from '@/ui/screens/my/web/Settings';
import { useTodayQuizView } from '@/ui/screens/studio/useTodayQuiz';
import { useTrashData } from '@/ui/screens/my/useTrashData';
import { WebTrash } from '@/ui/screens/my/web/Trash';
import { chapterAt, fmt, useStudioPlayer } from '@/store/studioPlayer';
import { mockAudioEpisode, mockAudioGen, mockAudioPeriods, mockAudioStocks, mockLabDisclaimer, mockLabNote, mockLabVars, mockLastClose, mockReport, mockReportStocks, mockStudioFeatures } from '@/ui/screens/studio/Studio.mock';
import { WebFail, WebGen, WebMini, WebPlayer } from '@/ui/screens/studio/web/Audio';
import { WebReportPopup, WebReportSum } from '@/ui/screens/studio/web/Report';
import { WebLab, WebLabResult, WebQuiz } from '@/ui/screens/studio/web/QuizLab';
import { labResultGroups } from '@/ui/screens/studio/labParts';
import { labStockFor, useLabStocks, useRunLab } from '@/ui/screens/studio/useLabRun';
import { useLabVars } from '@/ui/screens/studio/useLabVars';
import { WebAudioPopup } from '@/ui/screens/studio/web/AudioPopup';
import type { StudioKind } from '@/ui/screens/studio/Studio.types';
import { WebChargePopup, WebCreditPopup, WebUsageSheet } from '@/ui/screens/studio/web/Credit';
import { WebStudioHome } from '@/ui/screens/studio/web/StudioHome';
import { useUI } from '@/store/ui';
import { ConfirmDialog } from '@/ui/shared/ConfirmDialog';
import { ContextMenu } from '@/ui/shared/ContextMenu';
import { WebSnackbar } from '@/ui/shared/Snackbar';
import { size, webColor } from '@/ui/theme';
import { useTheme } from '@/store/theme';

const NOT_YET = '아직 연결되지 않았어요 · 데이터는 그대로예요';

/** 주소 → 사이드바에서 고른 곳 */
function sideKeyOf(path: string): SideKey {
  if (path === '/' || path === '/index') return 'home';
  if (path.startsWith('/updates')) return 'updates';
  if (path.startsWith('/journal')) return 'journal';
  const m = /^\/stocks\/([^/]+)/.exec(path);
  if (m) return { stock: m[1] };
  if (path.startsWith('/stocks')) return 'mine';
  return null;
}

/**
 * 웹 로그인 후 영역: UI v2 WebShell (사이드바 250/72 · 가운데 · 스튜디오 열 436/96).
 * 앱(안드로이드·iOS)은 같은 폴더의 _layout.native.tsx.
 * mock 단계: 사이드바·스튜디오 머리 숫자는 WebShell.mock. 설정·휴지통·피드백·알림함 창은 이 셸에서 연다 (⑨-3).
 */
export default function MainLayout() {
  const status = useAuth((s) => s.status);
  /* 로그인한 채 다른 사용자로 바뀌면(A → B) 커짐 → 아래 Stack 을 다시 마운트해 열린 화면을 새 사용자 값으로 (store/auth sessionKey) */
  const sessionKey = useAuth((s) => s.sessionKey);
  /* 로그인 전: 서비스 설명을 본 적 없으면 /intro (원본 웹처럼 처음 한 번만), 봤으면 /login */
  const introSeen = useIntroSeen(status === 'signedOut');
  const router = useRouter();
  const pathname = usePathname();
  const { width } = useWindowDimensions();
  const [sideOpen, setSideOpen] = useState(true);
  /* 원본 studio.tsx: 화면 폭 1280 이하면 처음에 접힘 */
  const [studioOpen, setStudioOpen] = useState(() => width > size.studioNarrow);
  const dark = useTheme((s) => s.dark);
  const setDark = useTheme((s) => s.setDark);
  /* 사용법 안내 화면 이동 (원본 웹 coach.tsx: 첫 카드 홈 → ①②③ 종목 보드(메모 창은 보드가 엶) → ④ 홈 + 스튜디오 열 펼침 → 끝나면 홈) */
  /* ⑥ 사이드바 종목: 순서 끌기 · 우클릭/⋯ 메뉴 · + 종목 추가 (실제 모드면 GET /stocks 와 저장 API, mock 이면 이 셸 안에서만).
     사용법 안내 ①②③ 대상 종목(내 첫 종목)도 이 순서 */
  const [sideStocks, setSideStocks] = useSideStocks();
  const coachStep = useCoach((s) => s.step);
  const replayCoach = useCoach((s) => s.replay);
  const coachWas = useRef<number | null>(null);
  useEffect(() => {
    const prev = coachWas.current;
    coachWas.current = coachStep;
    if (coachStep === prev) return;
    if (coachStep == null || coachStep === -1) {
      /* 첫 카드는 홈에서 (원본 go home) · 끝나도 홈 */
      if ((prev != null || coachStep === -1) && pathname !== '/') router.navigate('/');
      return;
    }
    /* ①②③ 보드: mock 모드는 000660, 실제 모드는 내 첫 종목(사이드바 순서). 내 종목이 없으면 홈에 머묾 → 가운데 카드 (lib/coachTarget) */
    const place = coachPlace(coachStep, !env.useMock, sideStocks.map((s) => s.stock_code));
    if (place.kind === 'board') {
      if (!pathname.startsWith(`/stocks/${place.code}`)) router.navigate({ pathname: '/stocks/[code]', params: { code: place.code } });
    } else if (place.kind === 'home') {
      if (pathname !== '/') router.navigate('/');
    } else {
      router.navigate('/');
      useStudioPlayer.getState().setWebView('home');
      setTimeout(() => setStudioOpen(true), 0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coachStep]);
  /* + 종목 추가 창 후보: 실제 모드면 서버 검색 · 많이 찾는 종목 */
  const addSearch = useAddStockSearch();
  /* 투자 실험실 변수 '지금 값': 실제 모드면 GET /market/macro (2026-11-21) */
  const labVars = useLabVars();
  const labStocks = useLabStocks();
  const runLab = useRunLab();
  const [smenu, setSmenu] = useState<{ code: string; at: { x: number; y: number } } | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [ask, setAsk] = useState<string | null>(null);
  const [snack, setSnack] = useState<{ msg: string; undo?: () => void; check?: boolean } | null>(null);
  /* ⑨-3a 설정 창(내 프로필) · 사이드바 로그아웃 확인 (mock: 프로필은 화면 상태만) */
  const [settings, setSettings] = useState<SettingsTab | null>(null);
  const [logoutAsk, setLogoutAsk] = useState(false);
  const signOut = useAuth((s) => s.signOut);
  /* 내 프로필: 로그인한 사용자 (저장은 PATCH /me). mock 모드만 예시 프로필 */
  const { profile: myProfile, save: saveMyProfile, plan: myPlan } = useMyProfile();
  /* AI 사용량: 실제 모드면 GET /me/usage (2026-11-22), mock 모드면 My.mock */
  const usage = useUsageView();
  const myNoti = useMyMock((s) => s.noti);
  const setMyNoti = useMyMock((s) => s.setNoti);
  /* ⑨-3c 휴지통 · 피드백 · 알림함 (mock: 복원·읽음은 화면 상태만, 영구 삭제·보내기는 연결 안 됨) */
  const [trashOpen, setTrashOpen] = useState(false);
  const [fbOpen, setFbOpen] = useState(false);
  const [inboxOpen, setInboxOpen] = useState(false);
  const unread = useMyMock((s) => s.unread);
  const readNotif = useMyMock((s) => s.read);
  const readAll = useMyMock((s) => s.readAll);
  const uiToast = useUI((s) => s.toast);
  /* ⑧-8a 스튜디오: 사용량 창 · PLUS 창(다 쓴 뒤 만들기) · 충전 창. 결제·만들기는 연결 안 됨 */
  const [studioPop, setStudioPop] = useState<'usage' | 'credit' | 'charge' | 'audio' | 'report' | null>(null);
  const usageSpent = usage.paused || usage.usage_pct >= 100;
  const studioFeat = (k: StudioKind) => {
    if (k !== 'quiz' && usageSpent) return setStudioPop('credit');
    if (k === 'audio') return setStudioPop('audio');
    if (k === 'report') return setStudioPop('report');
    useStudioPlayer.getState().setWebView(k === 'quiz' ? 'quiz' : 'lab');
  };
  /* ⑧-8b 오디오: 만들기 · 재생 mock 상태 (store/studioPlayer). 개발 빌드(__DEV__)에서만 ?studio_fail=1 이면 다음 만들기가 실패 (확인용 · 배포 빌드는 무시) */
  const sp = useStudioPlayer();
  /* 오늘의 퀴즈: 실제 모드면 DB 문제 (퀴즈 화면을 열었을 때만 읽음) */
  const quiz = useTodayQuizView(sp.webView === 'quiz');
  const labStock = labStocks.find((s) => s.stock_code === sp.labCode) ?? labStocks[0];
  const spItem = sp.made.find((m) => m.id === sp.cur);
  /* ⑧-8c 주간보고서: 스튜디오 열 요약 · 가운데 /report 자세히 */
  const repItem = sp.made.find((m) => m.id === sp.curReport && m.kind === 'report');
  const labItem = sp.made.find((m) => m.id === sp.curLab && m.kind === 'lab');
  const repStocks = mockReportStocks.filter((s) => (repItem?.codes ?? []).includes(s.stock_code));
  const { studio_fail } = useGlobalSearchParams<{ studio_fail?: string }>();
  const unreadShown = mockInbox.filter((n) => unread.includes(n.id) && (n.kind === 'ai' ? myNoti.ai : myNoti.studio)).length;
  const say = (x: { msg: string; undo?: () => void; check?: boolean }) => {
    setSnack(x);
    setTimeout(() => setSnack((c) => (c === x ? null : c)), 4000);
  };
  const nameOf = (c: string) => sideStocks.find((x) => x.stock_code === c)?.name ?? '';
  const jo = (w: string) => {
    const c = w.charCodeAt(w.length - 1);
    return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? '을' : '를';
  };
  /* 휴지통: 실제 모드면 GET /trash · 복원 · 영구 삭제 (2026-11-22), mock 이면 store/myMock */
  const trashData = useTrashData(() => say({ msg: '아직 연결되지 않았어요 · 데이터는 그대로예요' }));
  if (status !== 'signedIn') {
    if (status === 'loading' || introSeen === null) return null;
    return <Redirect href={introSeen ? '/login' : '/intro'} />;
  }

  /* 로그아웃: mock 세션을 지우고 로그인으로 replace (로그인 뒤 화면은 위 Redirect 로 다시 못 들어옴) */
  const logout = () => {
    void signOut().finally(() => router.replace('/login'));
  };
  const openStock = (code: string) => router.navigate({ pathname: '/stocks/[code]', params: { code } });
  const search = (q: string): SideSearchHit[] =>
    sideStocks.filter((s) => s.name.includes(q) || s.stock_code.includes(q)).map((s) => ({ key: `s${s.stock_code}`, title: s.name, sub: s.stock_code }));

  const cur = smenu ? sideStocks.find((x) => x.stock_code === smenu.code) : undefined;
  return (
    <View style={{ flex: 1 }}>
    <WebShell
      sidebar={{
        open: sideOpen,
        onToggle: () => setSideOpen((o) => !o),
        current: sideKeyOf(pathname),
        stocks: sideStocks,
        /* 설정에서 바꾼 이름·소개를 사이드바 프로필에도 (mock 상태) */
        profile: { ...mockSideProfile, name: myProfile.name, job: myProfile.intro, photoUrl: myProfile.photoUrl ?? null },
        unreadNotifs: unreadShown,
        dark,
        recentSearches: mockRecentSearches,
        popular: mockPopular,
        onSearch: search,
        onPickSearch: (h) => openStock(h.key.slice(1)),
        onPickRecent: (name) => {
          const s = sideStocks.find((x) => x.name === name);
          if (s) openStock(s.stock_code);
        },
        onPickPopular: (code) => {
          if (sideStocks.some((s) => s.stock_code === code)) openStock(code);
        },
        onNavigate: (to) => router.navigate(to === 'home' ? '/' : to === 'mine' ? '/stocks' : `/${to}`),
        onOpenStock: openStock,
        onStockMenu: (code, at) => setSmenu({ code, at }),
        onReorderStocks: (codes) =>
          setSideStocks((all) => {
            const inG = new Set(codes);
            let i = 0;
            return all.map((x) => {
              if (!inG.has(x.stock_code)) return x;
              const c = codes[i++];
              return all.find((y) => y.stock_code === c) ?? x;
            });
          }),
        onAddStock: () => setAddOpen(true),
        onBell: () => setInboxOpen((o) => !o),
        onToggleDark: () => setDark(!dark),
        onTrash: () => setTrashOpen(true),
        onSettings: () => setSettings('내 프로필'),
        onFeedback: () => setFbOpen(true),
        onHelp: () => router.navigate('/help'),
        onProfile: () => setSettings('내 프로필'),
        onLogout: () => setLogoutAsk(true),
      }}
      studio={{
        open: studioOpen,
        onToggle: () => setStudioOpen((o) => !o),
        /* AI 사용량은 설정 창(My.mock)과 같은 값 */
        ...mockStudioHead,
        usagePct: usage.usage_pct,
        onUsage: () => setStudioPop('usage'),
        /* 접힌 열: 만드는 중인 기능에 '·' 점 (원본 studio.tsx 177 — 퀴즈 제외) */
        badges: sp.job?.status === 'run' ? { [sp.job.kind]: '·' } : undefined,
        onFeature: (k) => { setStudioOpen(true); studioFeat(k); },
        /* ⑧-8a 스튜디오 홈 (원본 studio.tsx Home). 오디오·보고서·실험실·퀴즈 화면은 8b~8d */
        content: (
          <View style={{ flex: 1 }}>
            {sp.webView === 'gen' && sp.job ? <WebGen job={sp.job} steps={sp.job.kind === 'report' ? mockReport.web_steps : mockAudioGen.steps} />
              : sp.webView === 'fail' ? <WebFail kind={sp.job?.kind ?? 'audio'} onHome={() => { sp.dropFailed(); sp.setWebView('home'); }} onRetry={() => { sp.retry(); sp.setWebView('gen'); }} />
              : sp.webView === 'quiz' ? <WebQuiz q={quiz} done={sp.quizPick} onBack={() => sp.setWebView('home')} onSubmit={sp.submitQuiz} />
              : sp.webView === 'lab' ? (
                <WebLab
                  vars={labVars}
                  stocks={labStocks}
                  code={labStock.stock_code}
                  dirs={sp.labDirs}
                  note={mockLabNote}
                  onBack={() => sp.setWebView('home')}
                  onPick={(c) => sp.setLab({ code: c })}
                  onDir={(i, d) => sp.setLab({ dirs: sp.labDirs.map((x, j) => (j === i ? d : x)) })}
                  onReset={() => sp.setLab({ dirs: mockLabVars.map(() => '유지') })}
                  onRun={async () => {
                    if (await runLab(labStock, sp.labDirs)) sp.setWebView('labResult');
                  }}
                />
              )
              : sp.webView === 'labResult' && labItem?.lab ? (
                <WebLabResult
                  stock={labStockFor(labStocks, labItem.lab)}
                  vars={labVars}
                  groups={labResultGroups(labItem.lab)}
                  disclaimer={mockLabDisclaimer}
                  onBack={() => sp.setWebView('home')}
                  onMemo={() => openStock(labItem.lab?.code ?? '')}
                  onAgain={() => { sp.setLab({ code: labItem.lab?.code, dirs: labItem.lab?.dirs }); sp.setWebView('lab'); }}
                />
              )
              : sp.webView === 'report' && repItem ? (
                <WebReportSum
                  rep={mockReport}
                  item={repItem}
                  stocks={repStocks}
                  allDefault={repStocks.length === mockReportStocks.length}
                  onBack={() => sp.setWebView('home')}
                  onDetail={() => router.navigate('/report')}
                />
              )
              : sp.webView === 'player' && spItem ? (
                <WebPlayer
                  item={spItem}
                  ep={mockAudioEpisode}
                  t={sp.t}
                  playing={sp.playing}
                  speed={sp.speed}
                  onBack={() => { sp.leavePlayer(); sp.setWebView('home'); }}
                  onToggle={sp.toggle}
                  onSeek={sp.seek}
                  onSpeed={() => sp.nextSpeed([1, 1.5, 2])}
                  onRemake={() => setStudioPop('audio')}
                />
              ) : (
                <WebStudioHome
                  features={mockStudioFeatures}
                  made={sp.made}
                  bottomPad={sp.mini && spItem ? 60 : 0}
                  spent={usageSpent}
                  refill={usage.usage_refill}
                  onFeature={studioFeat}
                  onOpenMade={(m) => {
                    if (m.kind === 'report') { sp.openReport(m.id); return sp.setWebView('report'); }
                    if (m.kind === 'lab') { sp.openLab(m.id); return sp.setWebView('labResult'); }
                    if (m.kind !== 'audio') return say({ msg: NOT_YET });
                    sp.select(m.id);
                    sp.setMini(false);
                    sp.setWebView('player');
                  }}
                  onQuickPlay={(m) => { if (sp.cur === m.id && sp.mini) sp.toggle(); else sp.play(m.id); sp.setMini(true); }}
                  onBuyCredit={() => setStudioPop('charge')}
                  onChangePlan={() => setSettings('사용량')}
                />
              )}
            {sp.mini && spItem && sp.webView !== 'player' ? (
              <WebMini
                title={spItem.title}
                sub={`지금 · ${mockAudioEpisode.chapters[chapterAt(sp.t)][1]} · ${fmt(sp.t)}`}
                progress={sp.t / mockAudioEpisode.dur}
                playing={sp.playing}
                onOpen={() => { sp.setMini(false); sp.setWebView('player'); }}
                onToggle={sp.toggle}
                onClose={sp.closeMini}
              />
            ) : null}
          </View>
        ),
      }}
    >
      <Stack key={sessionKey} screenOptions={{ headerShown: false, contentStyle: { backgroundColor: webColor.page }, animation: 'none' }} />
    </WebShell>
    <ContextMenu
      at={smenu?.at ?? null}
      items={
        cur
          ? [
              { label: cur.status === 'holding' ? '관심 종목으로 바꾸기' : '보유 종목으로 바꾸기', icon: 'move', run: () => {
                  const to = cur.status === 'holding' ? 'watching' : 'holding';
                  setSideStocks((all) => all.map((x) => (x.stock_code === cur.stock_code ? { ...x, status: to } : x)));
                  say({ msg: `${cur.name}${jo(cur.name)} ${to === 'holding' ? '보유' : '관심'} 종목으로 바꿨어요`, check: true });
                } },
              { label: '기업정보 보기', icon: 'info', run: () => router.navigate({ pathname: '/stocks/[code]', params: { code: cur.stock_code, tab: 'info' } }) },
              '-',
              { label: '내 종목에서 빼기', icon: 'trash', danger: true, run: () => setAsk(cur.stock_code) },
            ]
          : []
      }
      onClose={() => setSmenu(null)}
    />
    <ConfirmDialog
      variant="web"
      danger
      open={!!ask}
      title="내 종목에서 뺄까요?"
      body="휴지통에서 다시 복원할 수 있어요."
      confirmLabel="빼기"
      onCancel={() => setAsk(null)}
      onConfirm={() => {
        const c = ask;
        setAsk(null);
        if (!c) return;
        const before = sideStocks;
        setSideStocks((all) => all.filter((x) => x.stock_code !== c));
        say({ msg: `${nameOf(c)}${jo(nameOf(c))} 내 종목에서 뺐어요`, undo: () => (setSideStocks(before), setSnack(null)) });
      }}
    />
    <WebAddStockDialog
      open={addOpen}
      /* 이미 담은 종목(흐리게) = 사이드바 종목 — 창은 종목코드만 봄 */
      mine={sideStocks.map((s) => ({ ...s, market: 'KOSPI', memo_count: 0, ai_count: 0, new_count: 0, price: null, change_pct: null, ai_ready: true }))}
      /* 후보: 실제 모드면 서버 검색 · 많이 찾는 종목 (useAddStockSearch), mock 모드면 지금처럼 mock 후보 */
      universe={addSearch.universe}
      popular={addSearch.popular}
      remote={addSearch.remote}
      onQueryChange={addSearch.onQueryChange}
      onClose={() => setAddOpen(false)}
      onAdd={(code, hold) => {
        const u = addSearch.universe.find((x) => x.stock_code === code);
        if (!u) return;
        setSideStocks((all) => [...all, { stock_code: u.stock_code, name: u.name, status: hold, logo: u.logo, logo_bg: u.logo_bg, logo_ink: u.logo_ink }]);
        say({ msg: `${u.name}${jo(u.name)} ${hold === 'holding' ? '보유' : '관심'} 종목에 추가했어요`, check: true });
      }}
    />
    <WebSettings
      open={!!settings}
      tab={settings ?? '내 프로필'}
      profile={myProfile}
      counts={mockWithdrawCounts}
      onTab={setSettings}
      onClose={() => setSettings(null)}
      onChangeProfile={({ name, intro }) => {
        if (!name) return say({ msg: '이름은 비워 둘 수 없어요' });
        if (name !== myProfile.name || intro !== myProfile.intro) {
          saveMyProfile({ name, intro }).then(
            () => say({ msg: '프로필을 저장했어요', check: true }),
            (e: unknown) => say({ msg: e instanceof Error && e.message ? e.message : '프로필을 저장하지 못했어요' }),
          );
        }
      }}
      onPhoto={() => say({ msg: '아직 연결되지 않았어요 · 데이터는 그대로예요' })}
      onPhotoDelete={() => say({ msg: '지울 사진이 없어요' })}
      onLogout={() => { setSettings(null); logout(); }}
      onWithdraw={() => say({ msg: '아직 탈퇴 기능은 연결되지 않았어요 · 데이터는 그대로예요' })}
      noti={myNoti}
      onNoti={(n) => {
        const on = n.ai !== myNoti.ai ? n.ai : n.studio;
        setMyNoti(n);
        say({ msg: on ? '알림을 켰어요 · 알림함에 다시 보여요' : '알림을 껐어요 · 알림함에서도 안 보여요', check: true });
      }}
      /* 사용량 % · 갱신일: GET /me/usage · 플랜 이름 · 현재 플랜: 로그인 사용자 plan */
      usage={usage}
      tracked={mockTracked}
      onOpenMemo={(code) => { setSettings(null); openStock(code); }}
      plans={withCurrentPlan(mockPlans, planKey(myPlan))}
      compare={mockPlanCompare}
      notes={mockPlanNotes}
      plan_default={mockPlanDefault}
      current_plan_key={planKey(myPlan)}
      onStartPlan={() => say({ msg: '결제는 아직 연결되지 않았어요' })}
      onExport={() => say({ msg: '내보내기는 아직 연결되지 않았어요' })}
      onWipe={() => say({ msg: '아직 연결되지 않았어요 · 데이터는 그대로예요' })}
      version={Constants.expoConfig?.version ?? ''}
      sources={mockDataSources}
      oss={mockOss}
      docs={{ terms: legalDocument('terms'), privacy: legalDocument('privacy'), invest: legalDocument('invest') }}
      onFeedback={() => { setSettings(null); setFbOpen(true); }}
      onReplayGuide={() => {
        /* 원본 overlays.tsx replay: 창을 닫고 첫 카드부터 */
        setSettings(null);
        replayCoach();
      }}
    />
    <WebTrash
      open={trashOpen}
      items={trashData.items}
      onClose={() => setTrashOpen(false)}
      onBack={() => setTrashOpen(false)}
      onRestore={(t) => {
        const it = trashData.restore(t);
        if (it) say({ msg: it.kind === '메모' ? '메모를 복원했어요 · 원래 종목 보드에 돌아갔어요' : it.kind === '종목' ? '종목을 복원했어요 · 메모도 함께 돌아왔어요' : '복원했어요', check: true });
      }}
      onUndo={trashData.undo}
      onPurge={trashData.purge}
    />
    <WebAudioPopup
      open={studioPop === 'audio'}
      stocks={mockAudioStocks}
      periods={mockAudioPeriods}
      lastClose={mockLastClose}
      onClose={() => setStudioPop(null)}
      onMake={({ codes, period, market }) => {
        setStudioPop(null);
        setStudioOpen(true);
        sp.setWebView('gen');
        sp.startAudio({ sub: `${codes.length}종목 · ${period} · ${market ? '증시 요약 포함' : '증시 요약 없음'}`, n: codes.length }, __DEV__ && studio_fail === '1');
      }}
    />
    <WebReportPopup
      open={studioPop === 'report'}
      stocks={mockReportStocks}
      sub={mockReport.web_period}
      onClose={() => setStudioPop(null)}
      onMake={({ codes, market }) => {
        setStudioPop(null);
        setStudioOpen(true);
        sp.setWebView('gen');
        sp.startReport({ sub: `${codes.length}종목${market ? ' · 국내 증시 흐름 포함' : ''} · ${mockReport.gen_range}`, codes, market }, __DEV__ && studio_fail === '1');
      }}
    />
    <WebUsageSheet open={studioPop === 'usage'} pct={usage.usage_pct} refill={usage.usage_refill} onClose={() => setStudioPop(null)} onBuyCredit={() => setStudioPop('charge')} onChangePlan={() => setSettings('사용량')} />
    <WebCreditPopup open={studioPop === 'credit'} onClose={() => setStudioPop(null)} onPlan={() => { setStudioPop(null); setSettings('사용량'); }} onCharge={() => setStudioPop('charge')} />
    <WebChargePopup open={studioPop === 'charge'} packs={mockCreditPacks} default_credits={mockCreditDefault} methods={mockPayMethods} onClose={() => setStudioPop(null)} onPay={() => say({ msg: '결제는 아직 연결되지 않았어요' })} />
    <WebFeedback open={fbOpen} kinds={mockReportKinds} onClose={() => setFbOpen(false)} onSend={() => say({ msg: '아직 연결되지 않았어요' })} />
    <WebInbox
      open={inboxOpen}
      left={(sideOpen ? 250 : 72) + 8}
      items={mockInbox}
      unread={unread}
      noti={myNoti}
      onClose={() => setInboxOpen(false)}
      onOpen={(n) => {
        setInboxOpen(false);
        readNotif(n.id);
        if (n.kind === 'ai' && n.stock_code) openStock(n.stock_code);
        else setStudioOpen(true);
      }}
      onReadAll={readAll}
      onSettings={() => { setInboxOpen(false); setSettings('알림'); }}
    />
    <ConfirmDialog
      variant="web"
      danger
      open={logoutAsk}
      title="로그아웃할까요?"
      body="이 기기에서 로그아웃해요."
      confirmLabel="로그아웃"
      onCancel={() => setLogoutAsk(false)}
      onConfirm={() => { setLogoutAsk(false); logout(); }}
    />
    <WebSnackbar visible={!!snack || !!uiToast} message={snack?.msg ?? uiToast?.message ?? ''} onUndo={snack?.undo} check={snack?.check} style={{ position: 'absolute', bottom: 30, alignSelf: 'center' }} />
    </View>
  );
}
