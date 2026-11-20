import React, { useState } from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter, type Href } from 'expo-router';
import { useAuth } from '@/store/auth';
import { mockAppPopularStocks, mockOnboardingStocks } from '@/ui/screens/onboarding/Onboarding.mock';
import type { HomeMode, OnboardingSelection, OnboardingStep, StockStatus } from '@/ui/screens/onboarding/Onboarding.types';
import { AppOnboardingFlow } from '@/ui/screens/onboarding/app/OnboardingFlow';
import { WebOnboardingFlow } from '@/ui/screens/onboarding/web/OnboardingFlow';

/**
 * 신규 사용자 온보딩 host.
 * 종목/보유·관심/홈 구성은 이 화면의 임시 상태만 사용하며 API나 DB에는 저장하지 않는다.
 * 실제 신규 사용자 판별과 완료 이력 영속화는 서버 계약이 생긴 뒤 연결한다.
 */
export default function PickScreen() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<OnboardingSelection>({});
  const [step, setStep] = useState<OnboardingStep>('pick');
  const [holdingOpen, setHoldingOpen] = useState(false);
  const [homeMode, setHomeMode] = useState<HomeMode>('template');
  /* 로그아웃 뒤 뒤로가기로 들어오지 못하게 (가입 흐름도 로그인한 사람만) */
  const status = useAuth((s) => s.status);
  const finish = (mode = homeMode) => {
    const encoded = Object.entries(selected).map(([code, status]) => `${code}:${status}`).join(',');
    router.replace({ pathname: '/', params: { onboarding: 'welcome', home_mode: mode, selected: encoded } } as Href);
  };
  const props = {
    /* 앱 = 원본 app/login.html '많이 찾는 종목' 12개 · 웹 = 기존 목록 (웹 원본 기준) */
    stocks: Platform.OS === 'web' ? mockOnboardingStocks : mockAppPopularStocks,
    query,
    selected,
    step,
    holding_open: holdingOpen,
    onQueryChange: setQuery,
    onToggle: (code: string) => setSelected((all) => {
      if (all[code]) {
        const next = { ...all };
        delete next[code];
        return next;
      }
      return { ...all, [code]: 'watching' as StockStatus };
    }),
    onStatusChange: (code: string, status: StockStatus) => setSelected((all) => ({ ...all, [code]: status })),
    onRemove: (code: string) => setSelected((all) => {
      const next = { ...all };
      delete next[code];
      if (Object.keys(next).length === 0) setHoldingOpen(false);
      return next;
    }),
    onOpenHolding: () => setHoldingOpen(true),
    onCloseHolding: () => setHoldingOpen(false),
    onBack: () => {
      /* 약관 → 종목 고르기는 replace라 돌아갈 화면이 없을 수 있다 → 약관으로 */
      if (step !== 'pick') setStep('pick');
      else if (router.canGoBack()) router.back();
      else router.replace('/terms');
    },
    onSkip: () => setStep('setup'),
    onContinue: () => setStep('setup'),
    onChooseHome: (mode: HomeMode) => {
      setHomeMode(mode);
      if (Platform.OS === 'web') finish(mode);
      else setStep('ready');
    },
    onFinish: () => finish(),
  };
  if (status === 'signedOut') return <Redirect href={(Platform.OS === 'web' ? '/login' : '/intro') as Href} />;
  return Platform.OS === 'web' ? <WebOnboardingFlow {...props} /> : <AppOnboardingFlow {...props} />;
}
