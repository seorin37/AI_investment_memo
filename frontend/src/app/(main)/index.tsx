import React, { useEffect, useMemo, useState } from 'react';
import { useCoach } from '@/store/coach';
import { Linking } from 'react-native';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import type { Checklist } from '@/types/models';
import { mockCustomBoard, mockHomeData, mockHomeSchedule } from '@/ui/screens/home/Home.mock';
import type { CustomItem, HomeWidget } from '@/ui/screens/home/Home.types';
import { WebHome } from '@/ui/screens/home/web/Home';
import { mockOnboardingStocks } from '@/ui/screens/onboarding/Onboarding.mock';
import { WebFirstHome } from '@/ui/screens/onboarding/web/FirstHome';

/**
 * 웹 홈 = UI v2 (ui/screens/home/web · ②). 앱은 index.native.tsx.
 * 온보딩 query는 서버 상태가 아니라 현재 가입 흐름을 검증하기 위한 host 임시 상태다.
 */
export default function HomeScreen() {
  const router = useRouter();
  const { mode, fail, onboarding, home_mode, selected } = useLocalSearchParams<{ mode?: string; fail?: string; onboarding?: string; home_mode?: string; selected?: string }>();
  const [widgets, setWidgets] = useState<HomeWidget[]>(mockHomeData.widgets);
  const [board, setBoard] = useState<CustomItem[]>(mockCustomBoard);
  const [checklists, setChecklists] = useState<Record<string, Checklist>>(mockHomeData.checklists);
  const [retried, setRetried] = useState(false);
  const [firstActive, setFirstActive] = useState(!!onboarding);
  const [guideOpen, setGuideOpen] = useState(onboarding === 'welcome');
  const [pickerOpen, setPickerOpen] = useState(false);
  const selectedCodes = useMemo(() => (selected ?? '').split(',').map((v) => v.split(':')[0]).filter(Boolean), [selected]);
  const firstStocks = useMemo(() => {
    const found = mockOnboardingStocks.filter((s) => selectedCodes.includes(s.stock_code));
    return found.length ? found : mockOnboardingStocks.slice(0, 3);
  }, [selectedCodes]);
  const saved = onboarding === 'first_saved';
  /* 종목 고르기를 마치고 처음 홈에 오면 0.6초 뒤 사용법 안내 (원본 App.tsx coachPending) — 처음 한 번만 */
  const startCoach = useCoach((s) => s.startFirst);
  useEffect(() => {
    /* 첫 홈 안내 창 · 종목 고르기 창이 떠 있는 동안은 기다림 (창이 안내보다 위에 그려져서) */
    if (!onboarding || guideOpen || pickerOpen) return;
    const t = setTimeout(startCoach, 600);
    return () => clearTimeout(t);
  }, [onboarding, guideOpen, pickerOpen, startCoach]);
  const marketOk = fail !== '1' || retried;
  const patchCl = (code: string, f: (c: Checklist) => Checklist) => setChecklists((all) => (all[code] ? { ...all, [code]: f(all[code]) } : all));
  const firstStart = firstActive ? (
    <WebFirstHome
      stocks={firstStocks}
      guide_open={guideOpen}
      picker_open={pickerOpen}
      saved={saved}
      onNextGuide={() => { setGuideOpen(false); setPickerOpen(true); }}
      onCloseGuide={() => setGuideOpen(false)}
      onSkip={() => { setGuideOpen(false); setPickerOpen(false); setFirstActive(false); }}
      onOpenPicker={() => setPickerOpen(true)}
      onClosePicker={() => setPickerOpen(false)}
      onPickStock={(stock) => { setPickerOpen(false); router.navigate({ pathname: '/stocks/[code]', params: { code: stock.stock_code, stock_name: stock.name, first: '1', onboarding_selected: selected ?? '', onboarding_home_mode: home_mode ?? mode ?? 'template' } } as Href); }}
    />
  ) : undefined;
  return (
    <WebHome
      {...mockHomeData}
      mode={(home_mode ?? mode) === 'custom' ? 'custom' : 'template'}
      firstStart={firstStart}
      widgets={widgets}
      checklists={checklists}
      market={marketOk ? mockHomeData.market : null}
      schedule={mockHomeSchedule}
      board={board}
      onChangeBoard={setBoard}
      onGoStart={() => router.navigate('/onboarding/pick')}
      onChangeWidgets={setWidgets}
      onOpenUpdates={() => router.navigate('/updates')}
      onOpenStockUpdates={(code) => router.navigate({ pathname: '/updates/[code]', params: { code } })}
      onOpenStock={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code } })}
      onOpenNews={(n) => Linking.openURL(n.url)}
      onRetryMarket={() => setRetried(true)}
      onToggleCheck={(code, id) => patchCl(code, (c) => ({ ...c, items: c.items.map((i) => (i.id === id ? { ...i, done: !i.done } : i)) }))}
      onAddCheck={(code, text) => patchCl(code, (c) => ({ ...c, items: [...c.items, { id: `n${c.items.length + 1}`, text, done: false }] }))}
      onNudge={() => {}}
    />
  );
}
