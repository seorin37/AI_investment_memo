import React, { useEffect } from 'react';
import { useLocalSearchParams } from 'expo-router';
import { useJournal } from '@/store/journal';
import { WebJournal } from '@/ui/screens/journal/web/Journal';

/**
 * 웹 투자 기록 = UI v2 (ui/screens/journal/web · ⑦). 앱은 journal.native.tsx.
 * 기록은 store/journal — 실제 모드는 서버(GET·POST /journal · PATCH·DELETE /journal/{id}), mock 모드는 켜 둔 동안.
 * 쓰는 대로 화면에 바로 반영하고 서버에는 쉬는 틈에 저장.
 */
export default function JournalPage() {
  const sp = useLocalSearchParams<{ id?: string; empty?: string }>();
  const j = useJournal();
  const reset = j.reset;
  const load = j.load;
  /* 실제 모드: 서버 목록 받기 (같은 계정으로 이미 받았으면 그대로) */
  useEffect(() => {
    void load();
  }, [load]);
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
