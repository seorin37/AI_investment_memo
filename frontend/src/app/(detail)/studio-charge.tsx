import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { usePlanView } from '@/ui/screens/my/usePlanView';
import { AppCharge } from '@/ui/screens/studio/app/Charge';

/** 앱 크레딧 충전 (원본 studio.html pgCg). 결제는 연결 안 됨 → 안내만. 웹은 스튜디오 열의 충전 창 */
export default function StudioChargeScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const pv = usePlanView();
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return <AppCharge packs={pv.packs} default_credits={pv.default_credits} onBack={() => router.back()} onPay={() => toast('결제는 아직 연결되지 않았어요')} />;
}
