import React from 'react';
import { View } from 'react-native';
import { Redirect, Tabs } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
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
  const insets = useSafeAreaInsets();
  if (status !== 'signedIn') return <Redirect href="/intro" />;
  return (
    <View style={{ flex: 1 }}>
      <Tabs
        backBehavior="firstRoute"
        screenOptions={{ headerShown: false, animation: 'fade' }}
        tabBar={({ state, navigateToTab }) => (
          /* 숨김(메모 고르기 중)이면 탭바 자리를 기기 아래 안전 영역 높이로 접는다 — 고르기 막대(MemoBoard selBar, 80)가
             탭바 자리에 바로 오고, 탭바 없는 화면과 아래 여백이 같아짐. 탭바는 접힌 자리 안에서 아래로 내려가며 사라짐 */
          <View style={hidden ? { height: insets.bottom, overflow: 'hidden', backgroundColor: '#FFFFFF' } : undefined}>
            <BottomTabBar
              current={TAB_OF[state.routes[state.index]?.name ?? 'index'] ?? 'home'}
              hidden={hidden}
              badges={{ updates: UNREAD }}
              onPress={(tab) => {
                const route = state.routes.find((r) => r.name === ROUTE_OF[tab]);
                if (route) navigateToTab(route.key);
              }}
            />
          </View>
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
