import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useTrackedView } from '@/ui/screens/my/useTrackedView';
import { AppUsage } from '@/ui/screens/my/app/Usage';
import { useUsageView } from '@/ui/screens/my/useUsageView';

/** 앱 MY › 사용량 (원본 my.html usageHTML). 사용량 % · 갱신일 = GET /me/usage (mock 모드는 My.mock), 플랜 이름 = 로그인 사용자 plan. 추적 현황 = GET /ai/tracking (2026-11-23) */
export default function MyUsageScreen() {
  const router = useRouter();
  const usage = useUsageView();
  const tracked = useTrackedView(Platform.OS !== 'web');
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppUsage
      usage_pct={usage.usage_pct}
      usage_renew={usage.usage_renew}
      plan_name={usage.plan_name}
      credits_left={usage.credits_left}
      tracked={tracked}
      onBack={() => router.back()}
      onOpenMemo={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
      onPlans={() => router.push('/my-plans')}
    />
  );
}
