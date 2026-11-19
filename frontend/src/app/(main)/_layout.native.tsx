import React from 'react';
import { View } from 'react-native';
import { Redirect, Tabs } from 'expo-router';
import { useAuth } from '@/store/auth';
import { useUI } from '@/store/ui';
import { BottomTabBar } from '@/ui/layout/app/BottomTabBar';
import { mockTabBadges } from '@/ui/layout/app/BottomTabBar.mock';
import type { AppTab } from '@/ui/layout/app/BottomTabBar.types';

/**
 * 앱(안드로이드·iOS) 로그인 후 영역: UI v2 아래 탭 5개. 웹은 같은 폴더의 _layout.tsx(WebShell).
 * 옛 탭바(components/layout/BottomTabBar)·MobileToast 는 지우지 않고 여기서만 뺌. 탭 안 화면은 아직 옛 화면.
 * 탭 안 화면 밀기는 updates/ · stocks/ 의 _layout.native.tsx(Stack), 탭바를 가리는 화면은 app/(detail)/.
 */
const ROUTE_OF: Record<AppTab, string> = { home: 'index', updates: 'updates', stocks: 'stocks', journal: 'journal', studio: 'studio/index' };
const TAB_OF: Record<string, AppTab> = { index: 'home', updates: 'updates', stocks: 'stocks', journal: 'journal', 'studio/index': 'studio' };

export default function MainTabsLayout() {
  const status = useAuth((s) => s.status);
  /* 메모 고르기 중 탭바 숨김 (옛 보드가 store/ui 로 알려 줌) */
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
            badges={mockTabBadges}
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
    </View>
  );
}
