import React, { useCallback, useRef, useState } from 'react';
import { BackHandler, View } from 'react-native';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { env } from '@/config/env';
import { useAiStats, useMyStocks } from '@/hooks/queries';
import { useStudioPlayer } from '@/store/studioPlayer';
import { useUI } from '@/store/ui';
import { StudioColumnFrame } from '@/ui/layout/web/StudioColumnFrame';
import { mockStudioHead } from '@/ui/layout/web/WebShell.mock';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';
import { mockPayMethods } from '@/ui/screens/my/My.mock';
import { usePlanView } from '@/ui/screens/my/usePlanView';
import { useUsageView } from '@/ui/screens/my/useUsageView';
import { webColor } from '@/ui/theme';
import { mockAudioGen, mockLabDisclaimer, mockLabNote, mockLabVars, mockReport, mockStudioFeatures } from '../Studio.mock';
import type { StudioKind } from '../Studio.types';
import { audioOff, blockPlay } from '../appAudio';
import { epOf } from '../audioEp';
import { useAudioPick, useCreateAudio } from '../audioView';
import { labResultGroups } from '../labParts';
import { reportView, useCreateReport, useReportPickStocks } from '../reportView';
import { useAddMemo } from '../useAddMemo';
import { useLabMemo } from '../useLabMemo';
import { labStockFor, useLabStocks, useRunLab } from '../useLabRun';
import { useLabVars } from '../useLabVars';
import { labWatchDraft, labWatchItems, labWatchKey } from '../useLabWatch';
import { useQuizAnswer } from '../useQuizAnswer';
import { useTodayQuizView } from '../useTodayQuiz';
import { WebFail, WebGen, WebLabGen, WebPlayer } from '../web/Audio';
import { WebAudioPopup } from '../web/AudioPopup';
import { WebChargePopup, WebCreditPopup, WebUsageSheet } from '../web/Credit';
import { WebLab, WebLabResult, WebQuiz } from '../web/QuizLab';
import { WebReportPopup, WebReportSum } from '../web/Report';
import { WebStudioHome } from '../web/StudioHome';

const NOT_YET = '아직 연결되지 않았어요 · 데이터는 그대로예요';

/**
 * 앱 스튜디오 탭 = 웹 스튜디오 열(app/(main)/_layout.tsx)의 컴포넌트와 상태(store/studioPlayer webView)를 그대로 씀.
 * 웹과 다른 것: 폭 100% · 접기 없음 · 재생 모듈이 없는 동안 재생 막기(appAudio) · '메모에 추가'는 바로 저장(useAddMemo) ·
 * 요금제 화면과 메모 열기는 앱 화면으로. 미니 플레이어는 탭 레이아웃.
 */
