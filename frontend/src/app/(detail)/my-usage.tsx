import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { mockMyUsage, mockTracked } from '@/ui/screens/my/My.mock';
import { AppUsage } from '@/ui/screens/my/app/Usage';
import { planName } from '@/ui/screens/my/planLabel';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';

/** 앱 MY › 사용량 (원본 my.html usageHTML). 플랜 이름 = 로그인 사용자 plan, 사용량 % · 갱신일 · 추적 현황은 아직 My.mock 예시 값 */
export default function MyUsageScreen() {
  const router = useRouter();
  const { plan } = useMyProfile();
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppUsage
      {...mockMyUsage}
      plan_name={planName(plan)}
      tracked={mockTracked}
      onBack={() => router.back()}
      onOpenMemo={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
      onPlans={() => router.push('/my-plans')}
    />
  );
}
