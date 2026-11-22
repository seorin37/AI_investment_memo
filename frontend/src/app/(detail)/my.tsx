import React from 'react';
import { Platform } from 'react-native';
import Constants from 'expo-constants';
import { Redirect, useRouter, type Href } from 'expo-router';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';
import { mockMyUsage } from '@/ui/screens/my/My.mock';
import type { MyMenuKey } from '@/ui/screens/my/My.types';
import { AppMy } from '@/ui/screens/my/app/My';
import { useTheme } from '@/store/theme';

/** MY 하위 화면 (⑨-3b·c) */
const ROUTE: Record<MyMenuKey, Href> = { noti: '/my-noti', usage: '/my-usage', data: '/my-data', trash: '/my-trash', info: '/my-info', fb: '/my-feedback', help: '/my-help' };

/** 앱 MY = UI v2 (원본 app/my.html). 웹은 사이드바 프로필·설정 창을 쓰므로 홈으로 돌려보낸다. */
export default function MyScreen() {
  const router = useRouter();
  const { profile } = useMyProfile();
  const dark = useTheme((s) => s.dark);
  const setDark = useTheme((s) => s.setDark);
  const toggleDark = () => setDark(!dark);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppMy
      profile={profile}
      usage_pct={mockMyUsage.usage_pct}
      usage_renew={mockMyUsage.usage_renew}
      version={`memo's v${Constants.expoConfig?.version ?? ''} (베타)`}
      dark={dark}
      onBack={() => router.back()}
      onProfile={() => router.push('/my-profile')}
      onUsage={() => router.push('/my-usage')}
      onOpen={(key) => router.push(ROUTE[key])}
      onToggleDark={toggleDark}
    />
  );
}
