import React, { useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useJournal } from '@/store/journal';
import { AppNote } from '@/ui/screens/journal/app/Note';
import { mockJournalNow } from '@/ui/screens/journal/Journal.mock';

/**
 * 앱 투자 기록 보기·쓰기 = UI v2 (ui/screens/journal/app/Note · ⑦-7b). id 'new' = 새 기록.
 * 저장은 store/journal (mock · 앱을 켜 둔 동안). 나갈 때 확인창 없이 저장 (원본 back) → 목록이 알림·반짝임.
 * 옛 화면(JournalEditor)은 features/journal/LegacyJournalDetailRoute.tsx 로 옮겨 보관.
 */
export default function JournalNoteScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const entries = useJournal((s) => s.entries);
  const saveApp = useJournal((s) => s.saveApp);
  const pin = useJournal((s) => s.pin);
  const setFlash = useJournal((s) => s.setFlash);
  /* 아래 [새 기록]은 같은 화면에서 새 기록으로 바꿈 (원본 act('new')) */
  const [cur, setCur] = useState(id ?? 'new');
  const isNew = cur.startsWith('new');
  const entry = isNew ? null : (entries.find((j) => j.id === cur) ?? null);
  const pinned = !!entry?.pinned;
  return (
    <AppNote
      key={cur}
      entry={entry}
      full={mockJournalNow.full}
      pinned={pinned}
      onBack={(blocks) => {
        const r = saveApp(entry?.id ?? null, blocks);
        if (r) setFlash({ kind: 'saved', id: r.id, isNew: r.isNew });
        else if (isNew) setFlash({ kind: 'empty' });
        router.back();
      }}
      onNew={(blocks) => {
        saveApp(entry?.id ?? null, blocks);
        setCur(`new${Date.now()}`);
      }}
      onPin={() => entry && pin([entry.id], !pinned)}
      onTrash={() => {
        if (entry) setFlash({ kind: 'trash', id: entry.id });
        router.back();
      }}
    />
  );
}
