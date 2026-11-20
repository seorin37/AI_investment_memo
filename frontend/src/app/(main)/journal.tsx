import React, { useEffect } from 'react';
import { useLocalSearchParams } from 'expo-router';
import { useJournal } from '@/store/journal';
import { WebJournal } from '@/ui/screens/journal/web/Journal';

/**
 * 웹 투자 기록 = UI v2 (ui/screens/journal/web · ⑦). 앱은 journal.native.tsx.
 * 기록은 store/journal (mock · 켜 둔 동안) — 쓰는 대로 바로 반영. 옛 화면은 features/journal/LegacyJournalRoute.tsx 로 옮겨 보관.
 */
export default function JournalPage() {
  const sp = useLocalSearchParams<{ id?: string; empty?: string }>();
  const j = useJournal();
  const reset = j.reset;
  useEffect(() => {
    if (__DEV__ && sp.empty === '1') reset(true);
  }, [sp.empty, reset]);
  return (
    <WebJournal
      entries={j.entries}
      initialId={sp.id}
      onOpen={() => {}}
      onNew={j.addWeb}
      onUpdate={j.updateWeb}
      onDropEmpty={j.dropEmpty}
      onPin={j.pin}
      onTrash={j.trash}
      onRestore={j.restore}
    />
  );
}
