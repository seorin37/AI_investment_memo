import React, { useCallback } from 'react';
import { Platform } from 'react-native';
import { Redirect, useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useGenJobs } from '@/store/genJobs';
import { AppGen } from '@/ui/screens/studio/app/Gen';

/** 앱 만드는 중 (원본 studio.html pgGen · 오디오 · 주간보고서 · 투자 실험실). 다 되면 store/genJobs 가 결과 화면으로 바꿔 열기 */
export default function StudioGenScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const job = useGenJobs((s) => s.jobs.find((j) => j.id === id));
  const setViewing = useGenJobs((s) => s.setViewing);
  const retry = useGenJobs((s) => s.retry);
  useFocusEffect(
    useCallback(() => {
      /* 이미 끝났거나 새로고침으로 없어진 작업 */
      if (!useGenJobs.getState().jobs.some((j) => j.id === id)) {
        router.dismissTo('/studio');
        return;
      }
      setViewing(id);
      return () => setViewing(null);
    }, [id, router, setViewing]),
  );
  if (Platform.OS === 'web') return <Redirect href="/" />;
  if (!job) return null;
  return <AppGen job={job} onBack={() => router.back()} onAway={() => router.dismissTo('/studio')} onRetry={() => retry(job.id)} />;
}
