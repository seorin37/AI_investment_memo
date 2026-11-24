import React, { useCallback, useEffect, useRef } from 'react';
import { Platform } from 'react-native';
import { Redirect, useFocusEffect, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { mockAudioGen, mockReport } from '@/ui/screens/studio/Studio.mock';
import { AppGen } from '@/ui/screens/studio/app/Gen';

/** 앱 만드는 중 (원본 studio.html pgGen · 오디오 · 주간보고서). 크레딧 차감 없음 · 다 되면 결과 화면으로 바꿔 열기 */
export default function StudioGenScreen() {
  const router = useRouter();
  const job = useStudioPlayer((s) => s.job);
  const openSig = useStudioPlayer((s) => s.openPlayer);
  const setVisible = useStudioPlayer((s) => s.setGenVisible);
  const retry = useStudioPlayer((s) => s.retry);
  const first = useRef(openSig);
  useFocusEffect(useCallback(() => { setVisible(true); return () => setVisible(false); }, [setVisible]));
  useEffect(() => {
    if (openSig === first.current) return;
    router.replace(useStudioPlayer.getState().openKind === 'report' ? '/studio-report' : '/studio-player');
  }, [openSig, router]);
  /* 보고서가 기다리는 시간을 넘기면 job 이 비워진다 (안내 토스트) → 스튜디오로 돌아감 (2026-11-24) */
  const hadJob = useRef(!!job);
  useEffect(() => {
    if (job) hadJob.current = true;
    else if (hadJob.current && Platform.OS !== 'web') router.back();
  }, [job, router]);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  if (!job) return null;
  return <AppGen job={job} steps={job.kind === 'report' ? mockReport.steps : mockAudioGen.steps} onBack={() => router.back()} onAway={() => router.back()} onRetry={retry} />;
}
