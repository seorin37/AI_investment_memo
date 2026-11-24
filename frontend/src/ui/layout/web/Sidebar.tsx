import React, { useEffect, useRef, useState } from 'react';
import { Animated, Image, Platform, Pressable, ScrollView, StyleSheet, View, type ViewStyle } from 'react-native';
import { Text, TextInput } from '@/components/ui/AppText';
import { WebIcon, type WebIconName } from '@/ui/icons/Icon';
import { Collapse } from '@/ui/motion/Collapse';
import { useMotionK } from '@/ui/motion/useMotion';
import { Avatar } from '@/ui/shared/Avatar';
import { CountBadge } from '@/ui/shared/CountBadge';
import { StockLogo } from '@/ui/shared/StockLogo';
import { curve, fpx, shadow, size, webColor } from '@/ui/theme';
import { useShellSize } from './shellSize';
import { SortList } from './sidebarSort.web';
import type { SideKey, SideSearchHit, SidebarProps, SideStock } from './WebShell.types';

/* 원본 shell.tsx: Figma Main Sidebar (Expanded 250 / Collapsed 72). 펼침 크기는 shellSize (1600 미만 224) */
const LABEL = { color: webColor.label };
/* 웹 전용 스타일 (RN 타입에 없는 값) */
const FIXED = { position: 'fixed' } as unknown as ViewStyle;
const NO_OUTLINE = { outlineStyle: 'none' } as unknown as ViewStyle;

type HoverState = { pressed: boolean; hovered?: boolean };

function Row({ icon, label, on, onPress, w, children }: { icon?: WebIconName; label: string; on?: boolean; onPress?: () => void; w?: number; children?: React.ReactNode }) {
  const z = useShellSize();
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={({ hovered }: HoverState) => [st.row, { width: w ?? z.sideInner, height: z.rowH, backgroundColor: on ? webColor.selBg : hovered ? webColor.hover : webColor.surface }]}>
      {icon ? <WebIcon name={icon} size={z.icon} color={on ? webColor.selInk : webColor.icon} /> : null}
      <Text style={[LABEL, z.menuText, on && st.on]} numberOfLines={1}>
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
  const z = useShellSize();
  const [hover, setHover] = useState(false);
  return (
    <View style={[st.stockWrap, { width: z.stockRow }]} onPointerEnter={() => setHover(true)} onPointerLeave={() => setHover(false)}>
      <Pressable onPress={onOpen} accessibilityRole="button" accessibilityLabel={s.name} style={[st.stock, { width: z.stockRow, height: z.rowH, backgroundColor: lifted ? '#FFFFFF' : on ? webColor.selBg : hover ? webColor.hover : 'transparent' }]}>
        <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={z.logo} variant="webSide" />
        <Text style={[LABEL, z.menuText, st.shrink, on && st.on]} numberOfLines={1}>
          {s.name}
        </Text>
      </Pressable>
      {hover && !lifted ? (
        <Pressable onPress={(e) => {
          const ne = e.nativeEvent as unknown as { pageX: number; pageY: number };
          onMenu({ x: ne.pageX - 12, y: ne.pageY + 14 });
        }} accessibilityRole="button" accessibilityLabel={`${s.name} 메뉴`} style={({ hovered }: HoverState) => [st.stockMenu, { top: z.stockMenuTop }, hovered && { backgroundColor: webColor.menuHover }]}>
          <WebIcon name="dotsH" size={14} color={webColor.sub2} />
        </Pressable>
      ) : null}
    </View>
  );
}

const isStock = (cur: SideKey, code: string) => typeof cur === 'object' && cur !== null && cur.stock === code;

