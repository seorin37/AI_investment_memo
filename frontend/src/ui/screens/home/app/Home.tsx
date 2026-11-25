import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Animated, BackHandler, PanResponder, Pressable, ScrollView, StyleSheet, View, type ScrollViewInstance } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { TAB_BAR_H } from '@/ui/layout/app/TopBar';
import { Text } from '@/components/ui/AppText';
import { GripDots, PlusGlyph, SlidersGlyph, WIDGET_META, WidgetGlyph } from '@/ui/icons/HomeGlyphs';
import { Reveal } from '@/ui/motion/Reveal';
import { useMotionK } from '@/ui/motion/useMotion';
import { ConfirmDialog } from '@/ui/shared/ConfirmDialog';
import { NudgePill } from '@/ui/shared/NudgePill';
import { Sheet } from '@/ui/shared/Sheet';
import { AppSnackbar } from '@/ui/shared/Snackbar';
import { appColor, curve, ft } from '@/ui/theme';
import type { AppHomeProps, HomeWidget } from '../Home.types';
import { HomeSearch } from './HomeSearch';
import { CheckWidget, HeroCard, MarketFail, MarketWidget, NewsWidget, UpdatesWidget, WidgetShell } from './HomeWidgets';
import { useNudge } from '@/store/nudge';

const ALL: HomeWidget[] = ['market', 'updates', 'news', 'check'];
const DEFAULT_W: HomeWidget[] = ['market', 'updates', 'news'];
type Snack = { msg: string; undo?: () => void; key: number };
/** 애니메이션 다시 시작용 번호 */
let seq = 0;
const nextKey = () => ++seq;
type Shift = Record<HomeWidget, Animated.Value>;

/**
 * 앱 홈 (원본 home.html · 11.17 웹 통일)
 * 인사 카드(고정) · 시장 한눈에 보기 · 업데이트 · 뉴스 · (체크리스트) · 홈 편집 버튼 · 넛지
 * 홈 편집: 위젯을 꾹 누르거나 [홈 편집] → 탭바가 내려가고 보라 테두리 + ⋮⋮ · − 막대. ⋮⋮ 끌어 순서 · − 빼기(5초 되돌리기) · [+ 추가] 시트 · 기본 구성 되돌리기.
 * 크기 조절 없음. 당겨서 새로고침은 API 단계(③ 결정).
 */
