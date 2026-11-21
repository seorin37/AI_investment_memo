import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useJournal } from '@/store/journal';
import { useUI } from '@/store/ui';
import { TopBar } from '@/ui/layout/app/TopBar';
import { AppJournal } from '@/ui/screens/journal/app/Journal';

const NOT_YET = '아직 연결되지 않았어요 · 데이터는 그대로예요';

/**
 * 앱 투자 기록 탭 = UI v2 (ui/screens/journal/app · ⑦). 웹은 journal.tsx.
 * 기록은 store/journal (mock · 앱을 켜 둔 동안) — 기록 화면(/journal/[id])과 같이 씀.
 */
export default function JournalTab() {
  const router = useRouter();
  const sp = useLocalSearchParams<{ empty?: string }>();
  const setTabBarHidden = useUI((s) => s.setTabBarHidden);
  const j = useJournal();
  const [viewSig, setViewSig] = useState(0);
  const [notice, setNotice] = useState<{ key: number; message: string }>();
  const toast = (message: string) => setNotice((n) => ({ key: (n?.key ?? 0) + 1, message }));
  /* 기록 화면 열기 — 빠르게 두 번 눌러도 한 번만 */
  const busy = useRef(false);
  const go = (id: string) => {
    if (busy.current) return;
    busy.current = true;
    setTimeout(() => (busy.current = false), 800);
    router.push({ pathname: '/journal/[id]', params: { id } });
  };
  const reset = j.reset;
  useEffect(() => {
    if (__DEV__ && sp.empty === '1') reset(true);
  }, [sp.empty, reset]);
  useFocusEffect(useCallback(() => () => setTabBarHidden(false), [setTabBarHidden]));
  const onSelectionChange = useCallback((n: number) => setTabBarHidden(n > 0), [setTabBarHidden]);
  return (
    <AppJournal
      entries={j.entries}
      header={
        <TopBar
          preset="journal"
          title="투자 기록"
          actions={[
            { icon: 'moreHPurple', label: '더 보기', size: 34, iconSize: 18, color: '#16171A', onPress: () => setViewSig((n) => n + 1) },
            { icon: 'bell', label: '알림', onPress: () => toast(NOT_YET) },
          ]}
          avatar={{ name: '김나라', onPress: () => router.push('/my') }}
        />
      }
      viewSheetSignal={viewSig}
      onSelectionChange={onSelectionChange}
      notice={notice}
      flash={j.flash}
      onFlashDone={() => j.setFlash(null)}
      onOpen={(id) => go(id)}
      onNew={() => go('new')}
      onPin={j.pin}
      onTrash={j.trash}
      onRestore={j.restore}
    />
  );
}
