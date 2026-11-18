import React from 'react';
import { View } from 'react-native';
import { Redirect, Tabs } from 'expo-router';
import { BottomTabBar, type MobileTab } from '@/components/layout/BottomTabBar';
import { MobileToast } from '@/components/layout/MobileScreen';
import { mockFeedStocks } from '@/features/updates/UpdateFeed.mock';
import { useAuth } from '@/store/auth';
import { useUI } from '@/store/ui';

/**
 * 앱(안드로이드·iOS) 로그인 후 영역: 하단 탭 5개 + 상단 바(각 화면). 웹은 같은 폴더의 _layout.tsx(AppShell · 사이드바)를 그대로 쓴다.
 * 탭 안 화면 밀기는 updates/ · stocks/ 의 _layout.native.tsx(Stack), 탭바를 가리는 화면은 app/(detail)/.
 * 로그인 전이면 소개(IntroSlides) → 로그인.
 */
const ROUTE_OF: Record<MobileTab, string> = { home: 'index', updates: 'updates', stocks: 'stocks', journal: 'journal', studio: 'studio/index' };
const TAB_OF: Record<string, MobileTab> = { index: 'home', updates: 'updates', stocks: 'stocks', journal: 'journal', 'studio/index': 'studio' };
/* mock 단계 배지: 읽지 않은 소식 수 (다음 단계에서 useUpdates 로) */
const UNREAD = mockFeedStocks.reduce((n, s) => n + s.items.filter((i) => i.unread).length, 0);

export default function MainTabsLayout() {
  const status = useAuth((s) => s.status);
  const hidden = useUI((s) => s.tabBarHidden);
  if (status !== 'signedIn') return <Redirect href="/intro" />;
  return (
    <View style={{ flex: 1 }}>
      <Tabs
        backBehavior="firstRoute"
        screenOptions={{ headerShown: false, animation: 'fade' }}
        tabBar={({ state, navigateToTab }) => (
          <BottomTabBar
            current={TAB_OF[state.routes[state.index]?.name ?? 'index'] ?? 'home'}
            hidden={hidden}
            badges={{ updates: UNREAD }}
            onPress={(tab) => {
              const route = state.routes.find((r) => r.name === ROUTE_OF[tab]);
              if (route) navigateToTab(route.key);
            }}
          />
        )}
      >
        <Tabs.Screen name="index" />
        <Tabs.Screen name="updates" />
        <Tabs.Screen name="stocks" />
        <Tabs.Screen name="journal" />
        <Tabs.Screen name="studio/index" />
        <Tabs.Screen name="help" options={{ href: null }} />
      </Tabs>
      <MobileToast />
    </View>
  );
}
