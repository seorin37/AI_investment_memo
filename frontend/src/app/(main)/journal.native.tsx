import React, { useCallback, useState } from 'react';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { TopBar } from '@/ui/layout/app/TopBar';
import { AppJournal } from '@/ui/screens/journal/app/Journal';
import { mockJournal } from '@/ui/screens/journal/Journal.mock';
import type { JournalEntry } from '@/ui/screens/journal/Journal.types';

const NOT_YET = '아직 연결되지 않았어요 · 데이터는 그대로예요';

/**
 * 앱 투자 기록 탭 = UI v2 (ui/screens/journal/app · ⑦). 웹은 journal.tsx.
 * mock: Journal.mock — 고정·휴지통·되돌리기는 앱을 켜 둔 동안 이 화면 안에서만.
 * 옛 목록(features/journal/JournalList)은 지우지 않고 라우트에서만 뺌.
 */
export default function JournalTab() {
  const router = useRouter();
  const sp = useLocalSearchParams<{ empty?: string }>();
  const setTabBarHidden = useUI((s) => s.setTabBarHidden);
  const [entries, setEntries] = useState<JournalEntry[]>(() => (__DEV__ && sp.empty === '1' ? [] : mockJournal));
  const [viewSig, setViewSig] = useState(0);
  const [notice, setNotice] = useState<{ key: number; message: string }>();
  const toast = (message: string) => setNotice((n) => ({ key: (n?.key ?? 0) + 1, message }));
  useFocusEffect(useCallback(() => () => setTabBarHidden(false), [setTabBarHidden]));
  const onSelectionChange = useCallback((n: number) => setTabBarHidden(n > 0), [setTabBarHidden]);
  return (
    <AppJournal
      entries={entries}
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
      onOpen={() => toast(NOT_YET)}
      onNew={() => toast(NOT_YET)}
      onPin={(ids, on) => setEntries((all) => all.map((j) => (ids.includes(j.id) ? { ...j, pinned: on } : j)))}
      onTrash={(ids) => setEntries((all) => all.filter((j) => !ids.includes(j.id)))}
      onRestore={setEntries}
    />
  );
}
