import React, { useCallback, useState } from 'react';
import { Platform, View } from 'react-native';
import { Redirect, useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useGenJobs } from '@/store/genJobs';
import { useAiStats, useMyStocks } from '@/hooks/queries';
import { useStudioPlayer } from '@/store/studioPlayer';
import { useUI } from '@/store/ui';
import { TopBar } from '@/ui/layout/app/TopBar';
import { useUsageView } from '@/ui/screens/my/useUsageView';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';
import { mockReport, mockStudioCounts, mockStudioFeatures } from '@/ui/screens/studio/Studio.mock';
import { blockPlay } from '@/ui/screens/studio/appAudio';
import { useAudioPick } from '@/ui/screens/studio/audioView';
import { startAudio, startReport } from '@/ui/screens/studio/genRuns';
import { useReportPickStocks } from '@/ui/screens/studio/reportView';
import { env } from '@/config/env';
import { AppAudioSheet } from '@/ui/screens/studio/app/AudioSheet';
import { AppReportSheet } from '@/ui/screens/studio/app/ReportSheet';
import { AppStudioHome } from '@/ui/screens/studio/app/StudioHome';
import { AppCreditDialog } from '@/ui/screens/studio/app/CreditDialog';
import { usePlanView } from '@/ui/screens/my/usePlanView';
import type { StudioKind } from '@/ui/screens/studio/Studio.types';

/**
 * 앱 스튜디오 탭 = UI v2 (원본 app/studio.html · ⑧).
 * 사용량·갱신일은 My.mock. 오디오(8b): 시트 → 만드는 중 → 플레이어 · 미니 플레이어(탭 레이아웃).
 * 주간보고서(8c): 시트 → 만드는 중 → 보고서. 실험실·퀴즈는 8d 전까지 안내만 (옛 화면으로 보내지 않음).
 * mock: 개발 빌드(__DEV__)에서만 ?fail=1 이면 다음 만들기가 실패로 끝남 (실패 화면 확인용 · 배포 빌드는 무시). ?make=audio 면 시트를 열고 시작.
 * 웹은 오른쪽 스튜디오 열을 쓰므로 홈으로.
 */
const NOT_YET = '아직 연결되지 않았어요 · 데이터는 그대로예요';

