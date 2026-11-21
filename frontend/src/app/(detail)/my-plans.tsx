import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { mockPlanCompare, mockPlanDefault, mockPlanNotes, mockPlans } from '@/ui/screens/my/My.mock';
import { AppPlans } from '@/ui/screens/my/app/Plans';

/** 앱 MY › 사용량 › 플랜 살펴보기 (원본 my.html plansHTML). 가격·한도는 가안, 결제는 연결 안 됨 */
export default function MyPlansScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppPlans
      plans={mockPlans}
      compare={mockPlanCompare}
      notes={mockPlanNotes}
      default_key={mockPlanDefault}
      onBack={() => router.back()}
      onStart={() => toast('결제는 아직 연결되지 않았어요')}
    />
  );
}
