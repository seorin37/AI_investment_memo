import React, { useState } from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { StockPick } from '@/features/onboarding/StockPick';
import { mockStockPickProps } from '@/features/onboarding/StockPick.mock';

/**
 * 앱: 가입 후 첫 종목 고르기. mock 단계에서는 주소(/onboarding/pick)로만 들어옴 —
 * 다음 단계에서 로그인 후 내 종목이 0개면 여기로 보내고, 고른 종목은 useAddStock 으로 저장.
 */
export default function PickScreen() {
  const router = useRouter();
  const notice = useMockNotice();
  const [selected, setSelected] = useState<string[]>(mockStockPickProps.selected);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <StockPick
      {...mockStockPickProps}
      selected={selected}
      onToggle={(code) => setSelected((s) => (s.includes(code) ? s.filter((c) => c !== code) : [...s, code]))}
      onOpenHolding={() => notice('보유·관심 정하기')}
      onNext={() => router.replace('/')}
      onSkip={() => router.replace('/')}
    />
  );
}
