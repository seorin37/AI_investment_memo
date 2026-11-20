import React from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { MobileScreen } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { Loading } from '@/components/ui/primitives';
import { JournalEditor } from '@/features/journal/JournalEditor';
import { useJournal } from '@/hooks/queries';

/**
 * 투자 기록 편집 — 기존 JournalEditor 를 그대로 씀 (11.18 결정).
 * mock 단계: 목록(JournalList.mock)과 기록 데이터(앱 mock API)의 id 가 달라, 못 찾으면 첫 기록을 보여 줌.
 */
export default function JournalEditScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { data } = useJournal();
  const entry = data?.find((j) => j.id === id) ?? data?.[0];
  return (
    <MobileScreen bg="#FFFFFF" bar={<TopBar left="back" title="투자 기록" onBack={() => router.back()} />}>
      {entry ? <JournalEditor key={entry.id} entry={entry} onDelete={() => router.back()} /> : <Loading height={300} />}
    </MobileScreen>
  );
}
