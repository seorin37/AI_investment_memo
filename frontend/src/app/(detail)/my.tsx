import React from 'react';
import { Platform, View } from 'react-native';
import Constants from 'expo-constants';
import { Redirect, useRouter, type Href } from 'expo-router';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';
import { useUsageView } from '@/ui/screens/my/useUsageView';
import type { MyMenuKey } from '@/ui/screens/my/My.types';
import { AppMy } from '@/ui/screens/my/app/My';
import { useTheme } from '@/store/theme';
import { BottomTabBar } from '@/ui/layout/app/BottomTabBar';
import { useUpdatesUnread } from '@/ui/screens/updates/app/useAppUpdates';
import type { AppTab } from '@/ui/layout/app/BottomTabBar.types';

const TAB_HREF: Record<AppTab, Href> = { home: '/', updates: '/updates', stocks: '/stocks', journal: '/journal', studio: '/studio' };

/** MY 하위 화면 (⑨-3b·c) */
const ROUTE: Record<MyMenuKey, Href> = { noti: '/my-noti', usage: '/my-usage', data: '/my-data', trash: '/my-trash', info: '/my-info', fb: '/my-feedback', help: '/my-help' };

/** 앱 MY = UI v2 (원본 app/my.html). 웹은 사이드바 프로필·설정 창을 쓰므로 홈으로 돌려보낸다. */
export default function MyScreen() {
  const router = useRouter();
  /* 아래 탭 '업데이트' 배지 = 읽지 않은 소식 수 (수정 76) */
  const updatesUnread = useUpdatesUnread();
  const { profile } = useMyProfile();
  /* AI 사용량: 실제 모드면 GET /me/usage, mock 모드면 My.mock */
  const usage = useUsageView();
  const dark = useTheme((s) => s.dark);
  const setDark = useTheme((s) => s.setDark);
  const toggleDark = () => setDark(!dark);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <View style={{ flex: 1 }}>
      <AppMy
        profile={profile}
        usage_pct={usage.usage_pct}
        usage_renew={usage.usage_renew}
        version={`memo's v${Constants.expoConfig?.version ?? ''} (베타)`}
        dark={dark}
        onBack={() => router.back()}
        onProfile={() => router.push('/my-profile')}
        onUsage={() => router.push('/my-usage')}
        onOpen={(key) => router.push(ROUTE[key])}
        onToggleDark={toggleDark}
      />
      {/* 선택된 탭 없음. 누르면 MY 를 닫고 아래 깔린 탭 화면으로 */}
      <BottomTabBar current={null} badges={{ updates: updatesUnread }} onPress={(tab) => router.dismissTo(TAB_HREF[tab])} />
    </View>
  );
}
