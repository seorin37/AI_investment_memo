import React, { useEffect, useState } from 'react';
import { Animated, Image, Platform, Pressable, ScrollView, StyleSheet, View, type ViewStyle } from 'react-native';
import { Text, TextInput } from '@/components/ui/AppText';
import { WebIcon, type WebIconName } from '@/ui/icons/Icon';
import { Collapse } from '@/ui/motion/Collapse';
import { useMotionK } from '@/ui/motion/useMotion';
import { Avatar } from '@/ui/shared/Avatar';
import { CountBadge } from '@/ui/shared/CountBadge';
import { StockLogo } from '@/ui/shared/StockLogo';
import { curve, fpx, shadow, size, webColor } from '@/ui/theme';
import { SortList } from './sidebarSort.web';
import type { SideKey, SideSearchHit, SidebarProps, SideStock } from './WebShell.types';

/* 원본 shell.tsx: Figma Main Sidebar (Expanded 250 / Collapsed 72) — 위치·크기 그대로 */
const LABEL = { ...fpx(17, 26), color: webColor.label };
/* 웹 전용 스타일 (RN 타입에 없는 값) */
const FIXED = { position: 'fixed' } as unknown as ViewStyle;
const NO_OUTLINE = { outlineStyle: 'none' } as unknown as ViewStyle;

type HoverState = { pressed: boolean; hovered?: boolean };

function Row({ icon, label, on, onPress, w = size.sideInner, children }: { icon?: WebIconName; label: string; on?: boolean; onPress?: () => void; w?: number; children?: React.ReactNode }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={({ hovered }: HoverState) => [st.row, { width: w, backgroundColor: on ? webColor.selBg : hovered ? webColor.hover : webColor.surface }]}>
      {icon ? <WebIcon name={icon} size={20} color={on ? webColor.selInk : webColor.icon} /> : null}
      <Text style={[LABEL, on && st.on]} numberOfLines={1}>
        {label}
      </Text>
      {children}
    </Pressable>
  );
}

function RailBtn({ icon, label, on, onPress, plain }: { icon: WebIconName; label: string; on?: boolean; onPress?: () => void; plain?: boolean }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={({ hovered }: HoverState) => [st.rail, { backgroundColor: on ? webColor.selBg : hovered ? webColor.hover : plain ? 'transparent' : webColor.surface }]}>
      <WebIcon name={icon} size={20} color={on ? webColor.selInk : webColor.icon} />
    </Pressable>
  );
}

/** 접기·펼치기 꺾쇠 (원본: transform .25s) */
function Chev({ up }: { up: boolean }) {
  const k = useMotionK();
  const [r] = useState(() => new Animated.Value(up ? 0 : 1));
  useEffect(() => {
    const a = Animated.timing(r, { toValue: up ? 0 : 1, duration: 250 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [up, r, k]);
  return (
    <Animated.View style={{ transform: [{ rotate: r.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '180deg'] }) }] }}>
      <WebIcon name="chevUp" size={16} color={webColor.iconSub} />
    </Animated.View>
  );
}

function Bell({ unread, rail, onPress }: { unread: number; rail?: boolean; onPress: () => void }) {
  const s = rail ? 40 : 32;
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={`알림${unread ? ` ${unread}개` : ''}`} style={({ hovered }: HoverState) => [{ width: s, height: s, borderRadius: 8, alignItems: 'center', justifyContent: 'center', backgroundColor: hovered ? webColor.hover : 'transparent' }]}>
      <WebIcon name="bellLg" size={20} color={webColor.icon} />
      <CountBadge count={unread} style={st.bellBadge} />
    </Pressable>
  );
}

