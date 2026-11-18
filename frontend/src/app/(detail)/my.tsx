import React, { useState } from 'react';
import { useRouter } from 'expo-router';
import { MobileScreen, useMockNotice } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { MyPage } from '@/features/settings/MyPage';
import { mockMyPageProps } from '@/features/settings/MyPage.mock';

/** MY — 상단 바 프로필로 들어옴. mock 단계 */
export default function MyScreen() {
  const router = useRouter();
  const notice = useMockNotice();
  const [dark, setDark] = useState(mockMyPageProps.dark_mode);
  return (
    <MobileScreen bar={<TopBar left="back" title="MY" onBack={() => router.back()} />}>
      <MyPage {...mockMyPageProps} dark_mode={dark} onToggleDark={setDark} onOpen={(key) => notice(`MY · ${key}`)} />
    </MobileScreen>
  );
}
