import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { mockWithdrawCounts } from '@/ui/screens/my/My.mock';
import { AppWithdraw } from '@/ui/screens/my/app/Withdraw';

/**
 * 앱 회원 탈퇴 = UI v2 (원본 app/my.html openLeave).
 * 되돌릴 수 없는 동작이라 확인 시트까지만 — mock 에서도 데이터·세션을 지우지 않는다 (탈퇴 API 없음).
 */
export default function MyWithdrawScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppWithdraw
      counts={mockWithdrawCounts}
      onBack={() => router.back()}
      onConfirm={() => toast('아직 탈퇴 기능은 연결되지 않았어요 · 데이터는 그대로예요')}
    />
  );
}
