import React, { useMemo, useState } from 'react';
import { Image, Platform, Pressable, ScrollView, TextInput, View } from 'react-native';
import { usePathname, useRouter, type Href } from 'expo-router';
import { env } from '@/config/env';
import { Icon, type IconName } from '@/components/icons/Icon';
import { Avatar, Hoverable, IconButton } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useJournal, useMyStocks, useStockSearch } from '@/hooks/queries';
import { useAuth } from '@/store/auth';
import { useUI } from '@/store/ui';
import { colors, fonts, layout, shadow } from '@/theme/tokens';

/** Main Sidebar — 시안 그대로: 로고 · 검색 · 홈/최신 업데이트/투자 기록 · 내 종목(보유/관심) · 휴지통 · 설정 및 지원 · 프로필 */
export function Sidebar({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const router = useRouter();
  const pathname = usePathname();
  const user = useAuth((s) => s.user);
  const signOut = useAuth((s) => s.signOut);
  const { toggleSidebar, openModal } = useUI();
  const { data: stocks = [], isError: stocksFailed, error: stocksError } = useMyStocks();
  const [open, setOpen] = useState({ mine: true, holding: true, watching: true });
  const [supportOpen, setSupportOpen] = useState(false);

  const go = (href: Href) => {
    router.navigate(href);
    onNavigate?.();
  };

  const holding = stocks.filter((s) => s.status === 'holding');
  const watching = stocks.filter((s) => s.status === 'watching');
  const width = collapsed ? layout.sidebarCollapsed : layout.sidebarWidth;

  return (
    <View style={{ width, height: '100%', backgroundColor: colors.surface, borderRightWidth: 1, borderRightColor: '#F1F1F3', zIndex: 20 }}>
      {/* 로고 + 접기 */}
      <View style={{ height: 80, flexDirection: collapsed ? 'column' : 'row', alignItems: 'center', justifyContent: collapsed ? 'center' : 'space-between', paddingHorizontal: collapsed ? 0 : 16, paddingTop: 8, gap: collapsed ? 6 : 0 }}>
        <Pressable onPress={() => go('/')} accessibilityLabel="홈으로">
          {collapsed ? (
            <Image source={require('../../../assets/images/logo-round.png')} style={{ width: 34, height: 34 }} />
          ) : (
            <Image source={require('../../../assets/images/logo-wordmark.png')} style={{ width: 114, height: 38 }} resizeMode="contain" />
          )}
        </Pressable>
        {!onNavigate && <IconButton name="panelLeft" label={collapsed ? '사이드바 펼치기' : '사이드바 접기'} onPress={toggleSidebar} color="#5F6672" size={20} />}
      </View>

      {!collapsed && <GlobalSearch onNavigate={onNavigate} />}

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: collapsed ? 12 : 16, paddingTop: collapsed ? 8 : 24, gap: 8 }} showsVerticalScrollIndicator={false}>
        <NavItem icon="home" label="홈" active={pathname === '/'} collapsed={collapsed} onPress={() => go('/')} />
        <NavItem icon="refresh" label="최신 업데이트" active={pathname.startsWith('/updates')} collapsed={collapsed} onPress={() => go('/updates')} />
        <NavItem icon="fileText" label="투자 기록" active={pathname.startsWith('/journal')} collapsed={collapsed} onPress={() => go('/journal')} />
        <NavItem
          icon="briefcase"
          label="내 종목"
          collapsed={collapsed}
          onPress={() => (collapsed ? toggleSidebar() : setOpen((o) => ({ ...o, mine: !o.mine })))}
          right={
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <IconButton name="plus" label="종목 추가" onPress={() => openModal({ type: 'addStock' })} size={16} color={colors.text} box={24} />
              <Icon name={open.mine ? 'chevronUp' : 'chevronDown'} size={16} color="#5F6672" />
            </View>
          }
        />
        {!collapsed && open.mine && (
          <View style={{ gap: 8 }}>
            {stocksFailed && <Hint text={stocksError instanceof Error ? stocksError.message : '내 종목을 불러오지 못했어요'} />}
            <Group label="보유" open={open.holding} onToggle={() => setOpen((o) => ({ ...o, holding: !o.holding }))} />
            {open.holding &&
              holding.map((s) => <StockItem key={s.code} name={s.name} active={pathname === `/stocks/${s.code}`} onPress={() => go(`/stocks/${s.code}`)} />)}
            {open.holding && holding.length === 0 && <Hint text="보유 종목이 없어요" />}
            <Group label="관심" open={open.watching} onToggle={() => setOpen((o) => ({ ...o, watching: !o.watching }))} />
            {open.watching &&
              watching.map((s) => <StockItem key={s.code} name={s.name} active={pathname === `/stocks/${s.code}`} onPress={() => go(`/stocks/${s.code}`)} />)}
            {open.watching && watching.length === 0 && <Hint text="관심 종목을 추가해 보세요" />}
          </View>
        )}
      </ScrollView>

      {/* 하단 */}
      <View style={{ paddingHorizontal: collapsed ? 12 : 16, gap: 8, paddingBottom: 8, zIndex: 30 }}>
        <NavItem icon="trash" label="휴지통" collapsed={collapsed} onPress={() => openModal({ type: 'trash' })} />
        <View style={{ zIndex: 40 }}>
          <NavItem
            icon="settings"
            label="설정 및 지원"
            collapsed={collapsed}
            active={supportOpen}
            neutralActive
            onPress={() => setSupportOpen((v) => !v)}
            right={supportOpen ? <Icon name="chevronRight" size={16} color={colors.textSub} /> : undefined}
          />
          {supportOpen && (
            <>
              {Platform.OS === 'web' && <Pressable onPress={() => setSupportOpen(false)} style={{ position: 'fixed' as 'absolute', top: 0, left: 0, right: 0, bottom: 0 } as object} />}
              <View style={{ position: 'absolute', left: collapsed ? 64 : 234, bottom: -6, width: 192, backgroundColor: colors.surface, borderRadius: 12, padding: 8, borderWidth: 1, borderColor: '#F0F1F3', ...shadow.pop }}>
                {(
                  [
                    { icon: 'settings', label: '설정', run: () => openModal({ type: 'settings' }) },
                    { icon: 'edit', label: '피드백', run: () => openModal({ type: 'feedback' }) },
                    { icon: 'helpSquare', label: '도움말', run: () => go('/help') },
                  ] as { icon: IconName; label: string; run: () => void }[]
                ).map((m) => (
                  <Hoverable
                    key={m.label}
                    onPress={() => {
                      setSupportOpen(false);
                      m.run();
                    }}
                    style={{ height: 44, flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, borderRadius: 8 }}
                    hoverStyle={{ backgroundColor: '#F6F6F8' }}
                  >
                    <Icon name={m.icon} size={18} color={colors.textBody} />
                    <T size={15}>{m.label}</T>
                  </Hoverable>
                ))}
              </View>
            </>
          )}
        </View>
        {env.useMock && !collapsed && (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingTop: 2 }}>
            <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: '#F5A524' }} />
            <T size={11} color={colors.textMuted}>
              {env.useRealStocks ? '종목 API만 실서버 연결 중' : '목업 데이터로 실행 중'}
            </T>
          </View>
        )}
        <View style={{ height: 1, backgroundColor: '#F3F3F5', marginTop: 4 }} />
        <View style={{ flexDirection: collapsed ? 'column' : 'row', alignItems: 'center', paddingVertical: 12, gap: 12 }}>
          <Pressable onPress={() => openModal({ type: 'settings', section: 'profile' })} accessibilityLabel="내 프로필">
            <Avatar name={user?.name ?? '?'} url={user?.avatar_url} size={collapsed ? 40 : 48} />
          </Pressable>
          {!collapsed && (
            <View style={{ flex: 1 }}>
              <T size={16} weight="medium">
                {user?.name}
              </T>
              <T size={12} color={colors.textMuted}>
                {user?.bio}
              </T>
            </View>
          )}
          <IconButton name="logout" label="로그아웃" onPress={() => void signOut()} color="#3A3F47" size={18} />
        </View>
      </View>
    </View>
  );
}

