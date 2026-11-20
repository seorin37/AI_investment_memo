import React, { useState } from 'react';
import { View, useWindowDimensions } from 'react-native';
import { Redirect, Stack, usePathname, useRouter } from 'expo-router';
import { useAuth } from '@/store/auth';
import { mockPopular, mockRecentSearches, mockSideProfile, mockSideStocks, mockStudioHead, mockUnreadNotifs } from '@/ui/layout/web/WebShell.mock';
import { WebShell } from '@/ui/layout/web/WebShell';
import type { SideKey, SideSearchHit, SideStock } from '@/ui/layout/web/WebShell.types';
import { mockMyStocksData } from '@/ui/screens/stocks/MyStocks.mock';
import { WebAddStockDialog } from '@/ui/screens/stocks/web/AddStockDialog';
import { useMyMock } from '@/store/myMock';
import { mockWithdrawCounts } from '@/ui/screens/my/My.mock';
import { WebSettings, type SettingsTab } from '@/ui/screens/my/web/Settings';
import { ConfirmDialog } from '@/ui/shared/ConfirmDialog';
import { ContextMenu } from '@/ui/shared/ContextMenu';
import { WebSnackbar } from '@/ui/shared/Snackbar';
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
  /* ⑥ 사이드바 종목: 순서 끌기 · 우클릭/⋯ 메뉴 · + 종목 추가 (mock: 이 셸 안에서만) */
  const [sideStocks, setSideStocks] = useState<SideStock[]>(mockSideStocks);
  const [smenu, setSmenu] = useState<{ code: string; at: { x: number; y: number } } | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [ask, setAsk] = useState<string | null>(null);
  const [snack, setSnack] = useState<{ msg: string; undo?: () => void; check?: boolean } | null>(null);
  /* ⑨-3a 설정 창(내 프로필) · 사이드바 로그아웃 확인 (mock: 프로필은 화면 상태만) */
  const [settings, setSettings] = useState<SettingsTab | null>(null);
  const [logoutAsk, setLogoutAsk] = useState(false);
  const signOut = useAuth((s) => s.signOut);
  const myProfile = useMyMock((s) => s.profile);
  const setMyProfile = useMyMock((s) => s.setProfile);
  const say = (x: { msg: string; undo?: () => void; check?: boolean }) => {
    setSnack(x);
    setTimeout(() => setSnack((c) => (c === x ? null : c)), 4000);
  };
  const nameOf = (c: string) => sideStocks.find((x) => x.stock_code === c)?.name ?? '';
  const jo = (w: string) => {
    const c = w.charCodeAt(w.length - 1);
    return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? '을' : '를';
  };
  if (status !== 'signedIn') return <Redirect href="/login" />;

  /* 로그아웃: mock 세션을 지우고 로그인으로 replace (로그인 뒤 화면은 위 Redirect 로 다시 못 들어옴) */
  const logout = () => {
    void signOut().finally(() => router.replace('/login'));
  };
  const openStock = (code: string) => router.navigate({ pathname: '/stocks/[code]', params: { code } });
  const search = (q: string): SideSearchHit[] =>
    mockSideStocks.filter((s) => s.name.includes(q) || s.stock_code.includes(q)).map((s) => ({ key: `s${s.stock_code}`, title: s.name, sub: s.stock_code }));

  const cur = smenu ? sideStocks.find((x) => x.stock_code === smenu.code) : undefined;
  return (
    <View style={{ flex: 1 }}>
    <WebShell
      sidebar={{
        open: sideOpen,
        onToggle: () => setSideOpen((o) => !o),
        current: sideKeyOf(pathname),
        stocks: sideStocks,
        /* 설정에서 바꾼 이름·소개를 사이드바 프로필에도 (mock 상태) */
        profile: { ...mockSideProfile, name: myProfile.name, job: myProfile.intro },
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
        onStockMenu: (code, at) => setSmenu({ code, at }),
        onReorderStocks: (codes) =>
          setSideStocks((all) => {
            const inG = new Set(codes);
            let i = 0;
            return all.map((x) => {
              if (!inG.has(x.stock_code)) return x;
              const c = codes[i++];
              return all.find((y) => y.stock_code === c) ?? x;
            });
          }),
        onAddStock: () => setAddOpen(true),
        onBell: () => {},
        onToggleDark: () => setDark((d) => !d),
        onTrash: () => {},
        onSettings: () => setSettings('내 프로필'),
        onFeedback: () => {},
        onHelp: () => router.navigate('/help'),
        onProfile: () => setSettings('내 프로필'),
        onLogout: () => setLogoutAsk(true),
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
    <ContextMenu
      at={smenu?.at ?? null}
      items={
        cur
          ? [
              { label: cur.status === 'holding' ? '관심 종목으로 바꾸기' : '보유 종목으로 바꾸기', icon: 'move', run: () => {
                  const to = cur.status === 'holding' ? 'watching' : 'holding';
                  setSideStocks((all) => all.map((x) => (x.stock_code === cur.stock_code ? { ...x, status: to } : x)));
                  say({ msg: `${cur.name}${jo(cur.name)} ${to === 'holding' ? '보유' : '관심'} 종목으로 바꿨어요`, check: true });
                } },
              { label: '기업정보 보기', icon: 'info', run: () => router.navigate({ pathname: '/stocks/[code]', params: { code: cur.stock_code, tab: 'info' } }) },
              '-',
              { label: '내 종목에서 빼기', icon: 'trash', danger: true, run: () => setAsk(cur.stock_code) },
            ]
          : []
      }
      onClose={() => setSmenu(null)}
    />
    <ConfirmDialog
      variant="web"
      danger
      open={!!ask}
      title="내 종목에서 뺄까요?"
      body="휴지통에서 다시 복원할 수 있어요."
      confirmLabel="빼기"
      onCancel={() => setAsk(null)}
      onConfirm={() => {
        const c = ask;
        setAsk(null);
        if (!c) return;
        const before = sideStocks;
        setSideStocks((all) => all.filter((x) => x.stock_code !== c));
        say({ msg: `${nameOf(c)}${jo(nameOf(c))} 내 종목에서 뺐어요`, undo: () => (setSideStocks(before), setSnack(null)) });
      }}
    />
    <WebAddStockDialog
      open={addOpen}
      mine={mockMyStocksData.stocks.filter((m) => sideStocks.some((x) => x.stock_code === m.stock_code))}
      universe={mockMyStocksData.universe}
      popular={mockMyStocksData.popular}
      onClose={() => setAddOpen(false)}
      onAdd={(code, hold) => {
        const u = mockMyStocksData.universe.find((x) => x.stock_code === code);
        if (!u) return;
        setSideStocks((all) => [...all, { stock_code: u.stock_code, name: u.name, status: hold, logo: u.logo, logo_bg: u.logo_bg, logo_ink: u.logo_ink }]);
        say({ msg: `${u.name}${jo(u.name)} ${hold === 'holding' ? '보유' : '관심'} 종목에 추가했어요`, check: true });
      }}
    />
    <WebSettings
      open={!!settings}
      tab={settings ?? '내 프로필'}
      profile={myProfile}
      counts={mockWithdrawCounts}
      onTab={setSettings}
      onClose={() => setSettings(null)}
      onChangeProfile={({ name, intro }) => {
        if (!name) return say({ msg: '이름은 비워 둘 수 없어요' });
        if (name !== myProfile.name || intro !== myProfile.intro) {
          setMyProfile({ name, intro });
          say({ msg: '프로필을 저장했어요', check: true });
        }
      }}
      onPhoto={() => say({ msg: '사진 올리기는 아직 준비 중이에요' })}
      onPhotoDelete={() => say({ msg: '지울 사진이 없어요' })}
      onLogout={() => { setSettings(null); logout(); }}
      onWithdraw={() => say({ msg: '아직 탈퇴 기능은 연결되지 않았어요 · 데이터는 그대로예요' })}
    />
    <ConfirmDialog
      variant="web"
      danger
      open={logoutAsk}
      title="로그아웃할까요?"
      body="이 기기에서 로그아웃해요."
      confirmLabel="로그아웃"
      onCancel={() => setLogoutAsk(false)}
      onConfirm={() => { setLogoutAsk(false); logout(); }}
    />
    <WebSnackbar visible={!!snack} message={snack?.msg ?? ''} onUndo={snack?.undo} check={snack?.check} style={{ position: 'absolute', bottom: 30, alignSelf: 'center' }} />
    </View>
  );
}
