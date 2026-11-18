import React from 'react';
import { useRouter } from 'expo-router';
import { MobileScreen, useMockNotice, useProfileAction } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { useLargeTitle } from '@/components/motion/Navigation';
import { JournalList } from '@/features/journal/JournalList';
import { mockJournalListProps } from '@/features/journal/JournalList.mock';

/** 앱 투자 기록 탭 (웹은 journal.tsx). 기록을 열면 기존 JournalEditor (/journal/[id]). mock 단계 */
export default function JournalTab() {
  const router = useRouter();
  const profile = useProfileAction();
  const notice = useMockNotice();
  const lt = useLargeTitle();
  return (
    <MobileScreen bar={<TopBar left="title" title="투자 기록" actions={[profile]} lineOpacity={lt.barLineOpacity} />}>
      <JournalList
        {...mockJournalListProps}
        onOpen={(id) => router.push({ pathname: '/journal/[id]', params: { id } })}
        onNew={() => notice('새 기록')}
        onDictate={() => notice('받아쓰기')}
        onLongPress={() => notice('여러 개 고르기')}
        onPin={() => notice('고정')}
        onDelete={() => notice('휴지통')}
        onScroll={lt.onScroll}
      />
    </MobileScreen>
  );
}
