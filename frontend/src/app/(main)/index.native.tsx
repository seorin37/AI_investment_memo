import React, { useCallback, useMemo, useState } from 'react';
import { Linking } from 'react-native';
import { useFocusEffect, useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { useUI } from '@/store/ui';
import type { Checklist } from '@/types/models';
import { TopBar } from '@/ui/layout/app/TopBar';
import { AppHome } from '@/ui/screens/home/app/Home';
import { mockHomeData, mockHomeSearch } from '@/ui/screens/home/Home.mock';
import type { HomeWidget } from '@/ui/screens/home/Home.types';
import { mockOnboardingStocks } from '@/ui/screens/onboarding/Onboarding.mock';
import { AppFirstHome } from '@/ui/screens/onboarding/app/FirstHome';

/** 앱 홈 탭. 온보딩 query는 현재 흐름에서만 유지되는 host 임시 상태다. */
export default function HomeTab() {
  const router = useRouter();
  const notice = useMockNotice();
  const setTabBarHidden = useUI((s) => s.setTabBarHidden);
  const { fail, onboarding, selected } = useLocalSearchParams<{ fail?: string; onboarding?: string; selected?: string }>();
  const [widgets, setWidgets] = useState<HomeWidget[]>(mockHomeData.widgets);
  const [checklists, setChecklists] = useState<Record<string, Checklist>>(mockHomeData.checklists);
  const [retried, setRetried] = useState(false);
  const [firstActive, setFirstActive] = useState(!!onboarding);
  const [pickerOpen, setPickerOpen] = useState(false);
  const selectedCodes = useMemo(() => (selected ?? '').split(',').map((v) => v.split(':')[0]).filter(Boolean), [selected]);
  const firstStocks = useMemo(() => {
    const found = mockOnboardingStocks.filter((s) => selectedCodes.includes(s.stock_code));
    return found.length ? found : mockOnboardingStocks.slice(0, 3);
  }, [selectedCodes]);
  const marketOk = fail !== '1' || retried;
  useFocusEffect(useCallback(() => () => setTabBarHidden(false), [setTabBarHidden]));
  const patchCl = (code: string, f: (c: Checklist) => Checklist) => setChecklists((all) => (all[code] ? { ...all, [code]: f(all[code]) } : all));
  const firstStart = firstActive ? (
    <AppFirstHome
      stocks={firstStocks}
      guide_open={false}
      picker_open={pickerOpen}
      saved={onboarding === 'first_saved'}
      onNextGuide={() => setPickerOpen(true)}
      onCloseGuide={() => {}}
      onSkip={() => { setPickerOpen(false); setFirstActive(false); }}
      onOpenPicker={() => setPickerOpen(true)}
      onClosePicker={() => setPickerOpen(false)}
      onPickStock={(stock) => { setPickerOpen(false); router.navigate({ pathname: '/memo/new', params: { code: stock.stock_code, name: stock.name, from_onboarding: '1', onboarding_selected: selected ?? '' } } as Href); }}
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
            { icon: 'bell', label: '알림', onPress: () => notice('알림') },
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
