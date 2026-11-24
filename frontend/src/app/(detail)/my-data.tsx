import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { mockWithdrawCounts } from '@/ui/screens/my/My.mock';
import { AppData } from '@/ui/screens/my/app/Data';

/** 앱 MY › 데이터 (원본 my.html openData). 전체 삭제는 확인까지만 — 아무것도 지우지 않음 */
export default function MyDataScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return <AppData counts={mockWithdrawCounts} onBack={() => router.back()} onWipe={() => toast('아직 연결되지 않았어요 · 데이터는 그대로예요')} />;
}
