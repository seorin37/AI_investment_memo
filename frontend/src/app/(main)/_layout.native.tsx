import React, { useEffect, useRef } from 'react';
import { View } from 'react-native';
import { Redirect, Tabs, usePathname, useRouter } from 'expo-router';
import { useCoach } from '@/store/coach';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth } from '@/store/auth';
import { chapterAt, fmt, useStudioPlayer } from '@/store/studioPlayer';
import { epOf } from '@/ui/screens/studio/audioEp';
import { AppMiniPlayer } from '@/ui/screens/studio/app/MiniPlayer';
import { size } from '@/ui/theme';
import { useUI } from '@/store/ui';
import { useStudioItemsSync } from '@/ui/screens/studio/studioItems';
import { BottomTabBar } from '@/ui/layout/app/BottomTabBar';
import { AppSnackbar } from '@/ui/shared/Snackbar';
import { mockTabBadges } from '@/ui/layout/app/BottomTabBar.mock';
import type { AppTab } from '@/ui/layout/app/BottomTabBar.types';
import { useAiOffPrompt } from '@/ui/shared/useAiOffChoice';

/**
 * 앱(안드로이드·iOS) 로그인 후 영역: UI v2 아래 탭 5개. 웹은 같은 폴더의 _layout.tsx(WebShell).
 * 탭 안 화면 밀기는 updates/ · stocks/ 의 _layout.native.tsx(Stack), 탭바를 가리는 화면은 app/(detail)/.
 */
const ROUTE_OF: Record<AppTab, string> = { home: 'index', updates: 'updates', stocks: 'stocks', journal: 'journal', studio: 'studio/index' };
const TAB_OF: Record<string, AppTab> = { index: 'home', updates: 'updates', stocks: 'stocks', journal: 'journal', 'studio/index': 'studio' };

export default function MainTabsLayout() {
  const status = useAuth((s) => s.status);
  /* 스튜디오 만든 항목: 실제 모드면 서버 목록으로 (2026-11-23) */
  useStudioItemsSync();
  /* 크레딧을 다 썼고 AI 연결 메모가 남아 있으면 '충전 · 업그레이드 · 모두 끄기' 한 번 묻기 (2026-11-24) */
  useAiOffPrompt();
  /* 로그인한 채 다른 사용자로 바뀌면(A → B) 커짐 → 탭을 다시 마운트해 열린 화면을 새 사용자 값으로 (store/auth sessionKey) */
  const sessionKey = useAuth((s) => s.sessionKey);
  /* 메모 고르기 중 탭바 숨김 (옛 보드가 store/ui 로 알려 줌) */
  const hidden = useUI((s) => s.tabBarHidden);
  if (status !== 'signedIn') return <Redirect href="/intro" />;
  return (
    <View style={{ flex: 1 }}>
      <Tabs
        key={sessionKey}
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
        <Tabs.Screen name="report" options={{ href: null }} />
      </Tabs>
      <Mini hidden={hidden} />
      <TabToast hidden={hidden} />
      <CoachDriver />
    </View>
  );
}

/**
 * 공통 안내 (store/ui showToast) — 탭 위 16 자리 새 UI 스낵바.
 * 상세 화면((detail))에서 안내를 띄우고 뒤로 오면(예: 체크리스트 완료) 상세 쪽 안내가 같이 사라지므로 탭 쪽에서도 보여 줌.
 */
function TabToast({ hidden }: { hidden: boolean }) {
  const toast = useUI((s) => s.toast);
  const insets = useSafeAreaInsets();
  const bottom = (hidden ? 0 : 1 + 65 + Math.max(size.tabBarPadBottom, insets.bottom)) + 16;
  return <AppSnackbar visible={!!toast} message={toast?.message ?? ''} style={{ position: 'absolute', left: 12, right: 12, bottom }} />;
}

/**
 * 사용법 안내 화면 이동 (원본 앱: 첫 카드 홈 → ①②③ 메모 화면(memo.html: 보드 + 버튼 · 메모 상세 AI 탭) → ④ 스튜디오 탭 → 끝나면 홈)
 * 대상 종목·메모는 원본처럼 SK하이닉스 · 첫 AI 연결 메모.
 */
function CoachDriver() {
  const router = useRouter();
  const pathname = usePathname();
  const step = useCoach((s) => s.step);
  const was = useRef<number | null>(null);
  useEffect(() => {
    const prev = was.current;
    was.current = step;
    if (step === prev) return;
    const inMemo = pathname.startsWith('/memo/');
    if (step == null || step === -1) {
      /* 첫 카드는 홈에서 (원본 owner(-1) = home) · 끝나도 홈 */
      if (prev == null && step == null) return;
      if (inMemo) router.back();
      if (pathname !== '/') router.navigate('/');
      return;
    }
    if (step === 0) {
      if (inMemo) router.back();
      router.navigate({ pathname: '/stocks/[code]', params: { code: '000660' } });
    } else if (step === 1 || step === 2) {
      if (!inMemo) router.push({ pathname: '/memo/[id]', params: { id: 'm1', tab: 'ai' } });
    } else {
      if (inMemo) router.back();
      router.navigate('/studio');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);
  return null;
}

/* ⑧-8b 미니 플레이어: 탭 바 위 10 (원본 .mini bottom 88). 탭을 바꿔도 남고, 위로 쌓이는 화면이 덮으면 가려짐 */
function Mini({ hidden }: { hidden: boolean }) {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const p = useStudioPlayer();
  const item = p.made.find((m) => m.id === p.cur);
  const ep = epOf(item);
  const ch = ep.chapters[chapterAt(p.t, ep)][1].split(' ·')[0];
  return (
    <AppMiniPlayer
      visible={p.mini && !!item && !hidden}
      bottom={1 + 65 + Math.max(size.tabBarPadBottom, insets.bottom) + 10}
      title={item?.title ?? ''}
      sub={`${ch} · ${fmt(p.t)} / ${fmt(ep.dur)}`}
      progress={p.t / ep.dur}
      playing={p.playing}
      onOpen={() => router.push('/studio-player')}
      onToggle={p.toggle}
      onClose={p.closeMini}
    />
  );
}
