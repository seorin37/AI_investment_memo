import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { env } from '@/config/env';
import { useJournal } from '@/store/journal';
import { AppNote } from '@/ui/screens/journal/app/Note';
import { mockJournalNow } from '@/ui/screens/journal/Journal.mock';
import { journalDates } from '@/ui/screens/journal/journalApi';
import { isEmptyEntry } from '@/ui/screens/journal/journalParts';
import type { JBlock } from '@/ui/screens/journal/Journal.types';

/**
 * 앱 투자 기록 보기·쓰기 = UI v2 (ui/screens/journal/app/Note · ⑦-7b). id 'new' = 새 기록.
 * 저장은 store/journal (실제 모드는 서버 · mock 모드는 앱을 켜 둔 동안). 나갈 때 확인창 없이 저장 (원본 back) → 목록이 알림·반짝임.
 */
export default function JournalNoteScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const entries = useJournal((s) => s.entries);
  const saveApp = useJournal((s) => s.saveApp);
  const pin = useJournal((s) => s.pin);
  const setFlash = useJournal((s) => s.setFlash);
  const load = useJournal((s) => s.load);
  /* 기록 화면으로 바로 들어와도 목록이 있게 (실제 모드 · 이미 받았으면 그대로) */
  useEffect(() => {
    void load();
  }, [load]);
  /* 아래 [새 기록]은 같은 화면에서 새 기록으로 바꿈 (원본 act('new')) */
  const [cur, setCur] = useState(id ?? 'new');
  const isNew = cur.startsWith('new');
  const entry = isNew ? null : (entries.find((j) => j.id === cur) ?? null);
  const pinned = !!entry?.pinned;
  const dropEmpty = useJournal((s) => s.dropEmpty);
  /* 자동 저장 (웹과 같게 쓰는 동안 저장): 새 기록은 첫 저장 때 생긴 id 로 이어서. 이 화면에서 처음 만들었는지도 기억 (나갈 때 '저장했어요' 알림) */
  const saved = useRef<{ id: string | null; made: boolean }>({ id: entry?.id ?? null, made: false });
  const autoSave = useCallback((blocks: JBlock[]) => {
    const r = saveApp(saved.current.id, blocks);
    if (r?.isNew) saved.current = { id: r.id, made: true };
  }, [saveApp]);
  const finish = (blocks: JBlock[]) => {
    const s = saved.current;
    /* 글을 다 지웠으면 이미 저장된 빈 기록은 지움 (웹 dropEmpty) */
    if (s.id && isEmptyEntry(blocks)) {
      saveApp(s.id, blocks);
      dropEmpty(s.id);
      return { r: null, empty: s.made || isNew };
    }
    const r = saveApp(s.id, blocks);
    return { r: r ?? (s.made && s.id ? { id: s.id, isNew: true } : null), empty: isNew && !s.made && !r };
  };
  return (
    <AppNote
      key={cur}
      entry={entry}
      full={env.useMock ? mockJournalNow.full : journalDates(new Date().toISOString()).full}
      pinned={pinned}
      onAutoSave={autoSave}
      onBack={(blocks) => {
        const { r, empty } = finish(blocks);
        if (r) setFlash({ kind: 'saved', id: r.id, isNew: r.isNew });
        else if (empty) setFlash({ kind: 'empty' });
        router.back();
      }}
      onNew={(blocks) => {
        finish(blocks);
        saved.current = { id: null, made: false };
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
