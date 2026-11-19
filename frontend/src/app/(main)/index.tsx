import React, { useState } from 'react';
import { Linking } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import type { Checklist } from '@/types/models';
import { mockCustomBoard, mockHomeData, mockHomeSchedule } from '@/ui/screens/home/Home.mock';
import type { CustomItem, HomeWidget } from '@/ui/screens/home/Home.types';
import { WebHome } from '@/ui/screens/home/web/Home';

/**
 * 웹 홈 = UI v2 (ui/screens/home/web · ②). 앱은 index.native.tsx.
 * mock 단계: Home.mock (11.18 종가 기준). 위젯 순서·맞춤 홈 배치·체크리스트 변화는 이 화면 안에서만.
 * ?mode=custom: 홈 직접 사용자화 · ?fail=1: 시장 위젯 불러오기 실패.
 */
export default function HomeScreen() {
  const router = useRouter();
  const { mode, fail } = useLocalSearchParams<{ mode?: string; fail?: string }>();
  const [widgets, setWidgets] = useState<HomeWidget[]>(mockHomeData.widgets);
  const [board, setBoard] = useState<CustomItem[]>(mockCustomBoard);
  const [checklists, setChecklists] = useState<Record<string, Checklist>>(mockHomeData.checklists);
  const [retried, setRetried] = useState(false);
  const marketOk = fail !== '1' || retried;
  const patchCl = (code: string, f: (c: Checklist) => Checklist) => setChecklists((all) => (all[code] ? { ...all, [code]: f(all[code]) } : all));
  return (
    <WebHome
      {...mockHomeData}
      mode={mode === 'custom' ? 'custom' : 'template'}
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