export default function StudioTab() {
  const router = useRouter();
  const { profile: { name: myName, photoUrl } } = useMyProfile();
  /* AI 사용량: 실제 모드면 GET /me/usage, mock 모드면 My.mock */
  const usage = useUsageView();
  const toast = useUI((s) => s.showToast);
  /* 내 종목 · AI 연결 메모 수: 실제 모드는 웹 스튜디오 머리와 같은 GET /stocks · /ai/stats */
  const myStocks = useMyStocks();
  const aiStats = useAiStats();
  const counts = env.useMock ? mockStudioCounts : { stock_count: myStocks.data?.length ?? 0, ai_memo_count: aiStats.data?.linked_memos ?? 0 };
  const { fail, make } = useLocalSearchParams<{ fail?: string; make?: string }>();
  const p = useStudioPlayer();
  /* 주간보고서: 실제 모드면 내 종목 · POST /studio/reports (2026-11-23) */
  const reportPick = useReportPickStocks();
  const jobs = useGenJobs((s) => s.jobs);
  const retry = useGenJobs((s) => s.retry);
  const setStudioOpen = useGenJobs((s) => s.setStudioOpen);
  useFocusEffect(
    useCallback(() => {
      setStudioOpen(true);
      return () => setStudioOpen(false);
    }, [setStudioOpen]),
  );
  const [sheet, setSheet] = useState(false);
  const [rsheet, setRSheet] = useState(false);
  /* AI 오디오: 실제 모드면 GET /studio/audio/options (시트를 열었을 때만) · POST /studio/audio (genRuns, 2026-11-24) */
  const audioPick = useAudioPick(sheet);
  /* 사용량을 다 쓴 뒤 오디오 · 보고서 · 실험 만들기를 누르면 '크레딧을 다 썼어요' 창 먼저 (웹 studioFeat 와 같음) */
  const usageSpent = usage.paused || usage.usage_pct >= 100;
  const [credit, setCredit] = useState(false);
  const { plan: myPlan } = useMyProfile();
  const planView = usePlanView();
  const nextPlan = planView.catalog.plans.find((x) => x.code === (myPlan === 'plus' ? 'pro' : 'plus'));
  const feature = (k: StudioKind) => {
    if (k !== 'quiz' && usageSpent) return setCredit(true);
    if (k === 'audio') return setSheet(true);
    if (k === 'report') return setRSheet(true);
    router.push(k === 'quiz' ? '/studio-quiz' : '/studio-lab');
  };
  const [mk, setMk] = useState(make);
  if (make !== mk) {
    setMk(make);
    if (make === 'audio') {
      if (usageSpent) setCredit(true);
      else setSheet(true);
    }
  }
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <View style={{ flex: 1 }}>
      <AppStudioHome
        header={
          <TopBar
            preset="studio"
            title="스튜디오"
            subtitle="쌓인 소식을 듣고, 읽고, 실험해 보세요"
            actions={[{ icon: 'bell', label: '알림', onPress: () => router.push('/my-inbox') }]}
            avatar={{ name: myName, photoUrl, onPress: () => router.push('/my') }}
          />
        }
        features={mockStudioFeatures}
        made={p.made}
        jobs={jobs}
        playingId={p.playing ? p.cur : null}
        onQuickPlay={(m) => {
          if (blockPlay()) return;
          if (p.cur === m.id && p.mini) p.toggle();
          else p.play(m.id);
          p.setMini(true);
        }}
        onJob={(id) => {
          retry(id);
          router.push({ pathname: '/studio-gen', params: { id } });
        }}
        usage_pct={usage.usage_pct}
        spent={usage.paused}
        usage_refill={usage.usage_refill}
        {...counts}
        onFeature={feature}
        onOpenMade={(m) => {
          if (m.kind === 'lab') {
            p.openLab(m.id);
            return router.push('/studio-lab-result');
          }
          if (m.kind === 'report') {
            p.openReport(m.id);
            return router.push('/studio-report');
          }
          if (m.kind !== 'audio') return toast(NOT_YET);
          p.select(m.id);
          router.push('/studio-player');
        }}
        onBuyCredit={() => router.push('/studio-charge')}
        onChangePlan={() => router.push('/my-plans')}
      />
      <AppAudioSheet
        open={sheet}
        stocks={audioPick.stocks}
        periods={audioPick.periods}
        lastClose={audioPick.lastClose}
        onClose={() => setSheet(false)}
        onMake={({ codes, period, market }) => {
          setSheet(false);
          const id = startAudio({ sub: `${codes.length}종목 · ${period} · ${market ? '증시 요약 포함' : '증시 요약 없음'}`, codes, period, market, fail: __DEV__ && fail === '1' });
          setTimeout(() => router.push({ pathname: '/studio-gen', params: { id } }), 220);
        }}
      />
      <AppCreditDialog
        open={credit}
        plan={myPlan ?? 'free'}
        nextName={nextPlan?.name}
        nextCredits={nextPlan?.monthly_credits}
        packLabel={planView.packs[0] ? `${planView.packs[0].credits}개 ${planView.packs[0].price}` : undefined}
        onClose={() => setCredit(false)}
        onPlan={() => { setCredit(false); router.push('/my-plans'); }}
        onCharge={() => { setCredit(false); router.push('/studio-charge'); }}
      />
      <AppReportSheet
        open={rsheet}
        stocks={reportPick.stocks}
        counts={reportPick.counts}
        period={env.useMock ? mockReport.period : '지난주 월~금'}
        onClose={() => setRSheet(false)}
        onMake={({ codes, market }) => {
          setRSheet(false);
          const id = startReport({ sub: `${codes.length}종목${market ? ' · 국내 증시 흐름 포함' : ''}${env.useMock ? ` · ${mockReport.gen_range}` : ' · 지난주'}`, codes, market, fail: __DEV__ && fail === '1' });
          setTimeout(() => router.push({ pathname: '/studio-gen', params: { id } }), 220);
        }}
      />
    </View>
  );
}
