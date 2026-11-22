import React, { useMemo, useState } from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter, type Href } from 'expo-router';
import { env } from '@/config/env';
import { useAddStock, usePopularStocks, useStockSearch } from '@/hooks/queries';
import { useAuth } from '@/store/auth';
import type { StockMaster } from '@/types/models';
import { fallbackLogo } from '@/ui/screens/company/useCompanyInfo';
import { mockAppPopularStocks, mockOnboardingStocks } from '@/ui/screens/onboarding/Onboarding.mock';
import type { HomeMode, OnboardingSelection, OnboardingStep, OnboardingStock, StockStatus } from '@/ui/screens/onboarding/Onboarding.types';
import { AppOnboardingFlow } from '@/ui/screens/onboarding/app/OnboardingFlow';
import { WebOnboardingFlow } from '@/ui/screens/onboarding/web/OnboardingFlow';
import { addSelectedStocks, withSelectedStocks } from '@/ui/screens/onboarding/pickSave';

const SAVE_ERROR = '일부 종목을 담지 못했어요. 다시 시도해 주세요.';

/** 종목 마스터 → 화면 카드 (로고는 기업정보와 같은 fallbackLogo, 업종은 카드에 그리지 않아 빈 값) */
function toOnboardingStock(s: StockMaster): OnboardingStock {
  return { stock_code: s.code, name: s.name, market: s.market === 'KOSDAQ' ? 'KOSDAQ' : 'KOSPI', category: '', ...fallbackLogo(s.code, s.name) };
}

/**
 * 신규 사용자 온보딩 host (2026-11-22 실제 연결).
 * - 목록: 실제 모드면 GET /stocks/popular (불러오는 중 · 실패면 지금 mock 목록 — 실제 종목코드라 담기는 됨).
 *   웹 검색은 GET /stocks/search (#61 useStockSearch). 앱은 검색 없음 그대로
 * - 고른 종목 담기: '계속'(웹 보유·관심 확인 [이대로 계속] · 앱 [N개 종목으로 계속])에서 POST /stocks 를 하나씩 → 사이드바는 기존 무효화로 갱신
 *   전부 성공 → 홈 구성으로 (지금처럼) · 일부 실패 → 머무르고 실패한 종목만 선택 상태로 남김 + 버튼 위 한 줄
 * - '건너뛰기'는 담지 않고 홈 구성으로 (그대로). mock 모드는 담지 않음 (그대로)
 */
export default function PickScreen() {
  const router = useRouter();
  const real = !env.useMock;
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<OnboardingSelection>({});
  const [step, setStep] = useState<OnboardingStep>('pick');
  const [holdingOpen, setHoldingOpen] = useState(false);
  const [homeMode, setHomeMode] = useState<HomeMode>('template');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /* 로그아웃 뒤 뒤로가기로 들어오지 못하게 (가입 흐름도 로그인한 사람만) */
  const status = useAuth((s) => s.status);

  const mockList = Platform.OS === 'web' ? mockOnboardingStocks : mockAppPopularStocks;
  const popular = usePopularStocks(12, real);
  const search = useStockSearch(real && Platform.OS === 'web' ? query : '');
  const addStock = useAddStock();

  const base = useMemo<OnboardingStock[]>(() => {
    if (!real) return mockList;
    if (Platform.OS === 'web' && query.trim()) return (search.data ?? []).map(toOnboardingStock);
    return popular.data?.length ? popular.data.map(toOnboardingStock) : mockList;
  }, [real, mockList, query, search.data, popular.data]);
  /* 고를 때 그 카드를 기억 (검색어를 바꿔도 고른 종목이 보유·관심 확인 · 'N개 선택'에서 빠지지 않게) */
  const [pickedCards, setPickedCards] = useState<Record<string, OnboardingStock>>({});
  const stocks = useMemo(() => withSelectedStocks(base, pickedCards, selected), [base, pickedCards, selected]);

  /* 이미 담은 종목 (일부 실패 뒤 다시 시도하면 selected 엔 실패분만 남으므로, 홈에 넘길 때 합침) */
  const [added, setAdded] = useState<OnboardingSelection>({});

  const finish = (mode = homeMode) => {
    const encoded = Object.entries({ ...added, ...selected }).map(([code, status]) => `${code}:${status}`).join(',');
    router.replace({ pathname: '/', params: { onboarding: 'welcome', home_mode: mode, selected: encoded } } as Href);
  };

  /* 고른 종목 담기 → 다음 단계. 실패한 것만 남기고 머무름 */
  const saveAndContinue = () => {
    if (!real) return setStep('setup');
    if (saving) return;
    setSaving(true);
    setError(null);
    const asked = selected;
    /* 화면 순서대로 담음 → 서버가 맨 뒤에 붙이므로 사이드바 순서도 화면 순서 */
    const order = stocks.map((s) => s.stock_code);
    void addSelectedStocks(asked, (code, s) => addStock.mutateAsync({ code, status: s }), order).then(({ failed, added: ok }) => {
      setSaving(false);
      setAdded((all) => ({ ...all, ...Object.fromEntries(ok.map((code) => [code, asked[code]])) }));
      if (Object.keys(failed).length === 0) {
        setStep('setup');
        return;
      }
      setSelected(failed);
      setError(SAVE_ERROR);
    });
  };

  const props = {
    /* 앱 = 원본 app/login.html '많이 찾는 종목' · 웹 = 기존 목록 (실제 모드면 둘 다 GET /stocks/popular) */
    stocks,
    query,
    selected,
    step,
    holding_open: holdingOpen,
    saving,
    error,
    onQueryChange: setQuery,
    onToggle: (code: string) => {
      const card = stocks.find((s) => s.stock_code === code);
      if (card) setPickedCards((all) => (all[code] ? all : { ...all, [code]: card }));
      setSelected((all) => {
        if (all[code]) {
          const next = { ...all };
          delete next[code];
          return next;
        }
        return { ...all, [code]: 'watching' as StockStatus };
      });
    },
    onStatusChange: (code: string, status: StockStatus) => setSelected((all) => ({ ...all, [code]: status })),
    onRemove: (code: string) => setSelected((all) => {
      const next = { ...all };
      delete next[code];
      if (Object.keys(next).length === 0) setHoldingOpen(false);
      return next;
    }),
    /* 담는 중에는 보유·관심 확인 · 뒤로 · 건너뛰기를 받지 않음 (중간에 흐름이 바뀌지 않게) */
    onOpenHolding: () => {
      if (!saving) setHoldingOpen(true);
    },
    onCloseHolding: () => setHoldingOpen(false),
    onBack: () => {
      if (saving) return;
      /* 약관 → 종목 고르기는 replace라 돌아갈 화면이 없을 수 있다 → 약관으로 */
      if (step !== 'pick') setStep('pick');
      else if (router.canGoBack()) router.back();
      else router.replace('/terms');
    },
    onSkip: () => {
      if (!saving) setStep('setup');
    },
    onContinue: saveAndContinue,
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