export function AppHome(p: AppHomeProps) {
  const k = useMotionK();
  const insets = useSafeAreaInsets();
  const scroll = useRef<ScrollViewInstance>(null);
  const [ready, setReady] = useState(false);
  const [editing, setEditing] = useState(false);
  const [line, setLine] = useState(false);
  const [search, setSearch] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [reset, setReset] = useState(false);
  const [snack, setSnack] = useState<Snack | null>(null);
  const [gone, setGone] = useState<HomeWidget | null>(null);
  const [fresh, setFresh] = useState<{ ids: HomeWidget[]; key: number; flash: boolean } | null>(null);
  const [lifted, setLifted] = useState<HomeWidget | null>(null);
  /* 넛지 닫은 상태는 한 곳(store/nudge)에 — 다시 들어와도 안 뜸 · 사용법 안내 중엔 숨김 */
  const nudgeS = useNudge('home');
  const nudge = nudgeS.show;
  const setNudge = (v: boolean) => {
    if (!v) nudgeS.hide();
  };
  const [editV] = useState(() => new Animated.Value(0));
  const [tys] = useState<Shift>(() => ({ market: new Animated.Value(0), updates: new Animated.Value(0), news: new Animated.Value(0), check: new Animated.Value(0) }));
  const order = p.widgets;
  const total = p.updates.reduce((a, u) => a + u.new_count, 0);
  const checkCode = p.stocks.find((s) => p.checklists[s.stock_code])?.stock_code ?? p.stocks[0]?.stock_code;

  /* 원본 #079: 1.2초 뼈대 → 위젯이 0.07초 간격으로 올라옴 · 숫자 세기 · 선 그리기 */
  useEffect(() => {
    const t = setTimeout(() => setReady(true), 1200 * k);
    return () => clearTimeout(t);
  }, [k]);
  useEffect(() => {
    const a = Animated.timing(editV, { toValue: editing ? 1 : 0, duration: 300 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [editing, editV, k]);
  const { onEditingChange } = p;
  useEffect(() => {
    onEditingChange?.(editing);
  }, [editing, onEditingChange]);
  useEffect(() => {
    if (!editing) return;
    const s = BackHandler.addEventListener('hardwareBackPress', () => {
      setEditing(false);
      return true;
    });
    return () => s.remove();
  }, [editing]);
  useEffect(() => {
    if (!snack) return;
    const t = setTimeout(() => setSnack(null), (snack.undo ? 5000 : 2200) * k);
    return () => clearTimeout(t);
  }, [snack, k]);
  const show = (msg: string, undo?: () => void) => setSnack({ msg, undo, key: nextKey() });
  const enterEdit = useCallback(() => {
    setEditing(true);
    setSnack(null);
  }, []);
  const exitEdit = () => {
    setEditing(false);
    setSnack(null);
  };

  /* ⋮⋮ 끌어서 순서 (원본 startDrag · moveDrag · endDrag): 지나간 자리의 위젯은 .28s 비켜 주고, 놓으면 .42s 반동으로 앉음 */
  const commitRef = useRef<(o: HomeWidget[]) => void>(() => {});
  useEffect(() => {
    commitRef.current = (o) => {
      setLifted(null);
      p.onChangeWidgets(o);
    };
  });
  /* 끄는 값은 같은 transform 의 들어오기(nv)와 함께 쓰여 JS 로 움직임 (네이티브와 섞으면 오류) */
  const drag = useMemo(() => {
    const s = { lay: {} as Partial<Record<HomeWidget, { y: number; h: number }>>, ids: [] as HomeWidget[], id: null as HomeWidget | null, from: -1, to: -1, shift: {} as Partial<Record<HomeWidget, number>> };
    return {
      layout: (id: HomeWidget, y: number, h: number) => {
        s.lay[id] = { y, h };
      },
      setIds: (ids: HomeWidget[]) => {
        s.ids = ids;
      },
      start: (id: HomeWidget) => {
        s.id = id;
        s.from = s.ids.indexOf(id);
        s.to = s.from;
        s.shift = {};
      },
      move: (dy: number) => {
        const id = s.id;
        const me = id ? s.lay[id] : undefined;
        if (!id || !me) return;
        tys[id].setValue(dy);
        const c = me.y + dy + me.h / 2;
        let to = 0;
        s.ids.forEach((w, i) => {
          const r = s.lay[w];
          if (i !== s.from && r && r.y + r.h / 2 < c) to++;
        });
        s.to = to;
        const sh = me.h + 14;
        s.ids.forEach((w, i) => {
          if (w === id) return;
          let t = 0;
          if (s.from < to && i > s.from && i <= to) t = -sh;
          if (s.from > to && i >= to && i < s.from) t = sh;
          if ((s.shift[w] ?? 0) !== t) {
            s.shift[w] = t;
            Animated.timing(tys[w], { toValue: t, duration: 280 * k, easing: curve.ease, useNativeDriver: false }).start();
          }
        });
      },
      end: () => {
        const id = s.id;
        const me = id ? s.lay[id] : undefined;
        if (!id || !me) return;
        s.id = null;
        const { from, to, ids } = s;
        if (from === to) {
          Animated.timing(tys[id], { toValue: 0, duration: 420 * k, easing: curve.land, useNativeDriver: false }).start(() => commitRef.current(ids));
          return;
        }
        const tgt = s.lay[ids[to]];
        const target = !tgt ? 0 : to > from ? tgt.y + tgt.h - (me.y + me.h) : tgt.y - me.y;
        const next = ids.filter((w) => w !== id);
        next.splice(to, 0, id);
        Animated.timing(tys[id], { toValue: target, duration: 420 * k, easing: curve.land, useNativeDriver: false }).start(() => commitRef.current(next));
      },
    };
  }, [tys, k]);
  useEffect(() => {
    drag.setIds(order);
  }, [order, drag]);
  /* 순서가 바뀐 뒤 새 자리에서 밀어 둔 값을 0 으로 (그리기 전) */
  const orderKey = order.join(',');
  useLayoutEffect(() => {
    ALL.forEach((w) => tys[w].setValue(0));
  }, [orderKey, tys]);

  /* − 빼기 (원본 removeW: 접히며 사라짐 .35s · 5초 되돌리기 링) */
  const remove = (id: HomeWidget) => {
    const idx = order.indexOf(id);
    setGone(id);
    setTimeout(() => {
      setGone(null);
      const rest = order.filter((w) => w !== id);
      p.onChangeWidgets(rest);
      show(`‘${WIDGET_META[id].title}’ 위젯을 뺐어요`, () => {
        const back = rest.filter((w) => w !== id);
        back.splice(idx, 0, id);
        p.onChangeWidgets(back);
        setFresh({ ids: [id], key: nextKey(), flash: false });
        setSnack(null);
      });
    }, 360 * k);
  };
  /* 위젯 추가 (원본 addW: 맨 위(인사 카드 바로 아래)에 커지며 들어오고 보라 빛 1.2초) */
  const add = (id: HomeWidget) => {
    setSheet(false);
    scroll.current?.scrollTo({ y: 0, animated: true });
    setTimeout(() => {
      p.onChangeWidgets([id, ...order.filter((w) => w !== id)]);
      setFresh({ ids: [id], key: nextKey(), flash: true });
      show(`‘${WIDGET_META[id].title}’ 위젯을 맨 위에 넣었어요 · 끌어서 옮길 수 있어요`);
    }, 300 * k);
  };

  const body = (id: HomeWidget) => {
    if (id === 'market') return p.market ? <MarketWidget indices={p.market} ready={ready} draw={ready} onOpen={(key) => !editing && p.onOpenMarket(key)} /> : <MarketFail onRetry={p.onRetryMarket} />;
    if (id === 'updates') return <UpdatesWidget rows={p.updates} ready={ready} editing={editing} onAll={p.onOpenUpdates} onRow={p.onOpenStockUpdates} />;
    if (id === 'news') return <NewsWidget items={p.news} day={p.news_day || (p.days[p.days.length - 1] ?? '')} total={p.news_day_total} now={p.now} ready={ready} editing={editing} onOpen={p.onOpenNews} />;
    const cl = checkCode ? (p.checklists[checkCode] ?? null) : null;
    return <CheckWidget cl={cl} editing={editing} onToggle={(iid) => checkCode && p.onToggleCheck(checkCode, iid)} onAdd={(t) => checkCode && p.onAddCheck(checkCode, t)} />;
  };

  const snackBottom = editing ? 24 + insets.bottom : 16;
  return (
    <View style={st.root}>
      {p.header({ line, onSearch: () => setSearch(true) })}
      {/* 편집 머리 (원본 .eh: 위 바 자리에 페이드 · -6 → 0) */}
      <Animated.View pointerEvents={editing ? 'auto' : 'none'} style={[st.eh, { top: insets.top, opacity: editV, transform: [{ translateY: editV.interpolate({ inputRange: [0, 1], outputRange: [-6, 0] }) }] }]}>
        <Text style={st.ehT}>홈 편집</Text>
        <Pressable onPress={() => setSheet(true)} accessibilityRole="button" style={({ pressed }) => [st.addp, pressed && { transform: [{ scale: 0.92 }] }]}>
          <PlusGlyph />
          <Text style={st.addpT}>추가</Text>
        </Pressable>
        <Pressable onPress={exitEdit} accessibilityRole="button" style={st.done}>
          <Text style={st.doneT}>완료</Text>
        </Pressable>
      </Animated.View>
      <ScrollView
        ref={scroll}
        style={st.flex}
        contentContainerStyle={st.pw}
        scrollEnabled={!lifted}
        showsVerticalScrollIndicator={false}
        scrollEventThrottle={16}
        onScroll={(e) => setLine(e.nativeEvent.contentOffset.y > 0)}
      >
        {/* 편집 안내 (원본 .einfo: 높이 0 → 52) */}
        <Animated.View style={{ height: editV.interpolate({ inputRange: [0, 1], outputRange: [0, 52] }), opacity: editV, overflow: 'hidden' }}>
          <Text style={st.einfo}>위젯을 끌어 순서를 바꾸고, 필요 없는 건 빼 보세요.</Text>
          <Pressable onPress={() => setReset(true)} accessibilityRole="button" hitSlop={4}>
            <Text style={[st.einfo, st.ereset]}>기본 구성으로 되돌리기</Text>
          </Pressable>
        </Animated.View>
        {/* 상단 줄 (웹 홈 제목 줄과 같은 정보): 내 종목 N · AI 연결 메모 N · 홈 편집 */}
        {!editing && !p.firstStart ? (
          <View style={st.hr}>
            <View style={st.pill}><Text style={st.pillT}>내 종목 <Text style={st.pillB}>{p.counts.holding + p.counts.watching}</Text></Text></View>
            <View style={st.pill}><Text style={st.pillT}>AI 연결 메모 <Text style={st.pillB}>{p.counts.ai_memos}</Text></Text></View>
            <Pressable onPress={enterEdit} accessibilityRole="button" style={({ pressed }) => [st.pill, st.pillEdit, pressed && { transform: [{ scale: 0.94 }] }]}>
              <SlidersGlyph />
              <Text style={[st.pillT, { color: appColor.ink }]}>홈 편집</Text>
            </Pressable>
          </View>
        ) : null}
        <View style={st.wl}>
          {/* 첫 홈(원본 start.html)은 위젯 없이 고른 종목만 있는 빈 홈 → firstStart 가 있으면 그것만 */}
          {p.firstStart}
          {!p.firstStart ? <HeroCard name={p.user_name} total={total} editing={editing} ready={ready} onCta={() => !editing && p.onOpenUpdates()} /> : null}
          {!p.firstStart && order.map((id, i) => (
            <WidgetItem
              key={id}
              id={id}
              editing={editing}
              editV={editV}
              ty={tys[id]}
              lifted={lifted === id}
              gone={gone === id}
              fresh={fresh && fresh.ids.includes(id) ? fresh : null}
              drag={drag}
              onLift={setLifted}
              onRemove={() => remove(id)}
              onLongPress={enterEdit}
            >
              {ready ? (
                <Reveal i={i + 1} key={`r-${String(ready)}`}>
                  {body(id)}
                </Reveal>
              ) : (
                body(id)
              )}
            </WidgetItem>
          ))}
        </View>
        {editing && order.length === 0 ? (
          <Reveal>
            <Pressable onPress={() => setSheet(true)} accessibilityRole="button" style={st.addw}>
              <View style={st.addwPl}>
                <Text style={st.addwPlT}>+</Text>
              </View>
              <Text style={st.addwB}>위젯 추가</Text>
              <Text style={st.addwT}>눌러서 위젯을 골라 보세요</Text>
            </Pressable>
          </Reveal>
        ) : null}
        <View style={{ height: !editing && nudge && !p.firstStart ? 64 : 0 }} />
      </ScrollView>

      {nudge && !editing && ready && !p.firstStart ? (
        <View style={[st.nudge, { bottom: snack ? 76 : 16 }]} pointerEvents="box-none">
          <NudgePill text="이번 주 내 종목, 한 장으로 볼까요?" onGo={() => p.onNudge('report')} onClose={() => setNudge(false)} />
        </View>
      ) : null}
      <AppSnackbar visible={!!snack} message={snack?.msg ?? ''} onUndo={snack?.undo} style={[st.snack, { bottom: snackBottom }]} />

      <HomeSearch open={search} onClose={() => setSearch(false)} recent={p.search.recent} popular={p.search.popular} all={p.search.all} onPick={p.onOpenStock} />
      <Sheet open={sheet} onClose={() => setSheet(false)} title="위젯 추가" label="위젯 추가">
        <View style={{ paddingTop: 4 }}>
          {ALL.map((id) => {
            const have = order.includes(id);
            return (
              <View key={id} style={st.wr}>
                <View style={[st.wrBx, { backgroundColor: WIDGET_META[id].bg }]}>
                  <WidgetGlyph id={id} />
                </View>
                <View style={st.flexMin}>
                  <Text style={st.wrB}>{WIDGET_META[id].title}</Text>
                  <Text style={st.wrS}>{WIDGET_META[id].sub}</Text>
                </View>
                <Pressable disabled={have} onPress={() => add(id)} accessibilityRole="button" style={({ pressed }) => [st.ad, have && st.adOff, pressed && { transform: [{ scale: 0.92 }] }]}>
                  <Text style={[st.adT, have && { color: appColor.ink3 }]}>{have ? '추가됨' : '추가'}</Text>
                </Pressable>
              </View>
            );
          })}
        </View>
      </Sheet>
      <ConfirmDialog
        variant="app"
        open={reset}
        title="기본 구성으로 되돌릴까요?"
        body="지금 순서와 고른 위젯이 처음 구성(시장 · 업데이트 · 뉴스)으로 바뀌어요."
        confirmLabel="되돌리기"
        onCancel={() => setReset(false)}
        onConfirm={() => {
          setReset(false);
          p.onChangeWidgets(DEFAULT_W);
          setFresh({ ids: DEFAULT_W, key: nextKey(), flash: false });
        }}
      />
    </View>
  );
}

type DragBox = { layout: (id: HomeWidget, y: number, h: number) => void; start: (id: HomeWidget) => void; move: (dy: number) => void; end: () => void };

/** 위젯 한 칸: 편집 테두리 · ⋮⋮ − 막대 · 꾹 눌러 편집 · 빼기 접힘 · 새로 들어옴 · 끌기 */
function WidgetItem({
  id,
  editing,
  editV,
  ty,
  lifted,
  gone,
  fresh,
  drag,
  onLift,
  onRemove,
  onLongPress,
  children,
}: {
  id: HomeWidget;
  editing: boolean;
  editV: Animated.Value;
  ty: Animated.Value;
  lifted: boolean;
  gone: boolean;
  fresh: { key: number; flash: boolean; ids: HomeWidget[] } | null;
  drag: DragBox;
  onLift: (id: HomeWidget | null) => void;
  onRemove: () => void;
  onLongPress: () => void;
  children: React.ReactNode;
}) {
  const k = useMotionK();
  const [h, setH] = useState(0);
  const [cv] = useState(() => new Animated.Value(1));
  const [nv] = useState(() => new Animated.Value(1));
  const [fl] = useState(() => new Animated.Value(0));
  const freshKey = fresh?.key ?? 0;
  const flash = !!fresh?.flash;
  const idx = fresh ? fresh.ids.indexOf(id) : 0;
  useEffect(() => {
    if (!gone) return;
    const a = Animated.timing(cv, { toValue: 0, duration: 350 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [gone, cv, k]);
  useEffect(() => {
    if (!freshKey) return;
    nv.setValue(0);
    const a = Animated.timing(nv, { toValue: 1, duration: 600 * k, delay: idx * 60 * k, easing: curve.spring, useNativeDriver: false });
    a.start();
    let b: Animated.CompositeAnimation | null = null;
    if (flash) {
      b = Animated.sequence([
        Animated.timing(fl, { toValue: 1, duration: 240 * k, useNativeDriver: false }),
        Animated.timing(fl, { toValue: 0, duration: 960 * k, useNativeDriver: false }),
      ]);
      b.start();
    }
    return () => {
      a.stop();
      b?.stop();
    };
  }, [freshKey, flash, idx, nv, fl, k]);
  /* 꾹 누르기 550ms → 편집 (8 넘게 움직이면 취소) */
  const lp = useMemo(() => {
    const s = { t: null as ReturnType<typeof setTimeout> | null, x: 0, y: 0 };
    const clear = () => {
      if (s.t) clearTimeout(s.t);
      s.t = null;
    };
    return {
      clear,
      begin: (x: number, y: number, fn: () => void) => {
        clear();
        s.x = x;
        s.y = y;
        s.t = setTimeout(fn, 550);
      },
      check: (x: number, y: number) => {
        if (Math.hypot(x - s.x, y - s.y) > 8) clear();
      },
    };
  }, []);
  const pan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onPanResponderGrant: () => {
          drag.start(id);
          onLift(id);
        },
        onPanResponderMove: (_, g) => drag.move(g.dy),
        onPanResponderRelease: () => drag.end(),
        onPanResponderTerminate: () => drag.end(),
        onPanResponderTerminationRequest: () => false,
      }),
    [drag, id, onLift],
  );
  return (
    <Animated.View
      onLayout={(e) => {
        drag.layout(id, e.nativeEvent.layout.y, e.nativeEvent.layout.height);
        if (!gone) setH(e.nativeEvent.layout.height);
      }}
      onTouchStart={(e) => {
        if (editing) return;
        lp.begin(e.nativeEvent.pageX, e.nativeEvent.pageY, onLongPress);
      }}
      onTouchMove={(e) => {
        lp.check(e.nativeEvent.pageX, e.nativeEvent.pageY);
      }}
      onTouchEnd={lp.clear}
      onTouchCancel={lp.clear}
      style={[
        lifted && st.lift,
        gone && h ? { height: cv.interpolate({ inputRange: [0, 1], outputRange: [0, h] }), marginTop: cv.interpolate({ inputRange: [0, 1], outputRange: [-14, 0] }), overflow: 'hidden' } : null,
        {
          zIndex: lifted ? 10 : 0,
          opacity: gone ? cv : nv,
          transform: [
            { translateY: Animated.add(ty, nv.interpolate({ inputRange: [0, 1], outputRange: [20, 0] })) },
            { scale: gone ? cv.interpolate({ inputRange: [0, 1], outputRange: [0.94, 1] }) : lifted ? 1.02 : nv.interpolate({ inputRange: [0, 1], outputRange: [0.92, 1] }) },
          ],
        },
      ]}
    >
      <WidgetShell>
        {/* 편집 막대 (원본 .wbar: 0 → 40 · 아래 선 #EEF0F3) */}
        <Animated.View style={[st.wbar, { height: editV.interpolate({ inputRange: [0, 1], outputRange: [0, 40] }), borderBottomWidth: editing ? 1 : 0 }]}>
          <View {...pan.panHandlers} style={st.hdl} accessibilityLabel="길게 눌러 이동">
            <GripDots />
            <Text style={st.hdlT}>길게 눌러 이동</Text>
          </View>
          <Pressable onPress={onRemove} accessibilityRole="button" accessibilityLabel="빼기" style={({ pressed }) => [st.rmb, pressed && { transform: [{ scale: 0.85 }] }]}>
            <Text style={st.rmbT}>−</Text>
          </Pressable>
        </Animated.View>
        {children}
      </WidgetShell>
      {/* 편집 테두리 1.5 보라 (원본 box-shadow 0 0 0 1.5) · 새 위젯 빛 (0 0 0 4 rgba(133,105,227,.35)) */}
      <Animated.View pointerEvents="none" style={[st.ring, { opacity: editV }]} />
      <Animated.View pointerEvents="none" style={[st.flash, { opacity: fl }]} />
    </Animated.View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: appColor.bg },
  flex: { flex: 1 },
  flexMin: { flex: 1, minWidth: 0 },
  pw: { paddingTop: 0, paddingHorizontal: 16, paddingBottom: 40 },
  wl: { gap: 14 },
  eh: { position: 'absolute', left: 0, right: 0, height: TAB_BAR_H, zIndex: 7, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 18, backgroundColor: appColor.bg },
  ehT: { flex: 1, ...ft(20), fontWeight: '700', color: appColor.ink },
  addp: { flexDirection: 'row', alignItems: 'center', gap: 4, minHeight: 34, paddingLeft: 11, paddingRight: 13, borderRadius: 17, backgroundColor: appColor.accentSoft2, marginRight: 6 },
  addpT: { ...ft(14), fontWeight: '800', color: appColor.deepPurple },
  done: { padding: 8 },
  doneT: { ...ft(16), fontWeight: '800', color: appColor.deepPurple },
  einfo: { ...ft(13, 1.7), color: appColor.ink2 },
  ereset: { fontWeight: '700', color: appColor.deepPurple },
  wbar: { overflow: 'hidden', flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 14, paddingRight: 10, borderBottomColor: '#EEF0F3' },
  hdl: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6, height: 40 },
  hdlT: { ...ft(12.5), color: appColor.ink3 },
  rmb: { marginLeft: 'auto', width: 26, height: 26, borderRadius: 13, backgroundColor: appColor.redSoft, alignItems: 'center', justifyContent: 'center' },
  rmbT: { fontSize: 18, lineHeight: 20, fontWeight: '700', color: appColor.red },
  ring: { position: 'absolute', top: -1.5, left: -1.5, right: -1.5, bottom: -1.5, borderRadius: 23.5, borderWidth: 1.5, borderColor: appColor.accent },
  flash: { position: 'absolute', top: -4, left: -4, right: -4, bottom: -4, borderRadius: 26, borderWidth: 4, borderColor: 'rgba(133,105,227,0.35)' },
  lift: { shadowColor: '#28145A', shadowOpacity: 0.45, shadowRadius: 20, shadowOffset: { width: 0, height: 24 }, elevation: 12, backgroundColor: appColor.surface, borderRadius: 22 },
  addw: { borderWidth: 1.5, borderStyle: 'dashed', borderColor: '#C9CDD4', borderRadius: 22, alignItems: 'center', justifyContent: 'center', gap: 6, padding: 26, marginTop: 14 },
  addwPl: { width: 44, height: 44, borderRadius: 22, backgroundColor: appColor.accentSoft, alignItems: 'center', justifyContent: 'center' },
  addwPlT: { fontSize: 24, lineHeight: 28, color: appColor.deepPurple },
  addwB: { ...ft(16), fontWeight: '700', color: appColor.ink },
  addwT: { ...ft(13), color: appColor.ink2 },
  hr: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingBottom: 10 },
  pill: { minHeight: 32, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, borderRadius: 16, backgroundColor: appColor.surface },
  pillEdit: { marginLeft: 'auto' },
  pillT: { ...ft(13), color: appColor.ink2 },
  pillB: { ...ft(13), fontWeight: '700', color: appColor.ink, fontVariant: ['tabular-nums'] },
  nudge: { position: 'absolute', left: 16, right: 16, alignItems: 'center' },
  snack: { position: 'absolute', left: 14, right: 14 },
  wr: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingHorizontal: 22, minHeight: 68 },
  wrBx: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  wrB: { ...ft(15.5), fontWeight: '700', color: appColor.ink },
  wrS: { ...ft(12.5), color: appColor.ink3 },
  ad: { marginLeft: 'auto', minHeight: 36, paddingHorizontal: 16, paddingVertical: 8, borderRadius: 12, backgroundColor: appColor.accent, alignItems: 'center', justifyContent: 'center' },
  adOff: { backgroundColor: '#EEF0F3' },
  adT: { ...ft(14), fontWeight: '700', color: '#FFFFFF' },
});
