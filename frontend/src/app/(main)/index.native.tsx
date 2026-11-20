import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useCoach } from '@/store/coach';
import { Linking } from 'react-native';
import { useFocusEffect, useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { useUI } from '@/store/ui';
import type { Checklist } from '@/types/models';
import { TopBar } from '@/ui/layout/app/TopBar';
import { AppHome } from '@/ui/screens/home/app/Home';
import { mockHomeData, mockHomeSearch } from '@/ui/screens/home/Home.mock';
import type { HomeWidget } from '@/ui/screens/home/Home.types';
import { mockExtract } from '@/ui/screens/memo/MemoDetail.mock';
import type { FirstMemoSummary } from '@/ui/screens/onboarding/FirstHome.types';
import { mockFirstHomeStocks } from '@/ui/screens/onboarding/Onboarding.mock';
import { AppFirstHome } from '@/ui/screens/onboarding/app/FirstHome';

/** 앱 홈 탭. 온보딩 query는 현재 흐름에서만 유지되는 host 임시 상태다. */
export default function HomeTab() {
  const router = useRouter();
  const notice = useMockNotice();
  const setTabBarHidden = useUI((s) => s.setTabBarHidden);
  const { fail, onboarding, selected, first_code, first_title, first_body, first_ai } = useLocalSearchParams<{ fail?: string; onboarding?: string; selected?: string; first_code?: string; first_title?: string; first_body?: string; first_ai?: string }>();
  const toast = useUI((s) => s.showToast);
  const [widgets, setWidgets] = useState<HomeWidget[]>(mockHomeData.widgets);
  const [checklists, setChecklists] = useState<Record<string, Checklist>>(mockHomeData.checklists);
  const [retried, setRetried] = useState(false);
  const [firstActive, setFirstActive] = useState(!!onboarding);
  const [pickerOpen, setPickerOpen] = useState(false);
  /* 저장한 첫 메모 (memo/new · memo/link 가 홈으로 돌아오며 넘김 — 이번 흐름의 임시 값) */
  const firstMemo = useMemo<FirstMemoSummary | null>(() => {
    if (onboarding !== 'first_saved' || !first_code || !first_title) return null;
    const ai = first_ai === '1';
    const name = mockFirstHomeStocks(`${first_code}:watching`)[0]?.name ?? '';
    const chips = ai ? mockExtract(first_title, first_body ?? '').map((x) => (x.kind === 'price' ? `가격 조건 · 종가 ${(x.price ?? 0) / 10000}만 원 ${x.direction}` : `공시·뉴스 · ${x.label}`)) : [];
    return { stock_code: first_code, stock_name: name, title: first_title, body: first_body ?? '', ai, chips };
  }, [onboarding, first_code, first_title, first_body, first_ai]);
  const firstStocks = useMemo(() => mockFirstHomeStocks(selected, firstMemo), [selected, firstMemo]);
  const marketOk = fail !== '1' || retried;
  useFocusEffect(useCallback(() => () => setTabBarHidden(false), [setTabBarHidden]));
  /* 가입 직후 첫 홈에서 0.7초 뒤 사용법 안내 (원본 start.html MX.coach(-1)) — 처음 한 번만 */
  const startCoach = useCoach((s) => s.startFirst);
  useEffect(() => {
    /* 종목 고르기 시트가 떠 있는 동안은 기다림 (시트가 안내보다 위에 그려져서) */
    if (!onboarding || pickerOpen) return;
    const t = setTimeout(startCoach, 700);
    return () => clearTimeout(t);
  }, [onboarding, pickerOpen, startCoach]);
  const patchCl = (code: string, f: (c: Checklist) => Checklist) => setChecklists((all) => (all[code] ? { ...all, [code]: f(all[code]) } : all));
  const openNew = (code: string) => {
    setPickerOpen(false);
    router.navigate({ pathname: '/memo/new', params: { code, from_onboarding: '1', onboarding_selected: selected ?? '' } } as Href);
  };
  const firstStart = firstActive ? (
    <AppFirstHome
      user_name={mockHomeData.user_name}
      stocks={firstStocks}
      memo={firstMemo}
      picker_open={pickerOpen}
      onOpenPicker={() => setPickerOpen(true)}
      onClosePicker={() => setPickerOpen(false)}
      onPickStock={(stock) => openNew(stock.stock_code)}
      onNoStocks={() => toast('먼저 내 종목에서 종목을 추가해 주세요')}
      onContinue={() => { setPickerOpen(false); setFirstActive(false); }}
    />
  ) : undefined;
  return (
    <AppHome
      {...mockHomeData}
      firstStart={firstStart}
      widgets={widgets}
      checklists={checklists}
      market={marketOk ? mockHomeData.market : null}
      search={mockHomeSearch}
      header={({ line, onSearch }) => (
        <TopBar
          preset="home"
          showLine={line}
          actions={[
            { icon: 'search', label: '검색', onPress: onSearch },
            { icon: 'bell', label: '알림', onPress: () => router.push('/my-inbox') },
          ]}
          avatar={{ name: mockHomeData.user_name, onPress: () => router.push('/my') }}
        />
      )}
      onEditingChange={setTabBarHidden}
      onChangeWidgets={setWidgets}
      onOpenUpdates={() => router.navigate('/updates')}
      onOpenStockUpdates={(code) => router.navigate({ pathname: '/updates/[code]', params: { code } })}
      onOpenStock={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code } })}
      onOpenMarket={(key) => router.push({ pathname: '/market/[key]', params: { key } })}
      onOpenNews={(n) => Linking.openURL(n.url)}
      onRetryMarket={() => setRetried(true)}
      onToggleCheck={(code, id) => patchCl(code, (c) => ({ ...c, items: c.items.map((i) => (i.id === id ? { ...i, done: !i.done } : i)) }))}
      onAddCheck={(code, text) => patchCl(code, (c) => ({ ...c, items: [...c.items, { id: `n${Date.now()}`, text, done: false }] }))}
      onNudge={() => notice('주간보고서')}
    />
  );
}
