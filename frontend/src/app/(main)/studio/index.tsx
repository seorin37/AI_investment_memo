import React, { useState } from 'react';
import { Platform, View } from 'react-native';
import { Redirect, useLocalSearchParams, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { useUI } from '@/store/ui';
import { TopBar } from '@/ui/layout/app/TopBar';
import { useUsageView } from '@/ui/screens/my/useUsageView';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';
import { mockAudioPeriods, mockAudioStocks, mockReport, mockStudioCounts, mockStudioFeatures } from '@/ui/screens/studio/Studio.mock';
import { useCreateReport, useReportPickStocks } from '@/ui/screens/studio/reportView';
import { env } from '@/config/env';
import { AppAudioSheet } from '@/ui/screens/studio/app/AudioSheet';
import { AppReportSheet } from '@/ui/screens/studio/app/ReportSheet';
import { AppStudioHome } from '@/ui/screens/studio/app/StudioHome';
import { useStudioHead } from '@/ui/screens/studio/useStudioHead';

/**
 * 앱 스튜디오 탭 = UI v2 (원본 app/studio.html · ⑧).
 * 사용량·갱신일은 useUsageView, 종목 수·AI 연결 메모 수는 useStudioHead (실제 API · mock 모드는 예시). 오디오(8b): 시트 → 만드는 중 → 플레이어 · 미니 플레이어(탭 레이아웃).
 * 주간보고서(8c): 시트 → 만드는 중 → 보고서. 실험실·퀴즈는 8d 전까지 안내만 (옛 화면으로 보내지 않음).
 * mock: 개발 빌드(__DEV__)에서만 ?fail=1 이면 다음 만들기가 실패로 끝남 (실패 화면 확인용 · 배포 빌드는 무시). ?make=audio 면 시트를 열고 시작.
 * 웹은 오른쪽 스튜디오 열을 쓰므로 홈으로.
 */
const NOT_YET = '아직 연결되지 않았어요 · 데이터는 그대로예요';

export default function StudioTab() {
  const router = useRouter();
  const { profile: { name: myName, photoUrl } } = useMyProfile();
  /* AI 사용량: 실제 모드면 GET /me/usage, mock 모드면 My.mock (설정 · MY 와 같은 값) */
  const usage = useUsageView();
  /* 내 종목 수 · AI 연결 메모 수: 실제 API (GET /stocks · /ai/stats). mock 모드는 예시 */
  const head = useStudioHead();
  const toast = useUI((s) => s.showToast);
  const { fail, make } = useLocalSearchParams<{ fail?: string; make?: string }>();
  const p = useStudioPlayer();
  /* 주간보고서: 실제 모드면 내 종목 · POST /studio/reports (2026-11-23) */
  const reportPick = useReportPickStocks();
  const createReport = useCreateReport();
  const [sheet, setSheet] = useState(false);
  const [rsheet, setRSheet] = useState(false);
  const [mk, setMk] = useState(make);
  if (make !== mk) {
    setMk(make);
    if (make === 'audio') setSheet(true);
  }
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <View style={{ flex: 1 }}>
      <AppStudioHome
        header={
          <TopBar
            preset="studio"
            title="스튜디오"
            actions={[{ icon: 'bell', label: '알림', onPress: () => router.push('/my-inbox') }]}
            avatar={{ name: myName, photoUrl, onPress: () => router.push('/my') }}
          />
        }
        features={mockStudioFeatures}
        made={p.made}
        job={p.job}
        bottomPad={p.mini ? 72 : 0}
        onJob={() => {
          if (p.job?.status === 'fail') p.retry();
          router.push('/studio-gen');
        }}
        usage_pct={usage.usage_pct}
        usage_refill={usage.usage_refill}
        stock_count={head.stock_count}
        ai_memo_count={head.ai_memo_count}
        onFeature={(k) => (k === 'audio' ? setSheet(true) : k === 'report' ? setRSheet(true) : router.push(k === 'quiz' ? '/studio-quiz' : '/studio-lab'))}
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
        stocks={mockAudioStocks}
        periods={mockAudioPeriods}
        onClose={() => setSheet(false)}
        onMake={({ codes, period, market }) => {
          setSheet(false);
          p.startAudio({ sub: `${codes.length}종목 · ${period} · ${market ? '증시 요약 포함' : '증시 요약 없음'}`, n: codes.length }, __DEV__ && fail === '1');
          setTimeout(() => router.push('/studio-gen'), 220);
        }}
      />
      <AppReportSheet
        open={rsheet}
        stocks={reportPick.stocks}
        counts={reportPick.counts}
        period={env.useMock ? mockReport.period : '지난주 월~금'}
        onClose={() => setRSheet(false)}
        onMake={({ codes, market }) => {
          setRSheet(false);
          p.startReport({ sub: `${codes.length}종목${market ? ' · 국내 증시 흐름 포함' : ''}${env.useMock ? ` · ${mockReport.gen_range}` : ' · 지난주'}`, codes, market },
            __DEV__ && fail === '1', env.useMock ? undefined : () => createReport(codes, market));
          setTimeout(() => router.push('/studio-gen'), 220);
        }}
      />
    </View>
  );
}
