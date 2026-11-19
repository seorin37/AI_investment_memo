import React, { useState } from 'react';
import { useWindowDimensions } from 'react-native';
import { Redirect, Stack, usePathname, useRouter } from 'expo-router';
import { useAuth } from '@/store/auth';
import { mockPopular, mockRecentSearches, mockSideProfile, mockSideStocks, mockStudioHead, mockUnreadNotifs } from '@/ui/layout/web/WebShell.mock';
import { WebShell } from '@/ui/layout/web/WebShell';
import type { SideKey, SideSearchHit } from '@/ui/layout/web/WebShell.types';
import { size, webColor } from '@/ui/theme';

/** 주소 → 사이드바에서 고른 곳 */
function sideKeyOf(path: string): SideKey {
  if (path === '/' || path === '/index') return 'home';
  if (path.startsWith('/updates')) return 'updates';
  if (path.startsWith('/journal')) return 'journal';
  const m = /^\/stocks\/([^/]+)/.exec(path);
  if (m) return { stock: m[1] };
  if (path.startsWith('/stocks')) return 'mine';
  return null;
}

/**
 * 웹 로그인 후 영역: UI v2 WebShell (사이드바 250/72 · 가운데 · 스튜디오 열 436/96).
 * 옛 AppShell(components/layout)은 지우지 않고 여기서만 뺌. 탭 안 화면은 아직 옛 화면.
 * 앱(안드로이드·iOS)은 같은 폴더의 _layout.native.tsx.
 * mock 단계: 사이드바·스튜디오 머리 숫자는 WebShell.mock. 알림·휴지통·설정 등 창은 다음 묶음에서 연결.
 */
export default function MainLayout() {
  const status = useAuth((s) => s.status);
  const router = useRouter();
  const pathname = usePathname();
  const { width } = useWindowDimensions();
  const [sideOpen, setSideOpen] = useState(true);
  /* 원본 studio.tsx: 화면 폭 1280 이하면 처음에 접힘 */
  const [studioOpen, setStudioOpen] = useState(() => width > size.studioNarrow);
  const [dark, setDark] = useState(false);
  if (status !== 'signedIn') return <Redirect href="/login" />;

  const openStock = (code: string) => router.navigate({ pathname: '/stocks/[code]', params: { code } });
  const search = (q: string): SideSearchHit[] =>
    mockSideStocks.filter((s) => s.name.includes(q) || s.stock_code.includes(q)).map((s) => ({ key: `s${s.stock_code}`, title: s.name, sub: s.stock_code }));

  return (
    <WebShell
      sidebar={{
        open: sideOpen,
        onToggle: () => setSideOpen((o) => !o),
        current: sideKeyOf(pathname),
        stocks: mockSideStocks,
        profile: mockSideProfile,
        unreadNotifs: mockUnreadNotifs,
        dark,
        recentSearches: mockRecentSearches,
        popular: mockPopular,
        onSearch: search,
        onPickSearch: (h) => openStock(h.key.slice(1)),
        onPickRecent: (name) => {
          const s = mockSideStocks.find((x) => x.name === name);
          if (s) openStock(s.stock_code);
        },
        onPickPopular: (code) => {
          if (mockSideStocks.some((s) => s.stock_code === code)) openStock(code);
        },
        onNavigate: (to) => router.navigate(to === 'home' ? '/' : to === 'mine' ? '/stocks' : `/${to}`),
        onOpenStock: openStock,
        onStockMenu: () => {},
        onAddStock: () => {},
        onBell: () => {},
        onToggleDark: () => setDark((d) => !d),
        onTrash: () => {},
        onSettings: () => {},
        onFeedback: () => {},
        onHelp: () => router.navigate('/help'),
        onProfile: () => {},
        onLogout: () => {},
      }}
      studio={{
        open: studioOpen,
        onToggle: () => setStudioOpen((o) => !o),
        ...mockStudioHead,
        onUsage: () => {},
        onFeature: () => setStudioOpen(true),
      }}
    >
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: webColor.page }, animation: 'none' }} />
    </WebShell>
  );
}
