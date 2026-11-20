import React, { useState } from 'react';
import { Platform } from 'react-native';
import { useRouter, type Href } from 'expo-router';
import { mockOnboardingStocks } from '@/ui/screens/onboarding/Onboarding.mock';
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
  const finish = (mode = homeMode) => {
    const encoded = Object.entries(selected).map(([code, status]) => `${code}:${status}`).join(',');
    router.replace({ pathname: '/', params: { onboarding: 'welcome', home_mode: mode, selected: encoded } } as Href);
  };
  const props = {
    stocks: mockOnboardingStocks,
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
      if (step === 'pick') router.back();
      else setStep('pick');
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
  return Platform.OS === 'web' ? <WebOnboardingFlow {...props} /> : <AppOnboardingFlow {...props} />;
}
