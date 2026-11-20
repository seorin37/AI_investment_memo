import React from 'react';
import { View } from 'react-native';
import { Redirect, Tabs, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth } from '@/store/auth';
import { chapterAt, fmt, useStudioPlayer } from '@/store/studioPlayer';
import { mockAudioEpisode } from '@/ui/screens/studio/Studio.mock';
import { AppMiniPlayer } from '@/ui/screens/studio/app/MiniPlayer';
import { size } from '@/ui/theme';
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
      <Mini hidden={hidden} />
    </View>
  );
}

/* ⑧-8b 미니 플레이어: 탭 바 위 10 (원본 .mini bottom 88). 탭을 바꿔도 남고, 위로 쌓이는 화면이 덮으면 가려짐 */
function Mini({ hidden }: { hidden: boolean }) {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const p = useStudioPlayer();
  const item = p.made.find((m) => m.id === p.cur);
  const ch = mockAudioEpisode.chapters[chapterAt(p.t)][1].split(' ·')[0];
  return (
    <AppMiniPlayer
      visible={p.mini && !!item && !hidden}
      bottom={1 + 65 + Math.max(size.tabBarPadBottom, insets.bottom) + 10}
      title={item?.title ?? ''}
      sub={`${ch} · ${fmt(p.t)} / ${fmt(mockAudioEpisode.dur)}`}
      progress={p.t / mockAudioEpisode.dur}
      playing={p.playing}
      onOpen={() => router.push('/studio-player')}
      onToggle={p.toggle}
      onClose={p.closeMini}
    />
  );
}
