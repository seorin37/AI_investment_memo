import React, { useState } from 'react';
import { useRouter } from 'expo-router';
import { MobileScreen, useProfileAction } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { useLargeTitle } from '@/components/motion/Navigation';
import { UpdateFeed } from '@/features/updates/UpdateFeed';
import { mockUpdateFeedProps } from '@/features/updates/UpdateFeed.mock';

/** 앱 업데이트 탭 (웹은 index.tsx 의 UpdatesOverview). mock 단계 */
export default function UpdatesTab() {
  const router = useRouter();
  const profile = useProfileAction();
  const lt = useLargeTitle();
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <MobileScreen bar={<TopBar left="title" title="최신 업데이트" actions={[profile]} lineOpacity={lt.barLineOpacity} />}>
      <UpdateFeed
        {...mockUpdateFeedProps}
        selected_stock={selected}
        onSelectStock={setSelected}
        onOpenStock={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
        onOpenItem={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
        onScroll={lt.onScroll}
      />
    </MobileScreen>
  );
}