function StockRow({ s, on, lifted, onOpen, onMenu }: { s: SideStock; on: boolean; lifted?: boolean; onOpen: () => void; onMenu: (at: { x: number; y: number }) => void }) {
  const [hover, setHover] = useState(false);
  return (
    <View style={st.stockWrap} onPointerEnter={() => setHover(true)} onPointerLeave={() => setHover(false)}>
      <Pressable onPress={onOpen} accessibilityRole="button" accessibilityLabel={s.name} style={[st.stock, { backgroundColor: lifted ? '#FFFFFF' : on ? webColor.selBg : hover ? webColor.hover : 'transparent' }]}>
        <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={24} radius={7.2} variant="webSide" />
        <Text style={[LABEL, st.shrink, on && st.on]} numberOfLines={1}>
          {s.name}
        </Text>
      </Pressable>
      {hover && !lifted ? (
        <Pressable onPress={(e) => {
          const ne = e.nativeEvent as unknown as { pageX: number; pageY: number };
          onMenu({ x: ne.pageX - 12, y: ne.pageY + 14 });
        }} accessibilityRole="button" accessibilityLabel={`${s.name} 메뉴`} style={({ hovered }: HoverState) => [st.stockMenu, hovered && { backgroundColor: webColor.menuHover }]}>
          <WebIcon name="dotsH" size={14} color={webColor.sub2} />
        </Pressable>
      ) : null}
    </View>
  );
}

const isStock = (cur: SideKey, code: string) => typeof cur === 'object' && cur !== null && cur.stock === code;

