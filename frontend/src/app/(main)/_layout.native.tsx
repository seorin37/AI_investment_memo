import React, { useEffect, useRef } from 'react';
import { View } from 'react-native';
import { Redirect, Tabs, usePathname, useRouter } from 'expo-router';
import { useCoach } from '@/store/coach';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth } from '@/store/auth';
import { MINI_GAP, MINI_H, MiniBar, useMiniOn } from '@/ui/screens/studio/app/MiniBar';
import { useBottomBar } from '@/ui/shared/app/BottomBar';
import { size } from '@/ui/theme';
import { useGenJobs } from '@/store/genJobs';
import { useGenRestore } from '@/ui/screens/studio/genRuns';
import { useUI } from '@/store/ui';
import { useStudioItemsSync } from '@/ui/screens/studio/studioItems';
import { BottomTabBar } from '@/ui/layout/app/BottomTabBar';
import { AppSnackbar } from '@/ui/shared/Snackbar';
import { useUpdatesUnread } from '@/ui/screens/updates/app/useAppUpdates';
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
  useGenRestore();
  const studioDot = useGenJobs((s) => s.dot);
  /* 업데이트 탭 배지: 업데이트 화면 '읽지 않은 소식 N건'과 같은 수 (수정 76) */
  const updatesUnread = useUpdatesUnread();
  /* 크레딧을 다 썼고 AI 연결 메모가 남아 있으면 '충전 · 업그레이드 · 모두 끄기' 한 번 묻기 (2026-11-24) */
  useAiOffPrompt();
  /* 로그인한 채 다른 사용자로 바뀌면(A → B) 커짐 → 탭을 다시 마운트해 열린 화면을 새 사용자 값으로 (store/auth sessionKey) */
  const sessionKey = useAuth((s) => s.sessionKey);
  /* 메모 고르기 중 탭바 숨김 (옛 보드가 store/ui 로 알려 줌) */
  const hidden = useUI((s) => s.tabBarHidden);
  const miniBottom = useMiniBottom(hidden);
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
            badges={{ updates: updatesUnread }}
            dots={{ studio: studioDot }}
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
      <MiniBar bottom={miniBottom} />
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
  const mini = useMiniBottom(hidden);
  const bottom = useMiniOn() ? mini + MINI_H + MINI_GAP : (hidden ? 0 : 1 + 65 + Math.max(size.tabBarPadBottom, insets.bottom)) + 16;
  const action = toast?.action && {
    label: toast.action.label,
    onPress: () => {
      useUI.setState({ toast: null });
      toast.action?.onPress();
    },
  };
  return <AppSnackbar visible={!!toast} message={toast?.message ?? ''} action={action} style={{ position: 'absolute', left: 12, right: 12, bottom }} />;
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

/* 미니 플레이어: 탭 바 위 10 (원본 .mini bottom 88). 고르기처럼 탭 바를 가리는 때는 그 막대 위 8 (막대가 없으면 바닥 10) */
function useMiniBottom(hidden: boolean) {
  const insets = useSafeAreaInsets();
  const bar = useBottomBar((s) => s.bar);
  if (!hidden) return 1 + 65 + Math.max(size.tabBarPadBottom, insets.bottom) + 10;
  return bar ? bar.top + MINI_GAP : insets.bottom + 10;
}
