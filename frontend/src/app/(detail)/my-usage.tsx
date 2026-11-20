import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { mockMyUsage, mockTracked } from '@/ui/screens/my/My.mock';
import { AppUsage } from '@/ui/screens/my/app/Usage';

/** 앱 MY › 사용량 (원본 my.html usageHTML). 사용량·추적 현황은 My.mock 예시 값 */
export default function MyUsageScreen() {
  const router = useRouter();
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppUsage
      {...mockMyUsage}
      tracked={mockTracked}
      onBack={() => router.back()}
      onOpenMemo={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
      onPlans={() => router.push('/my-plans')}
    />
  );
}