function NavItem({
  icon,
  label,
  active,
  collapsed,
  onPress,
  right,
  neutralActive,
}: {
  icon: IconName;
  label: string;
  active?: boolean;
  collapsed?: boolean;
  onPress: () => void;
  right?: React.ReactNode;
  neutralActive?: boolean;
}) {
  const activeBg = neutralActive ? '#F4F4F6' : colors.brandSoft;
  const fg = active && !neutralActive ? colors.brand : '#1C1C1C';
  return (
    <Hoverable
      accessibilityRole="link"
      accessibilityLabel={label}
      accessibilityState={{ selected: active }}
      onPress={onPress}
      style={[
        { height: 40, borderRadius: 8, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, gap: 10 },
        collapsed && { justifyContent: 'center', paddingHorizontal: 0 },
        active && { backgroundColor: activeBg },
      ]}
      hoverStyle={!active && { backgroundColor: '#F7F7F9' }}
    >
      <Icon name={icon} size={20} color={fg} strokeWidth={1.7} />
      {!collapsed && (
        <>
          <T size={16} weight={active && !neutralActive ? 'semibold' : 'regular'} color={fg} style={{ flex: 1 }} lh={1.2}>
            {label}
          </T>
          {right}
        </>
      )}
    </Hoverable>
  );
}

