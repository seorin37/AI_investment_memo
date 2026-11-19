import React, { useCallback, useState } from 'react';
import { Linking } from 'react-native';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { useUI } from '@/store/ui';
import type { Checklist } from '@/types/models';
import { TopBar } from '@/ui/layout/app/TopBar';
import { AppHome } from '@/ui/screens/home/app/Home';
import { mockHomeData, mockHomeSearch } from '@/ui/screens/home/Home.mock';
import type { HomeWidget } from '@/ui/screens/home/Home.types';

/**
 * 앱 홈 탭 = UI v2 (ui/screens/home/app · ②). 웹은 index.tsx.
 * mock 단계: Home.mock (11.18 종가 기준). 위젯 순서·체크리스트 변화는 이 화면 안에서만.
 * ?fail=1: 시장 위젯 불러오기 실패 상태 (5초 뒤 자동 다시 시도).
 * 홈에서 가는 길: 업데이트 탭 · 종목별 업데이트 · 검색 → 메모 보드(③) · 지수 자세히(/market/[key]) · MY.
 */
export default function HomeTab() {
  const router = useRouter();
  const notice = useMockNotice();
  const setTabBarHidden = useUI((s) => s.setTabBarHidden);
  const { fail } = useLocalSearchParams<{ fail?: string }>();
  const [widgets, setWidgets] = useState<HomeWidget[]>(mockHomeData.widgets);
  const [checklists, setChecklists] = useState<Record<string, Checklist>>(mockHomeData.checklists);
  const [retried, setRetried] = useState(false);
  const marketOk = fail !== '1' || retried;
  /* 다른 탭으로 가면 편집 때문에 숨긴 탭바를 다시 보이게 */
  useFocusEffect(useCallback(() => () => setTabBarHidden(false), [setTabBarHidden]));
  const patchCl = (code: string, f: (c: Checklist) => Checklist) => setChecklists((all) => (all[code] ? { ...all, [code]: f(all[code]) } : all));
  return (
    <AppHome
      {...mockHomeData}
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
