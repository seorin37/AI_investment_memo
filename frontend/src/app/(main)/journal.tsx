import React, { useState } from 'react';
import { useLocalSearchParams } from 'expo-router';
import { mockJournal } from '@/ui/screens/journal/Journal.mock';
import type { JournalEntry } from '@/ui/screens/journal/Journal.types';
import { WebJournal } from '@/ui/screens/journal/web/Journal';

/**
 * 웹 투자 기록 = UI v2 (ui/screens/journal/web · ⑦). 앱은 journal.native.tsx.
 * mock: Journal.mock — 고정·휴지통·되돌리기는 이 화면 안에서만. 옛 화면은 features/journal/LegacyJournalRoute.tsx 로 옮겨 보관.
 */
export default function JournalPage() {
  const sp = useLocalSearchParams<{ id?: string; empty?: string }>();
  const [entries, setEntries] = useState<JournalEntry[]>(() => (__DEV__ && sp.empty === '1' ? [] : mockJournal));
  return (
    <WebJournal
      entries={entries}
      initialId={sp.id}
      onOpen={() => {}}
      onNew={() => {}}
      onPin={(ids, on) => setEntries((all) => all.map((j) => (ids.includes(j.id) ? { ...j, pinned: on } : j)))}
      onTrash={(ids) => setEntries((all) => all.filter((j) => !ids.includes(j.id)))}
      onRestore={setEntries}
    />
  );
}