export function StudioScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const sp = useStudioPlayer();
  const toast = useUI((s) => s.showToast);
  const { studio_fail } = useLocalSearchParams<{ studio_fail?: string }>();
  const usage = useUsageView();
  const spent = usage.paused || usage.usage_pct >= 100;
  const { plan } = useMyProfile();
  const planView = usePlanView();
  const nextPlan = planView.catalog.plans.find((x) => x.code === (plan === 'plus' ? 'pro' : 'plus'));
  const openPlans = () => router.push('/my-plans');
  const myStocks = useMyStocks();
  const aiStats = useAiStats();
  const head = env.useMock ? mockStudioHead : { stockCount: myStocks.data?.length ?? 0, aiMemoCount: aiStats.data?.linked_memos ?? 0 };

  const [pop, setPop] = useState<'usage' | 'credit' | 'charge' | 'audio' | 'report' | null>(null);
  const feature = (k: StudioKind) => {
    if (k !== 'quiz' && spent) return setPop('credit');
    if (k === 'audio' || k === 'report') return setPop(k);
    sp.setWebView(k === 'quiz' ? 'quiz' : 'lab');
  };

  const audioPick = useAudioPick(pop === 'audio');
  const createAudio = useCreateAudio();
  const reportPick = useReportPickStocks();
  const createReport = useCreateReport();
  const quiz = useTodayQuizView(sp.webView === 'quiz');
  const quizAns = useQuizAnswer(quiz.slug, quiz.ready);
  const labVars = useLabVars();
  const labStocks = useLabStocks();
  const runLab = useRunLab();
  const labStock = labStocks.find((s) => s.stock_code === sp.labCode) ?? labStocks[0];
  const item = sp.made.find((m) => m.id === sp.cur);
  const ep = epOf(item);
  const repItem = sp.made.find((m) => m.id === sp.curReport && m.kind === 'report');
  const rep = reportView(repItem);
  const labItem = sp.made.find((m) => m.id === sp.curLab && m.kind === 'lab');
  const labMemo = useLabMemo(labItem?.lab?.code, sp.webView === 'labResult');
  const addMemo = useAddMemo();

  /* 실험 중 화면 단계: 웹 _layout runLabWithGen 과 같음 */
  const [labGen, setLabGen] = useState<{ pct: number; at: number } | null>(null);
  const labBusy = useRef(false);
  const runLabWithGen = async () => {
    if (labBusy.current) return;
    labBusy.current = true;
    setLabGen({ pct: 33, at: 1 });
    const tick = setInterval(() => setLabGen((g) => (g && g.at === 1 ? { ...g, pct: Math.min(90, g.pct + 3) } : g)), 500);
    const ok = await runLab(labStock, sp.labDirs);
    clearInterval(tick);
    if (!ok) {
      setLabGen(null);
      labBusy.current = false;
      return;
    }
    setLabGen({ pct: 100, at: 3 });
    setTimeout(() => {
      setLabGen(null);
      labBusy.current = false;
      if (useStudioPlayer.getState().webView === 'lab') useStudioPlayer.getState().setWebView('labResult');
    }, 400);
  };

  useFocusEffect(
    useCallback(() => {
      /* 웹은 스튜디오 열이 늘 보이지만 앱은 다른 탭에 가려짐: 나가 있는 동안 완성되면 알림만 (화면이 안 바뀌게), 돌아오면 이어서 */
      const s = useStudioPlayer.getState();
      if (s.job) s.setWebView(s.job.status === 'fail' ? 'fail' : 'gen');
      /* 안드로이드 뒤로 = 웹의 ‹ 스튜디오 */
      const sub = BackHandler.addEventListener('hardwareBackPress', () => {
        const now = useStudioPlayer.getState();
        if (now.webView === 'home') return false;
        if (now.webView === 'player') now.leavePlayer();
        if (now.webView === 'fail') now.dropFailed();
        now.setWebView('home');
        return true;
      });
      return () => {
        sub.remove();
        const now = useStudioPlayer.getState();
        if (now.webView === 'gen') now.setWebView('home');
      };
    }, []),
  );

  const mini = sp.mini && !!item && sp.webView !== 'player';
  const view = () => {
    if (sp.webView === 'gen' && sp.job) return <WebGen job={sp.job} steps={sp.job.kind === 'report' ? mockReport.web_steps : mockAudioGen.steps} />;
    if (sp.webView === 'fail') return <WebFail kind={sp.job?.kind ?? 'audio'} onHome={() => { sp.dropFailed(); sp.setWebView('home'); }} onRetry={() => { sp.retry(); sp.setWebView('gen'); }} />;
    if (sp.webView === 'quiz') return <WebQuiz q={quiz} done={quizAns.done} locked={!quizAns.canSubmit} onBack={() => sp.setWebView('home')} onSubmit={quizAns.submit} />;
    if (sp.webView === 'lab' && labGen) return <WebLabGen pct={labGen.pct} at={labGen.at} />;
    if (sp.webView === 'lab')
      return (
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
          onRun={runLabWithGen}
        />
      );
    if (sp.webView === 'labResult' && labItem?.lab) {
      const lab = labItem.lab;
      return (
        <WebLabResult
          stock={labStockFor(labStocks, lab)}
          memo={labMemo}
          vars={labVars}
          groups={labResultGroups(lab)}
          disclaimer={mockLabDisclaimer}
          watch={labWatchItems(labResultGroups(lab))}
          watchState={(_w, i) => (lab.added?.[labWatchKey(lab.code, i)] || addMemo.isAdded(labItem.id, labWatchKey(lab.code, i)) ? 'added' : 'idle')}
          onWatch={lab.code ? (w, i) => addMemo.add({ code: lab.code, ...labWatchDraft(w, labItem.title), itemId: labItem.id, key: labWatchKey(lab.code, i), server: labItem.server }) : undefined}
          onBack={() => sp.setWebView('home')}
          onMemo={(id) => (id ? router.push({ pathname: '/memo/[id]', params: { id } }) : router.push({ pathname: '/memo/new', params: { code: lab.code, name: labStockFor(labStocks, lab).name } }))}
          onAgain={() => { sp.setLab({ code: lab.code, dirs: lab.dirs }); sp.setWebView('lab'); }}
        />
      );
    }
    if (sp.webView === 'report' && repItem)
      return <WebReportSum rep={rep.rep} item={repItem} stocks={rep.stocks} allDefault={rep.allDefault} onBack={() => sp.setWebView('home')} onDetail={() => router.push('/studio-report')} />;
    if (sp.webView === 'player' && item)
      return (
        <WebPlayer
          item={item}
          ep={ep}
          t={sp.t}
          playing={sp.playing}
          speed={sp.speed}
          playOff={audioOff}
          onBack={() => { sp.leavePlayer(); sp.setWebView('home'); }}
          onToggle={() => !blockPlay() && sp.toggle()}
          onSeek={sp.seek}
          onSpeed={() => sp.nextSpeed([1, 1.5, 2])}
          onRemake={() => setPop('audio')}
        />
      );
    return (
      <WebStudioHome
        features={mockStudioFeatures}
        made={sp.made}
        bottomPad={0}
        spent={spent}
        refill={usage.usage_refill}
        playOff={audioOff}
        onFeature={feature}
        onOpenMade={(m) => {
          if (m.kind === 'report') { sp.openReport(m.id); return sp.setWebView('report'); }
          if (m.kind === 'lab') { sp.openLab(m.id); return sp.setWebView('labResult'); }
          if (m.kind !== 'audio') return toast(NOT_YET);
          sp.select(m.id);
          sp.setMini(false);
          sp.setWebView('player');
        }}
        onQuickPlay={(m) => {
          if (blockPlay()) return;
          if (sp.cur === m.id && sp.mini) sp.toggle();
          else sp.play(m.id);
          sp.setMini(true);
        }}
        onBuyCredit={() => setPop('charge')}
        onChangePlan={openPlans}
      />
    );
  };

  return (
    <View style={{ flex: 1, paddingTop: insets.top, backgroundColor: webColor.surface }}>
      <StudioColumnFrame mobile open onToggle={() => undefined} {...head} usagePct={usage.usage_pct} onUsage={() => setPop('usage')} onFeature={feature}>
        <View style={{ flex: 1, minHeight: 0, paddingBottom: mini ? 84 : 0 }}>{view()}</View>
      </StudioColumnFrame>
      <WebAudioPopup
        open={pop === 'audio'}
        stocks={audioPick.stocks}
        periods={audioPick.periods}
        lastClose={audioPick.lastClose}
        onClose={() => setPop(null)}
        onMake={({ codes, period, market }) => {
          setPop(null);
          sp.setWebView('gen');
          sp.startAudio({ sub: `${codes.length}종목 · ${period} · ${market ? '증시 요약 포함' : '증시 요약 없음'}`, n: codes.length, codes, market },
            __DEV__ && studio_fail === '1', env.useMock ? undefined : () => createAudio(codes, period, market));
        }}
      />
      <WebReportPopup
        open={pop === 'report'}
        stocks={reportPick.stocks}
        counts={reportPick.counts}
        sub={env.useMock ? mockReport.web_period : '지난주(월~금) 보고서에 넣을 종목'}
        onClose={() => setPop(null)}
        onMake={({ codes, market }) => {
          setPop(null);
          sp.setWebView('gen');
          sp.startReport({ sub: `${codes.length}종목${market ? ' · 국내 증시 흐름 포함' : ''}${env.useMock ? ` · ${mockReport.gen_range}` : ' · 지난주'}`, codes, market },
            __DEV__ && studio_fail === '1', env.useMock ? undefined : () => createReport(codes, market));
        }}
      />
      <WebUsageSheet open={pop === 'usage'} pct={usage.usage_pct} refill={usage.usage_refill} onClose={() => setPop(null)} onBuyCredit={() => setPop('charge')} onChangePlan={openPlans} />
      <WebCreditPopup
        open={pop === 'credit'}
        plan={plan ?? 'free'}
        nextName={nextPlan?.name}
        nextCredits={nextPlan?.monthly_credits}
        packLabel={planView.packs[0] ? `${planView.packs[0].credits}개 ${planView.packs[0].price}` : undefined}
        onClose={() => setPop(null)}
        onPlan={() => { setPop(null); openPlans(); }}
        onCharge={() => setPop('charge')}
      />
      <WebChargePopup open={pop === 'charge'} packs={planView.packs} default_credits={planView.default_credits} methods={mockPayMethods} onClose={() => setPop(null)} onPay={() => toast('결제는 아직 연결되지 않았어요')} />
    </View>
  );
}
