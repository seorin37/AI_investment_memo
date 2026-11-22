import React, { useCallback, useMemo, useState } from 'react';
import { useCoach } from '@/store/coach';
import { Linking } from 'react-native';
import { useFocusEffect, useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { mockCustomBoard, mockHomeData, mockHomeSchedule } from '@/ui/screens/home/Home.mock';
import type { CustomItem } from '@/ui/screens/home/Home.types';
import { useHomeData } from '@/ui/screens/home/useHomeData';
import { useHomeMarket } from '@/ui/screens/home/useHomeMarket';
import { WebHome } from '@/ui/screens/home/web/Home';
import { useHomeNewsProps } from '@/ui/screens/home/useHomeNews';
import { mockOnboardingStocks } from '@/ui/screens/onboarding/Onboarding.mock';
import { WebFirstHome } from '@/ui/screens/onboarding/web/FirstHome';

/**
 * 웹 홈 = UI v2 (ui/screens/home/web · ②). 앱은 index.native.tsx.
 * 온보딩 query는 서버 상태가 아니라 현재 가입 흐름을 검증하기 위한 host 임시 상태다.
 */
export default function HomeScreen() {
  const router = useRouter();
  const { mode, fail, onboarding, home_mode, selected } = useLocalSearchParams<{ mode?: string; fail?: string; onboarding?: string; home_mode?: string; selected?: string }>();
  const [board, setBoard] = useState<CustomItem[]>(mockCustomBoard);
  const [retried, setRetried] = useState(false);
  /* 뉴스 GET /news/home · 내 데이터(이름 · 종목 수 · 업데이트 · 체크리스트 · 켜 둔 위젯) useHomeData (2026-11-22). 일정 달력은 아직 mock */
  const news = useHomeNewsProps();
  const home = useHomeData();
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
  /* 홈이 보이는 동안에만 — 종목을 골라 첫 메모로 넘어가면 타이머를 끊고, 저장 후 돌아오면 시작 */
  useFocusEffect(useCallback(() => {
    /* 첫 홈 안내 창 · 종목 고르기 창이 떠 있는 동안은 기다림 (창이 안내보다 위에 그려져서) */
    if (!onboarding || guideOpen || pickerOpen) return;
    const t = setTimeout(startCoach, 600);
    return () => clearTimeout(t);
  }, [onboarding, guideOpen, pickerOpen, startCoach]));
  const marketOk = !(__DEV__ && fail === '1') || retried;
  /* 시장 지수: 실제 모드면 GET /market/overview, mock 모드면 Home.mock (2026-11-21) */
  const hm = useHomeMarket();
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
      {...home.data}
      mode={(home_mode ?? mode) === 'custom' ? 'custom' : 'template'}
      firstStart={firstStart}
      {...news}
      market={marketOk ? hm.market : null}
      days={hm.days}
      schedule={mockHomeSchedule}
      board={board}
      onChangeBoard={setBoard}
      onGoStart={() => router.navigate('/onboarding/pick')}
      onChangeWidgets={home.onChangeWidgets}
      onOpenUpdates={() => router.navigate('/updates')}
      onOpenStockUpdates={(code) => router.navigate({ pathname: '/updates/[code]', params: { code } })}
      onOpenStock={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code } })}
      onOpenNews={(n) => Linking.openURL(n.url)}
      onRetryMarket={() => { setRetried(true); hm.retry(); }}
      onToggleCheck={home.onToggleCheck}
      onAddCheck={home.onAddCheck}
      onNudge={() => {}}
    />
  );
}
