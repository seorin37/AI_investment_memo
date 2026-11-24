import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { mockPlanCompare, mockPlanDefault, mockPlanNotes, mockPlans } from '@/ui/screens/my/My.mock';
import { AppPlans } from '@/ui/screens/my/app/Plans';
import { planKey, withCurrentPlan } from '@/ui/screens/my/planLabel';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';

/** 앱 MY › 사용량 › 플랜 살펴보기 (원본 my.html plansHTML). 가격·한도는 가안, 결제는 연결 안 됨. 현재 플랜 = 로그인 사용자 plan */
export default function MyPlansScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const { plan } = useMyProfile();
  if (Platform.OS === 'web') return <Redirect href="/" />;
  const current = planKey(plan);
  return (
    <AppPlans
      plans={withCurrentPlan(mockPlans, current)}
      compare={mockPlanCompare}
      notes={mockPlanNotes}
      default_key={mockPlanDefault}
      current_key={current}
      onBack={() => router.back()}
      onStart={() => toast('결제는 아직 연결되지 않았어요')}
    />
  );
}