/** 웹 사이드바 (펼침 250 · 접힘 72). 종목 순서 끌기 · 우클릭 메뉴 = ⑥ (sidebarSort.web) */
export function Sidebar(p: SidebarProps) {
  const [fly, setFly] = useState(false);
  const [q, setQ] = useState('');
  const [focus, setFocus] = useState(false);
  const [open, setOpen] = useState({ mine: true, holding: true, watching: true });
  const homeOn = p.current === 'home';
  const hits: SideSearchHit[] = q.trim() ? p.onSearch(q.trim()) : [];

  const support = (
    <View style={st.rel}>
      {p.open ? <Row icon="settings" label="설정 및 지원" on={fly} onPress={() => setFly(!fly)} /> : <RailBtn icon="settings" label="설정 및 지원" on={fly} onPress={() => setFly(!fly)} />}
      {fly ? (
        <>
          <Pressable style={[StyleSheet.absoluteFill, FIXED, { zIndex: 30 }]} onPress={() => setFly(false)} accessibilityLabel="닫기" />
          <View style={[st.fly, { left: p.open ? 234 : 56 }]}>
            {(
              [
                ['settings', '설정', p.onSettings],
                ['feedback', '피드백', p.onFeedback],
                ['help', '도움말', p.onHelp],
              ] as const
            ).map(([i, l, f]) => (
              <Row
                key={l}
                icon={i}
                label={l}
                w={176}
                onPress={() => {
                  setFly(false);
                  f();
                }}
              />
            ))}
          </View>
        </>
      ) : null}
    </View>
  );

  if (!p.open)
    return (
      <View style={[st.nav, st.navRail]} accessibilityRole="menu" accessibilityLabel="메뉴 (접힘)">
        <View style={st.gap24}>
          <View style={st.gap8}>
            <RailBtn icon="panelOpen" label="사이드바 펼치기" onPress={p.onToggle} plain />
            <Bell unread={p.unreadNotifs} rail onPress={p.onBell} />
          </View>
          <Pressable onPress={p.onToggle} accessibilityRole="button" accessibilityLabel="검색" style={st.railSearch}>
            <WebIcon name="search" size={20} />
          </Pressable>
          <View style={st.gap8}>
            <RailBtn icon="home" label="홈" on={homeOn} onPress={() => p.onNavigate('home')} />
            <RailBtn icon="updates" label="최신 업데이트" on={p.current === 'updates'} onPress={() => p.onNavigate('updates')} />
            <RailBtn icon="journal" label="투자 기록" on={p.current === 'journal'} onPress={() => p.onNavigate('journal')} />
          </View>
        </View>
        <View style={st.railMid}>
          <RailBtn icon="stocks" label="내 종목" on={p.current === 'mine' || (typeof p.current === 'object' && p.current !== null)} onPress={() => p.onNavigate('mine')} />
        </View>
        <View style={st.gap20}>
          <View style={st.gap8}>
            <RailBtn icon="trash" label="휴지통" onPress={p.onTrash} />
            {support}
          </View>
          <View style={st.railDivider} />
          <Pressable onPress={p.onProfile} accessibilityRole="button" accessibilityLabel="내 프로필">
            <Avatar name={p.profile.name} photoUrl={p.profile.photoUrl} size={40} variant="web" />
          </Pressable>
        </View>
      </View>
    );

  const groups: { key: 'holding' | 'watching'; label: string; list: SideStock[] }[] = [
    { key: 'holding', label: '보유', list: p.stocks.filter((s) => s.status === 'holding') },
    { key: 'watching', label: '관심', list: p.stocks.filter((s) => s.status === 'watching') },
  ];

  return (
    <View style={[st.nav, st.navOpen]} accessibilityRole="menu" accessibilityLabel="메모스 메뉴">
      {/* 위 · 고정 */}
      <View style={st.gap24}>
        <View style={st.head}>
          <Pressable onPress={() => p.onNavigate('home')} accessibilityRole="button" accessibilityLabel="홈으로" style={st.wordmark}>
            <Image source={require('../../icons/wordmark-web.png')} style={st.wordmarkImg} resizeMode="stretch" />
          </Pressable>
          <View style={st.bellAt}>
            <Bell unread={p.unreadNotifs} onPress={p.onBell} />
          </View>
          <Pressable onPress={p.onToggle} accessibilityRole="button" accessibilityLabel="사이드바 접기" style={({ hovered }: HoverState) => [st.fold, hovered && { backgroundColor: webColor.hover }]}>
            <WebIcon name="panel" size={24} color={webColor.iconSub} />
          </Pressable>
        </View>
        <View style={[st.rel, { zIndex: 40 }]}>
          <View style={st.search}>
            <WebIcon name="search" size={20} />
            <TextInput
              value={q}
              onChangeText={setQ}
              onFocus={() => setFocus(true)}
              onBlur={() => setTimeout(() => setFocus(false), 150)}
              placeholder="검색"
              placeholderTextColor={webColor.groupLabel}
              style={[st.searchInput, Platform.OS === 'web' && NO_OUTLINE]}
              accessibilityLabel="검색"
            />
          </View>
          {!q.trim() && focus ? (
            <View style={st.drop}>
              <Text style={st.dropHead}>최근 찾은 종목</Text>
              <View style={st.recent}>
                {p.recentSearches.map((r) => (
                  <Pressable key={r} onPress={() => p.onPickRecent(r)} style={({ hovered }: HoverState) => [st.recentChip, hovered && { backgroundColor: webColor.chipHover }]}>
                    <Text style={st.recentText}>{r}</Text>
                  </Pressable>
                ))}
              </View>
              <Text style={[st.dropHead, st.dropHead2]}>많이 찾는 종목</Text>
              {p.popular.map((c) => (
                <Pressable key={c.stock_code} onPress={() => p.onPickPopular(c.stock_code)} style={({ hovered }: HoverState) => [st.pop, hovered && { backgroundColor: webColor.row }]}>
                  <Text style={st.popName}>{c.name}</Text>
                  <Text style={st.popSub}>{c.mine ? '내 종목' : '추가'}</Text>
                </Pressable>
              ))}
              <Text style={st.dropFoot}>종목·메모·기록을 한 번에 찾아요</Text>
            </View>
          ) : null}
          {q.trim() ? (
            <View style={st.drop}>
              {hits.length === 0 ? (
                <View style={st.none}>
                  <Text style={st.noneT}>찾지 못했어요</Text>
                  <Text style={st.noneB}>종목명·6자리 코드, 메모·기록 글자로 다시 찾아보세요</Text>
                </View>
              ) : (
                hits.map((h) => (
                  <Pressable
                    key={h.key}
                    onPress={() => {
                      p.onPickSearch(h);
                      setQ('');
                    }}
                    style={({ hovered }: HoverState) => [st.hit, hovered && { backgroundColor: webColor.active }]}
                  >
                    {({ hovered }: HoverState) => (
                      <>
                        <Text style={[st.hitT, { fontWeight: hovered ? '700' : '500' }]} numberOfLines={1}>
                          {h.title}
                        </Text>
                        <Text style={st.hitS}>{h.sub}</Text>
                      </>
                    )}
                  </Pressable>
                ))
              )}
            </View>
          ) : null}
        </View>
        <View style={st.gap8}>
          <Row icon="home" label="홈" on={homeOn} onPress={() => p.onNavigate('home')} />
          <Row icon="updates" label="최신 업데이트" on={p.current === 'updates'} onPress={() => p.onNavigate('updates')} />
          <Row icon="journal" label="투자 기록" on={p.current === 'journal'} onPress={() => p.onNavigate('journal')} />
        </View>
      </View>

      {/* 가운데 · 내 종목 */}
      <View style={st.mid}>
        <View style={st.mineHead}>
          <Row icon="stocks" label="내 종목" w={154} on={p.current === 'mine'} onPress={() => p.onNavigate('mine')} />
          <Pressable onPress={p.onAddStock} accessibilityRole="button" accessibilityLabel="종목 추가" style={({ hovered }: HoverState) => [st.plus, hovered && { backgroundColor: webColor.hover }]}>
            <WebIcon name="plus" size={28} height={32} color="#1C1C1C" />
          </Pressable>
          <Pressable onPress={() => setOpen((o) => ({ ...o, mine: !o.mine }))} accessibilityRole="button" accessibilityLabel="내 종목 접기" style={st.mineChev}>
            <Chev up={open.mine} />
          </Pressable>
        </View>
        <ScrollView style={st.flex} showsVerticalScrollIndicator={false}>
          <Collapse open={open.mine}>
            <View style={st.gap12}>
              {groups.map((g) => (
                <View key={g.key} style={st.gap4}>
                  <Pressable onPress={() => setOpen((o) => ({ ...o, [g.key]: !o[g.key] }))} accessibilityRole="button" accessibilityLabel={`${g.label} 접기`} style={({ hovered }: HoverState) => [st.group, { backgroundColor: hovered ? webColor.hover : webColor.surface }]}>
                    <Text style={st.groupT}>{g.label}</Text>
                    <View style={st.groupChev}>
                      <Chev up={open[g.key]} />
                    </View>
                  </Pressable>
                  <Collapse open={open[g.key]}>
                    {g.list.length ? (
                      <View style={st.listWrap}>
                        <View style={st.listLine} />
                        <SortList
                          codes={g.list.map((s) => s.stock_code)}
                          onCommit={p.onReorderStocks}
                          onMenu={p.onStockMenu}
                          renderRow={(code, lifted) => {
                            const s = g.list.find((x) => x.stock_code === code);
                            return s ? <StockRow s={s} lifted={lifted} on={isStock(p.current, code)} onOpen={() => p.onOpenStock(code)} onMenu={(at) => p.onStockMenu(code, at)} /> : null;
                          }}
                        />
                      </View>
                    ) : (
                      <Text style={st.empty}>{g.label} 종목이 없어요</Text>
                    )}
                  </Collapse>
                </View>
              ))}
            </View>
          </Collapse>
        </ScrollView>
      </View>

      {/* 아래 · 고정 */}
      <View style={st.gap20}>
        <View style={st.gap8}>
          <Row icon="trash" label="휴지통" onPress={p.onTrash} />
          {support}
        </View>
        <View style={st.divider} />
        <View style={st.profile}>
          <Pressable onPress={p.onProfile} accessibilityRole="button" accessibilityLabel="내 프로필" style={st.profileBtn}>
            <Avatar name={p.profile.name} photoUrl={p.profile.photoUrl} size={48} fontSize={20} variant="web" />
            <View style={st.profileText}>
              <Text style={[LABEL, st.maxw]} numberOfLines={1}>
                {p.profile.name}
              </Text>
              <Text style={[st.job, st.maxw]} numberOfLines={1}>
                {p.profile.job}
              </Text>
            </View>
          </Pressable>
          <Pressable onPress={p.onLogout} accessibilityRole="button" accessibilityLabel="로그아웃" style={st.logout}>
            <WebIcon name="logout" size={18} color={webColor.icon} />
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  nav: { height: '100%', backgroundColor: webColor.surface, paddingHorizontal: 16, paddingVertical: 24, zIndex: 30 },
  navOpen: { width: size.sidebar, gap: 8 },
  navRail: { width: size.rail, justifyContent: 'space-between' },
  flex: { flex: 1 },
  shrink: { flexShrink: 1 },
  rel: { position: 'relative' },
  abs: { position: 'absolute', left: 0 },
  gap4: { gap: 4 },
  gap8: { gap: 8 },
  gap12: { gap: 12 },
  gap20: { gap: 20 },
  gap24: { gap: 24 },
  on: { fontWeight: '700', color: webColor.selInk },
  row: { height: 40, flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 8, paddingHorizontal: 12 },
  rail: { width: 40, height: 40, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  railSearch: { width: 40, height: 40, borderRadius: 8, backgroundColor: webColor.hover, alignItems: 'center', justifyContent: 'center' },
  railMid: { flex: 1, minHeight: 0, paddingTop: 8 },
  railDivider: { height: 1, width: 40, backgroundColor: webColor.hover },
  head: { height: 40, position: 'relative' },
  wordmark: { position: 'absolute', left: 0, top: -16, width: 117, height: 72 },
  wordmarkImg: { width: 117, height: 72 },
  bellAt: { position: 'absolute', left: 154, top: 4 },
  bellBadge: { position: 'absolute', right: -4, top: -4 },
  fold: { position: 'absolute', left: 194, top: 8, width: 24, height: 24, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  search: { height: 40, width: size.sideInner, flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 8, backgroundColor: webColor.hover, paddingHorizontal: 12, paddingVertical: 10 },
  searchInput: { flex: 1, ...fpx(17, 26), color: webColor.label, padding: 0 },
  drop: { position: 'absolute', left: 0, top: 48, width: size.sideInner, borderRadius: 12, borderWidth: 1, borderColor: webColor.line2, backgroundColor: webColor.surface, padding: 6, ...shadow.drop },
  dropHead: { ...fpx(13, 20), fontWeight: '700', color: webColor.sub2, paddingHorizontal: 10, paddingBottom: 4, paddingTop: 8 },
  dropHead2: { paddingTop: 4 },
  recent: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, paddingHorizontal: 8, paddingBottom: 8 },
  recentChip: { borderRadius: 999, backgroundColor: webColor.chip, paddingHorizontal: 10, paddingVertical: 4 },
  recentText: { ...fpx(13, 20), fontWeight: '500', color: '#333D4B' },
  pop: { height: 36, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderRadius: 10, paddingHorizontal: 10 },
  popName: { ...fpx(14, 21), fontWeight: '500', color: webColor.strong },
  popSub: { ...fpx(13, 20), color: webColor.mute },
  dropFoot: { ...fpx(13, 20), color: webColor.sub2, paddingHorizontal: 10, paddingBottom: 4, paddingTop: 8 },
  none: { paddingHorizontal: 14, paddingVertical: 12 },
  noneT: { ...fpx(13, 20), fontWeight: '700', color: webColor.ink2 },
  noneB: { ...fpx(13, 20), color: webColor.mute },
  hit: { height: 41, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, borderRadius: 10, paddingHorizontal: 14 },
  hitT: { flexShrink: 1, ...fpx(14, 21), color: webColor.strong },
  hitS: { ...fpx(13, 20), color: webColor.mute },
  mid: { flex: 1, minHeight: 0, gap: 12 },
  mineHead: { height: 40, flexDirection: 'row', alignItems: 'center' },
  plus: { height: 32, width: 28, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  mineChev: { marginLeft: 4, height: 32, width: 28, alignItems: 'center', justifyContent: 'center' },
  group: { position: 'relative', height: 40, width: size.sideInner, flexDirection: 'row', alignItems: 'center', borderRadius: 8, paddingLeft: 40 },
  groupT: { ...fpx(13, 20), fontWeight: '500', color: webColor.groupLabel },
  groupChev: { position: 'absolute', left: 186, top: 4, height: 32, width: 28, alignItems: 'center', justifyContent: 'center' },
  listWrap: { flexDirection: 'row', gap: 3, paddingLeft: 44 },
  listLine: { width: 1, backgroundColor: webColor.line },
  stockWrap: { width: 170, borderRadius: 8 },
  stock: { height: 40, width: 170, flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 8, paddingLeft: 8, paddingRight: 12 },
  stockMenu: { position: 'absolute', right: 4, top: 8, width: 24, height: 24, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  empty: { ...fpx(13, 20), color: webColor.mute2, paddingBottom: 4, paddingLeft: 44 },
  fly: { position: 'absolute', bottom: 0, zIndex: 40, width: 192, gap: 4, borderRadius: 8, backgroundColor: webColor.surface, paddingHorizontal: 8, paddingVertical: 12, ...shadow.menu },
  divider: { height: 1, width: size.sideInner, backgroundColor: webColor.hover },
  profile: { height: 48, width: size.sideInner, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingRight: 4 },
  profileBtn: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  profileText: { minWidth: 0, gap: 4 },
  maxw: { maxWidth: 130 },
  job: { ...fpx(13, 20), color: webColor.sub },
  logout: { width: 18, height: 18, alignItems: 'center', justifyContent: 'center' },
});