/** 웹 사이드바 (펼침 250 · 접힘 72). 종목 순서 끌기 · 우클릭 메뉴 = ⑥ (sidebarSort.web) */
export function Sidebar(p: SidebarProps) {
  const z = useShellSize();
  const [fly, setFly] = useState(false);
  const [q, setQ] = useState('');
  const [focus, setFocus] = useState(false);
  /* 검색 결과에서 ↑↓로 고른 줄 (원본 shell.tsx sel) */
  const [sel, setSel] = useState(0);
  /* 드롭다운 항목을 누르는 중 — 입력칸 포커스가 빠져도(blur) 드롭다운을 닫지 않음 (원본 onMouseDown preventDefault 와 같은 효과, 웹·앱 공통) */
  const picking = useRef(false);
  const typing = useRef(false);
  const pickIn = () => {
    picking.current = true;
  };
  /* 누르다 다른 데서 뗐으면(onPress 없음) 다음 틈에 정리: 입력칸에 포커스가 없으면 닫기 */
  const pickOut = () =>
    setTimeout(() => {
      if (!picking.current) return;
      picking.current = false;
      if (!typing.current) setFocus(false);
    }, 0);
  /* 항목을 골랐으면 고르는 중 표시를 끄고 드롭다운 닫기 */
  const picked = () => {
    picking.current = false;
    setFocus(false);
  };
  const [open, setOpen] = useState({ mine: true, holding: true, watching: true });
  const homeOn = p.current === 'home';
  const hits: SideSearchHit[] = q.trim() ? p.onSearch(q.trim()) : [];
  const pickHit = (h: SideSearchHit | undefined) => {
    if (!h) return;
    p.onPickSearch(h);
    setQ('');
    setSel(0);
  };

  const support = (
    <View style={st.rel}>
      {p.open ? <Row icon="settings" label="설정 및 지원" on={fly} onPress={() => setFly(!fly)} /> : <RailBtn icon="settings" label="설정 및 지원" on={fly} onPress={() => setFly(!fly)} />}
      {fly ? (
        <>
          <Pressable style={[StyleSheet.absoluteFill, FIXED, { zIndex: 30 }]} onPress={() => setFly(false)} accessibilityLabel="닫기" />
          <View style={[st.fly, { left: p.open ? z.flyLeft : 56 }]}>
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
    <View style={[st.nav, st.navOpen, { width: z.sidebar }]} accessibilityRole="menu" accessibilityLabel="메모스 메뉴">
      {/* 위 · 고정 */}
      {/* zIndex 2: 검색 드롭다운이 아래 '내 종목' 블록(st.mid) 위로 (RN-web 은 View 마다 z-index 0 이라 블록끼리 순서를 정해 줘야 함) */}
      <View style={[st.gap24, { zIndex: 2 }]}>
        <View style={st.head}>
          <Pressable onPress={() => p.onNavigate('home')} accessibilityRole="button" accessibilityLabel="홈으로" style={st.wordmark}>
            <Image source={require('../../icons/wordmark-web.png')} style={st.wordmarkImg} resizeMode="stretch" />
          </Pressable>
          <View style={[st.bellAt, { left: z.bellLeft }]}>
            <Bell unread={p.unreadNotifs} onPress={p.onBell} />
          </View>
          <Pressable onPress={p.onToggle} accessibilityRole="button" accessibilityLabel="사이드바 접기" style={({ hovered }: HoverState) => [st.fold, { left: z.foldLeft }, hovered && { backgroundColor: webColor.hover }]}>
            <WebIcon name="panel" size={24} color={webColor.iconSub} />
          </Pressable>
        </View>
        <View style={[st.rel, { zIndex: 40 }]}>
          <View style={[st.search, { width: z.sideInner, height: z.rowH, paddingVertical: z.searchPadY }]}>
            <WebIcon name="search" size={z.icon} />
            <TextInput
              value={q}
              onChangeText={(v) => {
                setQ(v);
                setSel(0);
              }}
              onFocus={() => {
                typing.current = true;
                setFocus(true);
              }}
              onBlur={() => {
                typing.current = false;
                if (!picking.current) setTimeout(() => !picking.current && !typing.current && setFocus(false), 150);
              }}
              /* 원본 shell.tsx: ↓↑ 결과 이동 · Enter 고른 결과 열기 · Esc 검색어 지우기 */
              onKeyPress={(e) => {
                const k = e.nativeEvent.key;
                if (k === 'Escape') {
                  setQ('');
                  setSel(0);
                } else if (k === 'ArrowDown' || k === 'ArrowUp') {
                  (e as unknown as { preventDefault?: () => void }).preventDefault?.();
                  setSel((v) => (k === 'ArrowDown' ? Math.min(v + 1, hits.length - 1) : Math.max(v - 1, 0)));
                } else if (k === 'Enter' && q.trim()) {
                  /* 한글 조합 중 Enter(글자 확정)는 무시 — 확정 뒤 한 번 더 눌러야 열림 */
                  const ne = e.nativeEvent as unknown as { isComposing?: boolean; keyCode?: number };
                  if (ne.isComposing || ne.keyCode === 229) return;
                  pickHit(hits[sel]);
                }
              }}
              placeholder="검색"
              placeholderTextColor={webColor.groupLabel}
              style={[st.searchInput, z.menuText, Platform.OS === 'web' && NO_OUTLINE]}
              accessibilityLabel="검색"
            />
          </View>
          {!q.trim() && focus ? (
            <View style={[st.drop, { top: z.dropTop, width: z.sideInner }]}>
              <Text style={st.dropHead}>최근 찾은 종목</Text>
              <View style={st.recent}>
                {p.recentSearches.map((r) => (
                  <Pressable key={r} onPressIn={pickIn} onPressOut={pickOut} onPress={() => { picked(); p.onPickRecent(r); }} style={({ hovered }: HoverState) => [st.recentChip, hovered && { backgroundColor: webColor.chipHover }]}>
                    <Text style={st.recentText}>{r}</Text>
                  </Pressable>
                ))}
              </View>
              <Text style={[st.dropHead, st.dropHead2]}>많이 찾는 종목</Text>
              {p.popular.map((c) => (
                <Pressable key={c.stock_code} onPressIn={pickIn} onPressOut={pickOut} onPress={() => { picked(); p.onPickPopular(c.stock_code); }} style={({ hovered }: HoverState) => [st.pop, hovered && { backgroundColor: webColor.row }]}>
                  <Text style={st.popName}>{c.name}</Text>
                  <Text style={st.popSub}>{c.mine ? '내 종목' : '추가'}</Text>
                </Pressable>
              ))}
              <Text style={st.dropFoot}>종목·메모·기록을 한 번에 찾아요</Text>
            </View>
          ) : null}
          {q.trim() ? (
            <View style={[st.drop, { top: z.dropTop, width: z.sideInner }]}>
              {hits.length === 0 ? (
                <View style={st.none}>
                  <Text style={st.noneT}>찾지 못했어요</Text>
                  <Text style={st.noneB}>종목명·6자리 코드, 메모·기록 글자로 다시 찾아보세요</Text>
                </View>
              ) : (
                hits.map((h, i) => (
                  <Pressable
                    key={h.key}
                    onPressIn={pickIn}
                    onPressOut={pickOut}
                    onHoverIn={() => setSel(i)}
                    onPress={() => {
                      picked();
                      pickHit(h);
                    }}
                    /* 고른 줄(↑↓ 또는 마우스) = 배경 · 굵게 (원본 sel === i) */
                    style={[st.hit, sel === i && { backgroundColor: webColor.active }]}
                  >
                    {() => (
                      <>
                        <Text style={[st.hitT, { fontWeight: sel === i ? '700' : '500' }]} numberOfLines={1}>
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
        <View style={[st.mineHead, { height: z.rowH }]}>
          <Row icon="stocks" label="내 종목" w={z.mineRow} on={p.current === 'mine'} onPress={() => p.onNavigate('mine')} />
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
                  <Pressable onPress={() => setOpen((o) => ({ ...o, [g.key]: !o[g.key] }))} accessibilityRole="button" accessibilityLabel={`${g.label} 접기`} style={({ hovered }: HoverState) => [st.group, { width: z.sideInner, height: z.rowH, backgroundColor: hovered ? webColor.hover : webColor.surface }]}>
                    <Text style={st.groupT}>{g.label}</Text>
                    <View style={[st.groupChev, { left: z.groupChevLeft, top: z.groupChevTop }]}>
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

      {/* 아래 · 고정. 설정 메뉴가 열렸을 때만 위로(3): 화면 덮개가 위쪽 블록(2)까지 덮어 바깥을 누르면 메뉴만 닫히게 */}
      <View style={[st.gap20, fly && { zIndex: 3 }]}>
        <View style={st.gap8}>
          <Row icon="trash" label="휴지통" onPress={p.onTrash} />
          {support}
        </View>
        <View style={[st.divider, { width: z.sideInner }]} />
        <View style={[st.profile, { width: z.sideInner }]}>
          <Pressable onPress={p.onProfile} accessibilityRole="button" accessibilityLabel="내 프로필" style={st.profileBtn}>
            <Avatar name={p.profile.name} photoUrl={p.profile.photoUrl} size={z.avatar} fontSize={z.avatarText} variant="web" />
            <View style={st.profileText}>
              <Text style={[LABEL, z.menuText, { maxWidth: z.profileText }]} numberOfLines={1}>
                {p.profile.name}
              </Text>
              <Text style={[st.job, { maxWidth: z.profileText }]} numberOfLines={1}>
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
  navOpen: { gap: 8 },
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
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 8, paddingHorizontal: 12 },
  rail: { width: 40, height: 40, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  railSearch: { width: 40, height: 40, borderRadius: 8, backgroundColor: webColor.hover, alignItems: 'center', justifyContent: 'center' },
  railMid: { flex: 1, minHeight: 0, paddingTop: 8 },
  railDivider: { height: 1, width: 40, backgroundColor: webColor.hover },
  head: { height: 40, position: 'relative' },
  wordmark: { position: 'absolute', left: 0, top: -16, width: 117, height: 72 },
  wordmarkImg: { width: 117, height: 72 },
  bellAt: { position: 'absolute', top: 4 },
  bellBadge: { position: 'absolute', right: -4, top: -4 },
  fold: { position: 'absolute', top: 8, width: 24, height: 24, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  search: { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 8, backgroundColor: webColor.hover, paddingHorizontal: 12 },
  searchInput: { flex: 1, color: webColor.label, padding: 0 },
  drop: { position: 'absolute', left: 0, borderRadius: 12, borderWidth: 1, borderColor: webColor.line2, backgroundColor: webColor.surface, padding: 6, ...shadow.drop },
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
  mineHead: { flexDirection: 'row', alignItems: 'center' },
  plus: { height: 32, width: 28, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  mineChev: { marginLeft: 4, height: 32, width: 28, alignItems: 'center', justifyContent: 'center' },
  group: { position: 'relative', flexDirection: 'row', alignItems: 'center', borderRadius: 8, paddingLeft: 40 },
  groupT: { ...fpx(13, 20), fontWeight: '500', color: webColor.groupLabel },
  groupChev: { position: 'absolute', height: 32, width: 28, alignItems: 'center', justifyContent: 'center' },
  listWrap: { flexDirection: 'row', gap: 3, paddingLeft: 44 },
  listLine: { width: 1, backgroundColor: webColor.line },
  stockWrap: { borderRadius: 8 },
  stock: { flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 8, paddingLeft: 8, paddingRight: 12 },
  stockMenu: { position: 'absolute', right: 4, width: 24, height: 24, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  empty: { ...fpx(13, 20), color: webColor.mute2, paddingBottom: 4, paddingLeft: 44 },
  fly: { position: 'absolute', bottom: 0, zIndex: 40, width: 192, gap: 4, borderRadius: 8, backgroundColor: webColor.surface, paddingHorizontal: 8, paddingVertical: 12, ...shadow.menu },
  divider: { height: 1, backgroundColor: webColor.hover },
  profile: { height: 48, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingRight: 4 },
  profileBtn: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  profileText: { minWidth: 0, gap: 4 },
  job: { ...fpx(13, 20), color: webColor.sub },
  logout: { width: 18, height: 18, alignItems: 'center', justifyContent: 'center' },
});
