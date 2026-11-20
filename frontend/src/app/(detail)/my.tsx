import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useMyMock } from '@/store/myMock';
import { useUI } from '@/store/ui';
import { mockMyUsage, mockMyVersion } from '@/ui/screens/my/My.mock';
import type { MyMenuKey } from '@/ui/screens/my/My.types';
import { AppMy } from '@/ui/screens/my/app/My';

/** ⑨-3a 이후 묶음에서 채울 하위 화면 이름 */
const LATER: Record<MyMenuKey, string> = { noti: '알림', usage: '사용량', data: '데이터', trash: '휴지통', info: '정보', fb: '피드백 보내기', help: '도움말' };

/** 앱 MY = UI v2 (원본 app/my.html). 웹은 사이드바 프로필·설정 창을 쓰므로 홈으로 돌려보낸다. */
export default function MyScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const profile = useMyMock((s) => s.profile);
  const dark = useMyMock((s) => s.dark);
  const toggleDark = useMyMock((s) => s.toggleDark);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppMy
      profile={profile}
      {...mockMyUsage}
      version={mockMyVersion}
      dark={dark}
      onBack={() => router.back()}
      onProfile={() => router.push('/my-profile')}
      onUsage={() => toast('사용량 화면은 다음 묶음에서 열려요')}
      onOpen={(key) => toast(`${LATER[key]} 화면은 다음 묶음에서 열려요`)}
      onToggleDark={toggleDark}
    />
  );
}
