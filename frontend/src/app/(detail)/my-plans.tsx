import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { AppPlans } from '@/ui/screens/my/app/Plans';
import { planKey, withCurrentPlan } from '@/ui/screens/my/planLabel';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';
import { usePlanView } from '@/ui/screens/my/usePlanView';

/** 앱 MY › 사용량 › 플랜 살펴보기 (원본 my.html plansHTML). 가격·한도는 GET /plans (configs/credits.yaml, 2026-11-25), 결제는 연결 안 됨. 현재 플랜 = 로그인 사용자 plan */
export default function MyPlansScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const { plan } = useMyProfile();
  const pv = usePlanView();
  if (Platform.OS === 'web') return <Redirect href="/" />;
  const current = planKey(plan);
  return (
    <AppPlans
      plans={withCurrentPlan(pv.plans, current)}
      compare={pv.compare}
      notes={pv.notes}
      default_key={pv.default_key}
      current_key={current}
      onBack={() => router.back()}
      onStart={() => toast('결제는 아직 연결되지 않았어요')}
    />
  );
}