function Group({ label, open, onToggle }: { label: string; open: boolean; onToggle: () => void }) {
  return (
    <Hoverable onPress={onToggle} style={{ height: 40, flexDirection: 'row', alignItems: 'center', paddingLeft: 36, paddingRight: 12, borderRadius: 8 }} hoverStyle={{ backgroundColor: '#F7F7F9' }}>
      <T size={16} style={{ flex: 1 }} lh={1.2}>
        {label}
      </T>
      <Icon name={open ? 'chevronUp' : 'chevronDown'} size={16} color="#5F6672" />
    </Hoverable>
  );
}

function StockItem({ name, active, onPress }: { name: string; active: boolean; onPress: () => void }) {
  return (
    <Hoverable
      onPress={onPress}
      style={[{ height: 40, justifyContent: 'center', paddingLeft: 56, borderRadius: 8 }, active && { backgroundColor: colors.brandSoft }]}
      hoverStyle={!active && { backgroundColor: '#F7F7F9' }}
    >
      <T size={16} weight={active ? 'semibold' : 'regular'} color={active ? colors.brand : '#1C1C1C'} numberOfLines={1} lh={1.2}>
        {name}
      </T>
    </Hoverable>
  );
}

function Hint({ text }: { text: string }) {
  return (
    <T size={12} color={colors.textMuted} style={{ paddingLeft: 56 }}>
      {text}
    </T>
  );
}

/** 사이드바 검색: 내 종목 · 전체 종목 · 투자 기록 */
function GlobalSearch({ onNavigate }: { onNavigate?: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState('');
  const [focused, setFocused] = useState(false);
  const { data: mine = [] } = useMyStocks();
  const { data: found = [] } = useStockSearch(q);
  const { data: journal = [] } = useJournal();

  const results = useMemo(() => {
    const k = q.trim().toLowerCase();
    if (!k) return [];
    const my = mine.filter((s) => s.name.toLowerCase().includes(k) || s.code.includes(k)).map((s) => ({ key: `s${s.code}`, title: s.name, meta: `내 종목 · ${s.code}`, href: `/stocks/${s.code}` as Href }));
    const others = found
      .filter((f) => !mine.some((m) => m.code === f.code))
      .map((s) => ({ key: `f${s.code}`, title: s.name, meta: `종목 · ${s.code} · ${s.market}`, href: `/stocks/${s.code}` as Href }));
    const js = journal.filter((j) => j.title.toLowerCase().includes(k)).map((j) => ({ key: `j${j.id}`, title: j.title, meta: '투자 기록', href: `/journal?id=${j.id}` as Href }));
    return [...my, ...others, ...js].slice(0, 8);
  }, [q, mine, found, journal]);

  return (
    <View style={{ paddingHorizontal: 16, zIndex: 50 }}>
      <View style={{ height: 40, borderRadius: 8, backgroundColor: colors.surfaceMuted, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, gap: 8 }}>
        <Icon name="search" size={18} color="#8B8B8B" />
        <TextInput
          value={q}
          onChangeText={setQ}
          placeholder="검색"
          placeholderTextColor="#9F9F9F"
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 150)}
          style={[{ flex: 1, minWidth: 0, fontFamily: fonts.regular, fontSize: 15, color: colors.text, paddingVertical: 0 }, Platform.OS === 'web' && ({ outlineStyle: 'none' } as object)]}
          accessibilityLabel="검색"
        />
      </View>
      {focused && q.trim().length > 0 && (
        <View style={{ position: 'absolute', top: 46, left: 16, width: 300, backgroundColor: colors.surface, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 6, ...shadow.pop }}>
          {results.length === 0 ? (
            <T size={13} color={colors.textMuted} style={{ padding: 12 }}>
              검색 결과가 없어요
            </T>
          ) : (
            results.map((r) => (
              <Hoverable
                key={r.key}
                onPress={() => {
                  setQ('');
                  router.navigate(r.href);
                  onNavigate?.();
                }}
                style={{ paddingHorizontal: 10, paddingVertical: 8, borderRadius: 8 }}
                hoverStyle={{ backgroundColor: '#F5F6F8' }}
              >
                <T size={14} weight="medium">
                  {r.title}
                </T>
                <T size={11} color={colors.textMuted}>
                  {r.meta}
                </T>
              </Hoverable>
            ))
          )}
        </View>
      )}
    </View>
  );
}
