import React, { useEffect, useMemo, useState } from 'react';
import { Animated, BackHandler, PanResponder, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import { Text, TextInput } from '@/components/ui/AppText';
import { Odometer } from '@/ui/motion/Numbers';
import { Reveal } from '@/ui/motion/Reveal';
import { Skeleton } from '@/ui/motion/Skeleton';
import { useMotionK } from '@/ui/motion/useMotion';
import { FeedCard } from '@/ui/screens/memo/app/MemoFeed';
import { NudgePill } from '@/ui/shared/NudgePill';
import { AppSnackbar } from '@/ui/shared/Snackbar';
import { StockLogo } from '@/ui/shared/StockLogo';
import { appColor, curve, ft } from '@/ui/theme';
import type { AppUpdatesProps, KindFilter, UpdateItem, UpdateStock } from '../Updates.types';
import { versionsOf } from '../Updates.mock';
import { APP_TAG, KINDS, ago, byStock, dayGroup, unreadOf } from '../updatesFormat';
import { useNudge } from '@/store/nudge';

let seq = 0;
const nextKey = () => ++seq;

/**
 * 앱 업데이트 탭 (원본 update.html · 11.05 A안: 종목별 업데이트도 같은 화면에서 칩만 바뀜)
 * 큰 제목 · 읽지 않은 소식 · 종목 칩(검은 알약) · 종류 칩 · 종목 카드(최근 3건) / 종목을 고르면 종목 카드 + 날짜 묶음 + ④ 소식 카드
 * ✓ 모두 읽음(전체에서만 · 5초 되돌리기) · 내 종목에서 찾기 · 소식 줄 왼쪽으로 밀어 읽음/안 읽음 · 넛지.
 * 당겨서 새로고침은 API 단계(③ 결정).
 */
export function AppUpdates(p: AppUpdatesProps) {
  const k = useMotionK();
  const insets = useSafeAreaInsets();
  const [code, setCode] = useState<string | undefined>(p.code);
  const [kind, setKind] = useState<KindFilter>('전체');
  const [ready, setReady] = useState(false);
  const [y, setY] = useState(0);
  const [search, setSearch] = useState(false);
  const [q, setQ] = useState('');
  const [openId, setOpenId] = useState<string | null>(null);
  const [snack, setSnack] = useState<{ msg: string; undo?: () => void; key: number } | null>(null);
  /* 넛지 닫은 상태는 한 곳(store/nudge)에 — 다시 들어와도 안 뜸 · 사용법 안내 중엔 숨김 */
  const nudgeS = useNudge('updates');
  const nudge = nudgeS.show;
  const setNudge = (v: boolean) => {
    if (!v) nudgeS.hide();
  };
  const [fading, setFading] = useState<string[]>([]);
  const cur = code ? p.stocks.find((s) => s.stock_code === code) : undefined;
  const total = unreadOf(p.items);

  useEffect(() => {
    const t = setTimeout(() => setReady(true), 900 * k);
    return () => clearTimeout(t);
  }, [k]);
  useEffect(() => {
    if (!snack) return;
    const t = setTimeout(() => setSnack(null), (snack.undo ? 5000 : 2200) * k);
    return () => clearTimeout(t);
  }, [snack, k]);
  const pick = (c: string | undefined) => {
    setCode(c);
    setKind('전체');
    setOpenId(null);
    p.onChangeCode?.(c);
  };
  /* 하드웨어 뒤로: 검색 → 종목 → 화면 */
  useEffect(() => {
    if (!search && !code) return;
    const s = BackHandler.addEventListener('hardwareBackPress', () => {
      if (search) setSearch(false);
      else pick(undefined);
      return true;
    });
    return () => s.remove();
  });
  const readAll = () => {
    const ids = p.items.filter((u) => u.unread).map((u) => u.id);
    if (!ids.length) return;
    /* 원본: 점이 0.045초 간격으로 꺼진 뒤 표시 */
    setFading(ids);
    setTimeout(() => {
      setFading([]);
      p.onMarkRead(ids, true);
      setSnack({ msg: `${ids.length}건을 모두 읽음으로 표시했어요`, undo: () => (p.onMarkRead(ids, false), setSnack(null)), key: nextKey() });
    }, (ids.length * 45 + 120) * k);
  };
  const open = (u: UpdateItem) => {
    setOpenId((o) => (o === u.id ? null : u.id));
    if (u.unread) p.onMarkRead([u.id], true);
  };
  const tScale = 1 - Math.min(1, y / 60) * 0.12;
  const tOpacity = 1 - Math.min(1, y / 60) * 0.9;
  const nN = cur ? unreadOf(byStock(p.items, cur.stock_code)) : total;

  return (
    <View style={st.root}>
      {p.header({ title: y > 44, line: y > 44, onSearch: () => (setQ(''), setSearch(true)), onReadAll: code ? undefined : readAll, readAllOff: !total })}
      <ScrollView style={st.flex} contentContainerStyle={st.pw} stickyHeaderIndices={[1]} scrollEventThrottle={16} onScroll={(e) => setY(e.nativeEvent.contentOffset.y)} showsVerticalScrollIndicator={false}>
        <View style={[st.lt, { opacity: tOpacity, transform: [{ scale: tScale }] }]}>
          <Text style={st.ltH}>최신 업데이트</Text>
          <Text style={st.ltP}>내 종목의 공시·뉴스·주가 변동을 모아봤어요</Text>
          <View style={st.unr}>
            <View style={st.unrDot} />
            <Text style={st.unrT}>읽지 않은 소식 </Text>
            <Odometer value={total} style={st.unrB} />
            <Text style={st.unrB}>건</Text>
          </View>
        </View>
        <View style={st.chipsBar}>
          <SlideChips
            items={[{ key: 'all', label: '전체' }, ...p.stocks.map((s) => ({ key: s.stock_code, label: s.name, badge: unreadOf(byStock(p.items, s.stock_code)) }))]}
            value={code ?? 'all'}
            onChange={(c) => pick(c === 'all' ? undefined : c)}
          />
        </View>
        {!cur ? (
          <Overview p={p} kind={kind} setKind={setKind} ready={ready} fading={fading} onOpenStock={pick} onOpenRow={(u) => {
            if (u.unread) p.onMarkRead([u.id], true);
            p.onOpenEvidence(u);
          }} />
        ) : (
          <StockView p={p} s={cur} kind={kind} setKind={setKind} openId={openId} onOpen={open} />
        )}
        {cur && !byStock(p.items, cur.stock_code).length ? null : (
          <View style={st.fin}>
            <Svg width={34} height={34} viewBox="0 0 34 34">
              <Circle cx={17} cy={17} r={16} fill="#EEE9FB" />
              <Path d="M10.5 17.5l4.5 4.5 8.5-9" fill="none" stroke="#6A42AB" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" />
            </Svg>
            <Text style={st.finT}>최근 30일 업데이트를 모두 확인했어요</Text>
          </View>
        )}
        <Text style={st.disc}>투자 권유가 아닌 참고 정보예요 · AI는 틀릴 수 있어 원문을 꼭 확인해 주세요</Text>
        <View style={{ height: nudge && nN ? 60 : 0 }} />
      </ScrollView>

      {nudge && nN && !search ? (
        <View style={[st.nudge, { bottom: snack ? 76 : 16 }]} pointerEvents="box-none">
          <NudgePill text={`오늘 소식 ${nN}건, 라디오로 들을까요?`} onGo={p.onNudge} onClose={() => setNudge(false)} />
        </View>
      ) : null}
      <AppSnackbar visible={!!snack} message={snack?.msg ?? ''} onUndo={snack?.undo} style={st.snack} />
      {search ? <SearchOver stocks={p.stocks} items={p.items} q={q} setQ={setQ} top={insets.top} onClose={() => setSearch(false)} onPick={(c) => (setSearch(false), pick(c))} /> : null}
    </View>
  );
}

/* ───────── 칩 (원본 #039: 검은 알약이 .45s 반동으로 미끄러짐) ───────── */
function SlideChips({ items, value, onChange }: { items: { key: string; label: string; badge?: number; count?: number }[]; value: string; onChange: (k: string) => void }) {
  const k = useMotionK();
  const [lay, setLay] = useState<Record<string, { x: number; w: number }>>({});
  const [x] = useState(() => new Animated.Value(0));
  const [w] = useState(() => new Animated.Value(0));
  const cur = lay[value];
  useEffect(() => {
    if (!cur) return;
    const a = Animated.parallel([Animated.timing(x, { toValue: cur.x, duration: 450 * k, easing: curve.spring, useNativeDriver: false }), Animated.timing(w, { toValue: cur.w, duration: 450 * k, easing: curve.spring, useNativeDriver: false })]);
    a.start();
    return () => a.stop();
  }, [cur, x, w, k]);
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={st.cin}>
      {cur ? <Animated.View style={[st.cpill, { left: x, width: w }]} /> : null}
      {items.map((c) => {
        const on = c.key === value;
        return (
          <Pressable
            key={c.key}
            onLayout={(e) => {
              const { x: lx, width } = e.nativeEvent.layout;
              setLay((l) => (l[c.key]?.x === lx && l[c.key]?.w === width ? l : { ...l, [c.key]: { x: lx, w: width } }));
            }}
            onPress={() => onChange(c.key)}
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            style={[st.chip, !on && st.chipOff]}
          >
            <Text style={[st.chipT, on && { color: '#FFFFFF' }]}>{c.label}</Text>
            {c.count !== undefined ? <Text style={[st.chipN, on && { color: 'rgba(255,255,255,0.8)' }]}>{c.count}</Text> : null}
            {c.badge ? (
              <View style={st.chipC}>
                <Text style={st.chipCT}>{c.badge}</Text>
              </View>
            ) : null}
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

function KindChips({ pool, kind, setKind }: { pool: UpdateItem[]; kind: KindFilter; setKind: (k: KindFilter) => void }) {
  return (
    <View style={st.tch}>
      <SlideChips items={KINDS.map((t) => ({ key: t, label: t, count: pool.filter((u) => t === '전체' || u.kind === t).length }))} value={kind} onChange={(t) => setKind(t as KindFilter)} />
    </View>
  );
}

function OwnChip({ s }: { s: UpdateStock }) {
  const w = s.status === 'watching';
  return (
    <View style={[st.own, w && { backgroundColor: appColor.sf }]}>
      <Text style={[st.ownT, w && { color: appColor.ink2 }]}>{w ? '관심' : '보유'}</Text>
    </View>
  );
}
function Chev() {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={appColor.ink3} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M9 5l7 7-7 7" />
    </Svg>
  );
}

/* ───────── 전체: 종목 카드 (원본 .uc · 최근 3건 · N건 더 보기) ───────── */
function Overview({ p, kind, setKind, ready, fading, onOpenStock, onOpenRow }: { p: AppUpdatesProps; kind: KindFilter; setKind: (k: KindFilter) => void; ready: boolean; fading: string[]; onOpenStock: (c: string) => void; onOpenRow: (u: UpdateItem) => void }) {
  const pool = p.stocks.flatMap((s) => byStock(p.items, s.stock_code));
  return (
    <View>
      <KindChips pool={pool} kind={kind} setKind={setKind} />
      {p.stocks.map((s, i) => {
        const L = byStock(p.items, s.stock_code).filter((u) => kind === '전체' || u.kind === kind);
        if (kind !== '전체' && !L.length) return null;
        const rows = L.slice(0, 3);
        if (!ready)
          return (
            <View key={s.stock_code} style={st.uc}>
              <View style={[st.hd, { paddingBottom: 12 }]}>
                <Skeleton style={{ width: 40, height: 40 }} radius={11} />
                <View style={{ flex: 1, gap: 6 }}>
                  <Skeleton style={{ width: 110, height: 16 }} />
                  <Skeleton style={{ width: 80, height: 11 }} />
                </View>
              </View>
              <Skeleton style={{ height: 14, marginTop: 10, marginBottom: 14 }} />
              <Skeleton style={{ height: 14, marginBottom: 14, width: '85%' }} />
              <Skeleton style={{ height: 14, marginBottom: 10, width: '70%' }} />
            </View>
          );
        return (
          <Reveal key={s.stock_code} i={i} style={st.uc}>
            <Pressable onPress={() => onOpenStock(s.stock_code)} accessibilityRole="button" style={({ pressed }) => [st.hd, pressed && { opacity: 0.6 }]}>
              <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={40} variant="app" />
              <View style={st.flexMin}>
                <View style={st.nmRow}>
                  <Text style={st.nm} numberOfLines={1}>
                    {s.name}
                  </Text>
                  <OwnChip s={s} />
                </View>
                <Text style={st.code}>
                  {s.stock_code} · {s.market}
                </Text>
              </View>
              <Chev />
            </Pressable>
            {L.length ? (
              rows.map((u) => (
                <Pressable key={u.id} onPress={() => onOpenRow(u)} accessibilityRole="button" style={({ pressed }) => [st.lr, pressed && { opacity: 0.6 }]}>
                  <View style={[st.tg, { backgroundColor: APP_TAG[u.kind].bg }]}>
                    <Text style={[st.tgT, { color: APP_TAG[u.kind].ink }]}>{u.kind}</Text>
                  </View>
                  <Text style={st.tt} numberOfLines={1}>
                    {u.headline}
                  </Text>
                  <Text style={st.ag}>{ago(u.at, p.now)}</Text>
                  <Dot on={u.unread && !fading.includes(u.id)} />
                </Pressable>
              ))
            ) : (
              <View style={[st.lr, { justifyContent: 'center' }]}>
                <Text style={st.nv}>{s.ai_ready ? '아직 업데이트가 없어요 · 메모를 AI와 연결해 보세요' : 'AI 연결 준비 중인 종목이에요 · 메모는 바로 쓸 수 있어요'}</Text>
              </View>
            )}
            {L.length > 3 ? (
              <Pressable onPress={() => onOpenStock(s.stock_code)} accessibilityRole="button" style={st.more}>
                <Text style={st.moreT}>{L.length - 3}건 더 보기</Text>
              </Pressable>
            ) : null}
          </Reveal>
        );
      })}
    </View>
  );
}

function Dot({ on }: { on: boolean }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(on ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: on ? 1 : 0, duration: 350 * k, easing: curve.spring, useNativeDriver: true });
    a.start();
    return () => a.stop();
  }, [on, v, k]);
  return <Animated.View style={[st.dot, { opacity: v, transform: [{ scale: v }] }]} />;
}

/* ───────── 종목별 (원본 06.1: 종목 카드 · 읽지 않은 소식 · 종류 칩 · 날짜 묶음 · 줄 밀기) ───────── */
function StockView({ p, s, kind, setKind, openId, onOpen }: { p: AppUpdatesProps; s: UpdateStock; kind: KindFilter; setKind: (k: KindFilter) => void; openId: string | null; onOpen: (u: UpdateItem) => void }) {
  const all = byStock(p.items, s.stock_code);
  const L = all.filter((u) => kind === '전체' || u.kind === kind);
  const groups: [string, UpdateItem[]][] = [];
    L.forEach((u) => {
      const key = dayGroup(u.at, p.now);
      const f = groups.find((x) => x[0] === key);
      if (f) f[1].push(u);
      else groups.push([key, [u]]);
    });

  const card = (
    <View style={st.sc}>
      <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={40} variant="app" />
      <View style={st.flexMin}>
        <View style={st.nmRow}>
          <Text style={[st.nm, { ...ft(19) }]} numberOfLines={1}>
            {s.name}
          </Text>
          <OwnChip s={s} />
        </View>
        <Text style={st.code}>
          {s.stock_code} · {s.market}
        </Text>
      </View>
      <Pressable onPress={() => p.onOpenBoard(s.stock_code)} accessibilityRole="button" style={st.mb}>
        <Text style={st.mbT}>메모 보드 ›</Text>
      </Pressable>
    </View>
  );
  if (!all.length)
    return (
      <View>
        {card}
        <Empty name={s.name} onGo={() => p.onOpenBoard(s.stock_code)} />
      </View>
    );
  return (
    <View>
      {card}
      <View style={st.sub2}>
        <Text style={st.sub2T}>읽지 않은 소식 </Text>
        <Odometer value={unreadOf(all)} style={st.sub2B} />
        <Text style={st.sub2B}>건</Text>
        <Text style={st.sub2T}> · 최근 30일</Text>
      </View>
      <KindChips pool={all} kind={kind} setKind={setKind} />
      {groups.map(([g, list]) => (
        <View key={g}>
          <Text style={st.gh}>{g}</Text>
          {list.map((u) => (
            <ReadSwipe key={u.id} read={!u.unread} onToggle={() => p.onMarkRead([u.id], u.unread)}>
              <FeedCard f={u} ver={versionsOf(u.memo_id).find((v) => v.version === u.memo_version)} open={openId === u.id} onToggle={() => onOpen(u)} onOpenSource={() => p.onOpenSource(u)} onOpenEvidence={() => p.onOpenEvidence(u)} />
            </ReadSwipe>
          ))}
        </View>
      ))}
    </View>
  );
}

/** 소식 줄 왼쪽으로 밀기 → 읽음/안 읽음 (원본 .dr .act 88 · 보라) */
function ReadSwipe({ read, onToggle, children }: { read: boolean; onToggle: () => void; children: React.ReactNode }) {
  const k = useMotionK();
  const [x] = useState(() => new Animated.Value(0));
  const [opened, setOpened] = useState(false);
  const pan = useMemo(() => {
    const s = { base: 0, cur: 0 };
    return PanResponder.create({
      onMoveShouldSetPanResponderCapture: (_, g) => Math.abs(g.dx) > 8 && Math.abs(g.dx) > Math.abs(g.dy),
      onPanResponderGrant: () => {
        s.base = opened ? -88 : 0;
      },
      onPanResponderMove: (_, g) => {
        let v = s.base + g.dx;
        if (v > 0) v = 0;
        if (v < -88) v = -88 + (v + 88) * 0.3;
        s.cur = v;
        x.setValue(v);
      },
      onPanResponderRelease: () => {
        const o = s.cur < -44;
        setOpened(o);
        Animated.timing(x, { toValue: o ? -88 : 0, duration: 320 * k, easing: curve.ease, useNativeDriver: true }).start();
      },
      onPanResponderTerminationRequest: () => false,
    });
  }, [opened, x, k]);
  return (
    <View style={st.swWrap} {...pan.panHandlers}>
      <Pressable
        onPress={() => {
          onToggle();
          setOpened(false);
          Animated.timing(x, { toValue: 0, duration: 320 * k, easing: curve.ease, useNativeDriver: true }).start();
        }}
        accessibilityRole="button"
        style={st.act}
      >
        <Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
          <Path d="M4 12.5l5 5L20 7" />
        </Svg>
        <Text style={st.actT}>{read ? '안 읽음' : '읽음'}</Text>
      </Pressable>
      <Animated.View style={{ transform: [{ translateX: x }] }}>{children}</Animated.View>
    </View>
  );
}

function Empty({ name, onGo }: { name: string; onGo: () => void }) {
  return (
    <Reveal style={st.emp}>
      <Svg width={180} height={110} viewBox="0 0 180 110" fill="none">
        <Rect x={8} y={22} width={70} height={78} rx={12} fill="#FFF8E6" stroke="#F1DFA8" />
        <Path d="M20 42h46M20 56h40M20 70h30" stroke="#E2C97A" strokeWidth={3} strokeLinecap="round" />
        <Path d="M80 60 C 105 60, 105 40, 128 40" stroke="#8569E3" strokeWidth={2.4} strokeLinecap="round" strokeDasharray="4 5" />
        <Rect x={128} y={18} width={44} height={44} rx={12} fill="#EEE9FB" />
        <Path d="M140 32h20M140 40h20M140 48h12" stroke="#8569E3" strokeWidth={2.6} strokeLinecap="round" />
        <Path d="M100 14l2.4 6 6 2.4-6 2.4-2.4 6-2.4-6-6-2.4 6-2.4z" fill="#8569E3" />
      </Svg>
      <Text style={st.empH}>아직 {name} 업데이트가 없어요</Text>
      <Text style={st.empP}>{'메모를 AI와 연결하면 관련 공시·뉴스·\n가격 변화를 모아 드려요.'}</Text>
      <Pressable onPress={onGo} accessibilityRole="button" style={({ pressed }) => [st.cta, pressed && { transform: [{ scale: 0.95 }] }]}>
        <Text style={st.ctaT}>메모 보드로 가기</Text>
      </Pressable>
    </Reveal>
  );
}

/* ───────── 내 종목에서 찾기 (원본 11.13 제안 .sbx2 · .ssp) ───────── */
const CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';
const cho = (t: string) =>
  [...t]
    .map((c) => {
      const n = c.charCodeAt(0) - 44032;
      return n >= 0 && n < 11172 ? CHO[Math.floor(n / 588)] : c;
    })
    .join('');
function SearchOver({ stocks, items, q, setQ, top, onClose, onPick }: { stocks: UpdateStock[]; items: UpdateItem[]; q: string; setQ: (v: string) => void; top: number; onClose: () => void; onPick: (c: string) => void }) {
  const { height } = useWindowDimensions();
  const t = q.trim();
  const hits = stocks.filter((s) => !t || s.name.toLowerCase().includes(t.toLowerCase()) || cho(s.name).includes(t) || s.stock_code.includes(t));
  return (
    <View style={[StyleSheet.absoluteFill, { backgroundColor: appColor.bg, height }]}>
      <View style={[st.sbx, { marginTop: top }]}>
        <View style={st.sbxL}>
          <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={appColor.ink3} strokeWidth={2.2} strokeLinecap="round">
            <Circle cx={11} cy={11} r={7} />
            <Path d="M20 20l-4-4" />
          </Svg>
          <TextInput autoFocus value={q} onChangeText={setQ} placeholder="내 종목에서 찾기 (초성도 돼요)" placeholderTextColor={appColor.ink3} style={st.sbxIn} />
        </View>
        <Pressable onPress={onClose} accessibilityRole="button" style={st.cx}>
          <Text style={st.cxT}>취소</Text>
        </Pressable>
      </View>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={st.ssp}>
        {hits.length ? (
          <>
            <Text style={st.sh3}>{t ? `찾은 종목 ${hits.length}` : `내 종목 ${stocks.length}개`}</Text>
            <View style={st.gp}>
              {hits.map((s, i) => {
                const n = unreadOf(byStock(items, s.stock_code));
                const at = t ? s.name.toLowerCase().indexOf(t.toLowerCase()) : -1;
                return (
                  <Pressable key={s.stock_code} onPress={() => onPick(s.stock_code)} accessibilityRole="button" style={[st.rw, i > 0 && st.rwLine]}>
                    <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={36} variant="app" radius={10} fontSize={14} />
                    <View style={st.flexMin}>
                      <Text style={st.rwB}>
                        {at >= 0 ? (
                          <>
                            {s.name.slice(0, at)}
                            <Text style={{ color: appColor.deepPurple }}>{s.name.slice(at, at + t.length)}</Text>
                            {s.name.slice(at + t.length)}
                          </>
                        ) : (
                          s.name
                        )}
                      </Text>
                      <Text style={st.rwS}>
                        {s.stock_code} · {s.status === 'holding' ? '보유' : '관심'}
                      </Text>
                    </View>
                    <View style={[st.nb, !n && st.nbZ]}>
                      <Text style={[st.nbT, !n && { color: appColor.ink3 }]}>{n ? `새 소식 ${n}` : '새 소식 없음'}</Text>
                    </View>
                  </Pressable>
                );
              })}
            </View>
          </>
        ) : (
          <Text style={st.none}>{`내 종목에 "${t}"이 없어요\n종목은 내 종목 탭에서 추가해요`}</Text>
        )}
        <Text style={st.tipx}>고르면 그 종목 칩으로 바로 바뀌어요</Text>
      </ScrollView>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: appColor.bg },
  flex: { flex: 1 },
  flexMin: { flex: 1, minWidth: 0 },
  pw: { paddingBottom: 30 },
  lt: { paddingHorizontal: 18, paddingBottom: 10, transformOrigin: 'left top' },
  ltH: { fontSize: 27, lineHeight: 34, fontWeight: '800', letterSpacing: -0.5, color: appColor.ink },
  ltP: { ...ft(13.5), color: appColor.ink2, marginTop: 6 },
  unr: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', marginTop: 10, minHeight: 30, paddingHorizontal: 12, borderRadius: 15, backgroundColor: '#EEE9FB' },
  unrDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#E5484D', marginRight: 6 },
  unrT: { ...ft(13), fontWeight: '700', color: '#5B3BD1' },
  unrB: { fontSize: 13, lineHeight: 17, fontWeight: '700', color: '#5B3BD1' },
  chipsBar: { backgroundColor: appColor.bg, paddingTop: 8, paddingBottom: 12 },
  cin: { paddingHorizontal: 16, gap: 6 },
  cpill: { position: 'absolute', top: 0, height: 36, borderRadius: 18, backgroundColor: '#16171A' },
  chip: { minHeight: 36, paddingHorizontal: 14, borderRadius: 18, flexDirection: 'row', alignItems: 'center', gap: 6 },
  chipOff: { borderWidth: 1, borderColor: '#DADDE2' },
  chipT: { ...ft(14), fontWeight: '600', color: appColor.ink2 },
  chipN: { ...ft(14), fontWeight: '700', color: appColor.ink2, opacity: 0.55, marginLeft: -1 },
  chipC: { minWidth: 18, height: 18, borderRadius: 9, backgroundColor: appColor.red, paddingHorizontal: 5, alignItems: 'center', justifyContent: 'center' },
  chipCT: { fontSize: 11, lineHeight: 13, fontWeight: '700', color: '#FFFFFF' },
  tch: { paddingVertical: 10 },
  uc: { backgroundColor: '#FFFFFF', borderRadius: 22, marginHorizontal: 16, marginBottom: 12, paddingTop: 14, paddingHorizontal: 16, paddingBottom: 6 },
  hd: { flexDirection: 'row', alignItems: 'center', gap: 11, paddingBottom: 8 },
  nmRow: { flexDirection: 'row', alignItems: 'center' },
  nm: { flexShrink: 1, ...ft(16), fontWeight: '800', color: appColor.ink },
  own: { marginLeft: 6, borderRadius: 6, backgroundColor: '#EEE9FB', paddingHorizontal: 7, paddingVertical: 2 },
  ownT: { ...ft(11), fontWeight: '700', color: '#5B3BD1' },
  code: { ...ft(12), color: appColor.ink3, marginTop: 1 },
  lr: { flexDirection: 'row', alignItems: 'center', gap: 9, paddingVertical: 11, borderTopWidth: 1, borderTopColor: '#F0F1F4' },
  tg: { borderRadius: 7, paddingHorizontal: 7, paddingVertical: 3 },
  tgT: { ...ft(11.5), fontWeight: '700' },
  tt: { flex: 1, minWidth: 0, ...ft(14), color: appColor.ink },
  ag: { ...ft(12), color: appColor.ink3 },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: appColor.accent },
  nv: { ...ft(13), color: appColor.ink3 },
  more: { paddingTop: 10, paddingBottom: 8, borderTopWidth: 1, borderTopColor: '#F0F1F4', alignItems: 'center' },
  moreT: { ...ft(13), fontWeight: '700', color: appColor.deepPurple },
  sc: { backgroundColor: '#FFFFFF', borderRadius: 22, marginHorizontal: 16, padding: 16, flexDirection: 'row', alignItems: 'center', gap: 12 },
  mb: { marginLeft: 'auto', minHeight: 32, borderRadius: 16, backgroundColor: '#F4F0FF', paddingHorizontal: 12, justifyContent: 'center' },
  mbT: { ...ft(13), fontWeight: '700', color: appColor.deepPurple },
  sub2: { flexDirection: 'row', alignItems: 'center', paddingTop: 12, paddingHorizontal: 20 },
  sub2T: { ...ft(13), color: appColor.ink2 },
  sub2B: { fontSize: 13, lineHeight: 17, fontWeight: '700', color: appColor.deepPurple },
  gh: { ...ft(13), fontWeight: '700', color: appColor.ink2, paddingTop: 12, paddingHorizontal: 20, paddingBottom: 7 },
  swWrap: { marginHorizontal: 16, marginBottom: 8, borderRadius: 18, overflow: 'hidden', backgroundColor: appColor.accent },
  act: { position: 'absolute', right: 0, top: 0, bottom: 0, width: 88, alignItems: 'center', justifyContent: 'center', gap: 3 },
  actT: { ...ft(12.5), fontWeight: '700', color: '#FFFFFF' },
  fin: { alignItems: 'center', gap: 8, paddingTop: 22, paddingBottom: 10 },
  finT: { ...ft(13), color: appColor.ink3 },
  disc: { ...ft(12, 1.6), color: '#8A8F98', textAlign: 'center', paddingTop: 6, paddingHorizontal: 24, paddingBottom: 28 },
  emp: { alignItems: 'center', paddingTop: 40, paddingHorizontal: 30, paddingBottom: 20 },
  empH: { ...ft(17), fontWeight: '700', color: appColor.ink, marginTop: 18, marginBottom: 6, textAlign: 'center' },
  empP: { ...ft(13.5, 1.7), color: appColor.ink2, textAlign: 'center', marginBottom: 18 },
  cta: { minHeight: 46, paddingHorizontal: 22, borderRadius: 14, backgroundColor: appColor.accent, justifyContent: 'center' },
  ctaT: { ...ft(15), fontWeight: '800', color: '#FFFFFF' },
  nudge: { position: 'absolute', left: 16, right: 16, alignItems: 'center' },
  snack: { position: 'absolute', left: 14, right: 14, bottom: 16 },
  sbx: { height: 56, flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 6, paddingRight: 10 },
  sbxL: { flex: 1, height: 42, borderRadius: 12, backgroundColor: '#E9EAEE', flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12 },
  sbxIn: { flex: 1, minWidth: 0, ...ft(15), color: appColor.ink, paddingVertical: 0 },
  cx: { paddingVertical: 8, paddingHorizontal: 6 },
  cxT: { ...ft(15), fontWeight: '700', color: appColor.deepPurple },
  ssp: { paddingTop: 4, paddingHorizontal: 16, paddingBottom: 20 },
  sh3: { ...ft(12.5), fontWeight: '700', color: appColor.ink3, marginVertical: 8, marginHorizontal: 4 },
  gp: { backgroundColor: '#FFFFFF', borderRadius: 18, overflow: 'hidden' },
  rw: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, paddingHorizontal: 14 },
  rwLine: { borderTopWidth: 1, borderTopColor: '#F0F1F4' },
  rwB: { ...ft(15), fontWeight: '700', color: appColor.ink },
  rwS: { ...ft(12.5), color: appColor.ink3 },
  nb: { marginLeft: 'auto', borderRadius: 10, backgroundColor: '#E5484D', paddingHorizontal: 8, paddingVertical: 1 },
  nbZ: { backgroundColor: '#F1F2F4' },
  nbT: { ...ft(12.5), fontWeight: '800', color: '#FFFFFF' },
  none: { textAlign: 'center', paddingVertical: 30, paddingHorizontal: 10, ...ft(13.5, 1.7), color: appColor.ink3 },
  tipx: { ...ft(12, 1.6), color: appColor.ink3, textAlign: 'center', marginTop: 12 },
});
