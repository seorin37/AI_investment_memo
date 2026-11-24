import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';
import { AnimatedText, Text, TextInput } from '@/components/ui/AppText';
import type { Checklist } from '@/types/models';
import { CheckGlyph, CtaChevron, PlugGlyph, WIDGET_META, WidgetGlyph } from '@/ui/icons/HomeGlyphs';
import { CountUp, Odometer } from '@/ui/motion/Numbers';
import { Skeleton } from '@/ui/motion/Skeleton';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { useProgress } from '@/ui/motion/useProgress';
import { StockLogo } from '@/ui/shared/StockLogo';
import { appColor, curve, ft } from '@/ui/theme';
import type { HomeNewsItem, HomeUpdateRow, HomeWidget, MarketIndex } from '../Home.types';
import { APP_SPARK_N, ago, basisText, hm, mmdd, nf, spark } from '../homeFormat';
import { PopBurst } from '@/components/motion/Celebrate';

/* 원본 home.html confetti 색 */
const CONF = ['#8569E3', '#FFC800', '#E5484D', '#2FAE68', '#3D73F0'] as const;

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

/* ───────── 공통: 위젯 머리 (원본 .wt: 17px 700 · 사이 10 · 아래 14 · .bx 32 라운드 10) ───────── */
export function WidgetTitle({ id, title, right }: { id: HomeWidget; title: string; right?: React.ReactNode }) {
  return (
    <View style={st.wt}>
      <View style={[st.bx, { backgroundColor: WIDGET_META[id].bg }]}>
        <WidgetGlyph id={id} />
      </View>
      <Text style={st.wtT}>{title}</Text>
      {right ? <View style={st.wtR}>{right}</View> : null}
    </View>
  );
}

/* ───────── 인사 카드 (원본 .w.fixed: 165deg #EFF0F3 → #E3E5EA · 고정) ───────── */
export function HeroCard({ name, total, counts, editing, ready, onCta }: { name: string; total: number; counts: { holding: number; watching: number; ai_memos: number }; editing: boolean; ready: boolean; onCta: () => void }) {
  const [sz, setSz] = useState({ w: 0, h: 0 });
  return (
    <View style={[st.hero, editing && { opacity: 0.6 }]} onLayout={(e) => setSz({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })}>
      <Svg style={StyleSheet.absoluteFill} width={sz.w} height={sz.h}>
        <Defs>
          <LinearGradient id="homeHero" x1="0.371" y1="0.017" x2="0.629" y2="0.983">
            <Stop offset="0" stopColor="#EFF0F3" />
            <Stop offset="1" stopColor="#E3E5EA" />
          </LinearGradient>
        </Defs>
        <Rect x={0} y={0} width={sz.w} height={sz.h} fill="url(#homeHero)" />
      </Svg>
      <View style={st.wb}>
        {editing ? <Text style={st.note}>고정 · 이동할 수 없어요</Text> : null}
        {!ready ? (
          <View>
            <Skeleton style={{ width: 120, height: 12 }} />
            <Skeleton style={{ width: 220, height: 22, marginVertical: 10 }} />
            <Skeleton style={{ height: 58 }} radius={14} />
          </View>
        ) : (
          <>
            <Text style={st.hg}>안녕하세요, {name}님</Text>
            {total ? (
              <View style={st.htBox}>
                <Text style={st.ht}>오늘 내 생각에</Text>
                <View style={st.htRow}>
                  <Text style={st.ht}>붙은 소식 </Text>
                  <Odometer value={total} style={st.htOdo} />
                  <Text style={st.ht}>건</Text>
                </View>
              </View>
            ) : (
              <View style={st.htBox}>
                <Text style={st.ht}>{'오늘은 내 생각에\n붙은 새 소식이 없어요'}</Text>
                <Text keepAll style={st.htSub}>AI가 매일 확인하고 있어요. 새 소식이 오면 알려 드릴게요.</Text>
              </View>
            )}
            <View style={st.stats}>
              {(
                [
                  ['보유', counts.holding],
                  ['관심', counts.watching],
                  ['AI 메모', counts.ai_memos],
                ] as const
              ).map(([l, n]) => (
                <View key={l} style={st.st}>
                  <Text style={st.stS}>{l}</Text>
                  <CountUp to={n} style={st.stB} duration={600} />
                </View>
              ))}
            </View>
            <Pressable onPress={onCta} accessibilityRole="button" style={({ pressed }) => [st.cta2, pressed && { opacity: 0.85 }]}>
              <Text style={st.cta2T}>업데이트 확인하기</Text>
              <CtaChevron />
            </Pressable>
          </>
        )}
      </View>
    </View>
  );
}

/* ───────── 시장 한눈에 보기 (원본 .mk3: 3칸 · 사이 10 · .mc 104×46 선) ───────── */
function MarketCell({ q, draw, onPress }: { q: MarketIndex; draw: boolean; onPress: () => void }) {
  const [w, setW] = useState(104);
  const arr = q.closes.slice(-APP_SPARK_N);
  const s = spark(arr, w, 46);
  const col = q.change < 0 ? appColor.down : appColor.up;
  /* 원본 .ln: dasharray 300 → 0 (1s ease) */
  const t = useProgress(draw, 1000);
  const e = curve.ease(t);
  return (
    <View style={st.mcCol} onLayout={(ev) => setW(Math.max(40, Math.round(ev.nativeEvent.layout.width)))}>
      <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={`${q.name} 자세히`} style={({ pressed }) => [st.mc, pressed && { backgroundColor: '#F4F4F6' }]}>
        <Text style={st.mcS}>{q.name}</Text>
        <Text style={st.mcB} numberOfLines={1}>
          {nf(q.value)}
        </Text>
        <Text style={[st.mcC, { color: col }]} numberOfLines={1}>
          {q.change > 0 ? '+' : ''}
          {nf(q.change)} ({Math.abs(q.pct).toFixed(2)}%)
        </Text>
        <Svg width={w} height={46} style={st.mcSvg}>
          <Path d={s.area} fill={col} opacity={0.1} />
          <Path d={s.d} fill="none" stroke={col} strokeWidth={1.6} strokeDasharray="300" strokeDashoffset={300 * (1 - e)} />
          <Path d={`M0 22H${w}`} stroke="#C9CDD4" strokeDasharray="2 3" />
        </Svg>
        <Text style={st.mcT}>{basisText(q)}</Text>
      </Pressable>
    </View>
  );
}

export function MarketWidget({ indices, ready, draw, onOpen }: { indices: MarketIndex[]; ready: boolean; draw: boolean; onOpen: (k: MarketIndex['key']) => void }) {
  if (!ready)
    return (
      <View style={st.wb}>
        <Skeleton style={{ width: 150, height: 20, marginBottom: 16 }} />
        <View style={st.mk3}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} style={{ flex: 1, height: 96 }} />
          ))}
        </View>
      </View>
    );
  return (
    <View style={st.wb}>
      <WidgetTitle id="market" title="시장 한눈에 보기" />
      <View style={st.mk3}>
        {indices.map((q) => (
          <MarketCell key={q.key} q={q} draw={draw} onPress={() => onOpen(q.key)} />
        ))}
      </View>
    </View>
  );
}

/** 시장 정보 실패 (원본 #090: 플러그 · 5초 뒤 자동 다시 시도 · 누르면 플러그가 꽂히며 복구) */
export function MarketFail({ onRetry }: { onRetry: () => void }) {
  const k = useMotionK();
  const [ring] = useState(() => new Animated.Value(0));
  const [plug] = useState(() => new Animated.Value(0));
  const [shift, setShift] = useState(0);
  const [go, setGo] = useState(0);
  useEffect(() => {
    const id = plug.addListener(({ value }) => setShift(value));
    return () => plug.removeListener(id);
  }, [plug]);
  useEffect(() => {
    const a = Animated.timing(ring, { toValue: 44, duration: 5000 * k, easing: Easing.linear, useNativeDriver: false });
    a.start(({ finished }) => finished && setGo((n) => n + 1));
    return () => a.stop();
  }, [ring, k]);
  useEffect(() => {
    if (!go) return;
    ring.stopAnimation();
    const a = Animated.timing(plug, { toValue: 10, duration: 500 * k, easing: curve.spring, useNativeDriver: false });
    a.start(({ finished }) => finished && onRetry());
    return () => a.stop();
  }, [go, ring, plug, k, onRetry]);
  return (
    <View style={st.wb}>
      <WidgetTitle id="market" title="시장 한눈에 보기" />
      <View style={st.err}>
        <View style={st.plug}>
          <PlugGlyph shift={shift} />
        </View>
        <Text style={st.errT}>시장 정보를 불러오지 못했어요</Text>
        <Pressable onPress={() => setGo((n) => n + 1)} accessibilityRole="button" style={({ pressed }) => [st.retry, pressed && { opacity: 0.85 }]}>
          <Svg width={18} height={18} viewBox="0 0 18 18">
            <Circle cx={9} cy={9} r={7} fill="none" stroke="rgba(106,66,171,0.2)" strokeWidth={2.4} />
            <AnimatedCircle cx={9} cy={9} r={7} fill="none" stroke={appColor.deepPurple} strokeWidth={2.4} strokeLinecap="round" strokeDasharray="44" strokeDashoffset={ring} transform="rotate(-90 9 9)" />
          </Svg>
          <Text style={st.retryT}>다시 시도 · 5초 뒤 자동</Text>
        </Pressable>
      </View>
    </View>
  );
}

/* ───────── 업데이트 (원본 .ur: #F6F7F9 · 라운드 16 · 안쪽 12 · 위 8 · 로고 40 라운드 11) ───────── */
function NewBadge({ n, bye }: { n: number; bye: boolean }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(1));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: bye ? 0 : 1, duration: 350 * k, easing: curve.spring, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [bye, v, k]);
  return (
    <Animated.View style={[st.nb, { transform: [{ scale: v }] }]}>
      <Text style={st.nbT}>{n}</Text>
    </Animated.View>
  );
}

export function UpdatesWidget({ rows, ready, editing, onAll, onRow }: { rows: HomeUpdateRow[]; ready: boolean; editing: boolean; onAll: () => void; onRow: (code: string) => void }) {
  const [bye, setBye] = useState<string[]>([]);
  if (!ready)
    return (
      <View style={st.wb}>
        <Skeleton style={{ width: 110, height: 20, marginBottom: 12 }} />
        <Skeleton style={{ height: 62, marginTop: 8 }} radius={16} />
        <Skeleton style={{ height: 62, marginTop: 8 }} radius={16} />
      </View>
    );
  return (
    <View style={st.wb}>
      <WidgetTitle
        id="updates"
        title="업데이트"
        right={
          <Pressable onPress={() => !editing && onAll()} accessibilityRole="button" hitSlop={8}>
            <Text style={st.more}>전체 보기 ›</Text>
          </Pressable>
        }
      />
      {rows.map((u, i) => (
        <Pressable
          key={u.stock_code}
          onPress={() => {
            if (editing) return;
            setBye((b) => [...b, u.stock_code]);
            onRow(u.stock_code);
          }}
          accessibilityRole="button"
          style={({ pressed }) => [st.ur, i === 0 && { marginTop: 0 }, pressed && { transform: [{ scale: 0.98 }] }]}
        >
          <StockLogo logo={u.logo} bg={u.logo_bg} ink={u.logo_ink} size={40} variant="app" />
          <View style={st.urMid}>
            <Text style={st.urB} numberOfLines={1}>
              {u.name}
            </Text>
            <Text style={st.urS} numberOfLines={1}>
              {u.status === 'holding' ? '보유' : '관심'} · {u.new_count ? `새 업데이트 ${u.new_count}건` : '모두 확인했어요'}
            </Text>
          </View>
          {u.new_count ? <NewBadge n={u.new_count} bye={bye.includes(u.stock_code)} /> : <Text style={st.urChev}>›</Text>}
        </Pressable>
      ))}
    </View>
  );
}

/* ───────── 뉴스 (원본 .nf 머리 기사 + .nr 줄 4개) ───────── */
export function NewsWidget({ items, day, total, now, ready, editing, onOpen }: { items: HomeNewsItem[]; day: string; total: number; now: string; ready: boolean; editing: boolean; onOpen: (n: HomeNewsItem) => void }) {
  if (!ready)
    return (
      <View style={st.wb}>
        <Skeleton style={{ width: 90, height: 20, marginBottom: 12 }} />
        <Skeleton style={{ height: 96 }} radius={16} />
        <Skeleton style={{ height: 14, marginTop: 16 }} />
        <Skeleton style={{ height: 14, marginTop: 16, width: '80%' }} />
      </View>
    );
  const head = items[0];
  const rows = items.slice(1, 5);
  const open = (n: HomeNewsItem) => !editing && onOpen(n);
  return (
    <View style={st.wb}>
      <WidgetTitle id="news" title="뉴스" right={<Text style={st.ckp}>{`${mmdd(day)} · ${total}건`}</Text>} />
      {head ? (
        <Pressable onPress={() => open(head)} accessibilityRole="link" style={({ pressed }) => [st.nf, pressed && { opacity: 0.9 }]}>
          <View style={st.nfTop}>
            <View style={st.src}>
              <Text style={st.srcT}>{head.src}</Text>
            </View>
            <Text style={st.nfTm}>
              {hm(head.at)} · {ago(head.at, now)}
            </Text>
          </View>
          <Text style={st.nfB}>{head.title}</Text>
          <Text style={st.nfO}>원문 읽기 ↗</Text>
        </Pressable>
      ) : null}
      {rows.map((n, i) => (
        <Pressable key={n.id} onPress={() => open(n)} accessibilityRole="link" style={({ pressed }) => [st.nr, i === rows.length - 1 && { borderBottomWidth: 0 }, pressed && { opacity: 0.7 }]}>
          <Text style={st.nrT}>{n.at.slice(0, 10) === day ? hm(n.at) : mmdd(n.at)}</Text>
          <View style={st.nrMid}>
            <Text style={st.nrB}>{n.title}</Text>
            <Text style={st.nrS}>{n.src}</Text>
          </View>
          <Text style={st.nrAr}>↗</Text>
        </Pressable>
      ))}
    </View>
  );
}

/* ───────── 체크리스트 (원본 #014 #093: 진행 막대 · 동그라미가 차고 글자에 줄) ───────── */
function CheckRow({ text, done, isNew, onPress, burst = 0 }: { text: string; done: boolean; isNew: boolean; onPress: () => void; burst?: number }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(done ? 1 : 0));
  const [inV] = useState(() => new Animated.Value(isNew ? 0 : 1));
  const [tw, setTw] = useState(0);
  useEffect(() => {
    const a = Animated.timing(v, { toValue: done ? 1 : 0, duration: 350 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [done, v, k]);
  useEffect(() => {
    const a = Animated.timing(inV, { toValue: 1, duration: 400 * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [inV, k]);
  const scale = v.interpolate({ inputRange: [0, 1], outputRange: [1, 1.08] });
  return (
    <Animated.View style={{ opacity: inV, transform: [{ translateY: inV.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }) }] }}>
      <Pressable onPress={onPress} accessibilityRole="checkbox" accessibilityState={{ checked: done }} style={st.ci}>
        <Animated.View style={[st.cc, { backgroundColor: v.interpolate({ inputRange: [0, 1], outputRange: ['rgba(133,105,227,0)', appColor.accent] }), borderWidth: v.interpolate({ inputRange: [0, 0.3, 1], outputRange: [2, 0, 0] }), transform: [{ scale }] }]}>
          <Animated.View style={{ opacity: v.interpolate({ inputRange: [0, 0.3, 1], outputRange: [0, 1, 1] }) }}>
            <CheckGlyph />
          </Animated.View>
          {/* 마지막 항목을 끝내면 그 자리에서 26조각 (원본 home.html toggleCk → confetti) */}
          <PopBurst fire={burst} colors={CONF} />
        </Animated.View>
        <View style={st.txWrap}>
          <AnimatedText style={[st.tx, { color: v.interpolate({ inputRange: [0, 1], outputRange: [appColor.ink, appColor.ink3] }) }]} onLayout={(e) => setTw(e.nativeEvent.layout.width)}>
            {text}
          </AnimatedText>
          <Animated.View pointerEvents="none" style={[st.strike, { width: v.interpolate({ inputRange: [0, 0.3, 1], outputRange: [0, 0, tw] }) }]} />
        </View>
      </Pressable>
    </Animated.View>
  );
}

export function CheckWidget({ cl, editing, onToggle, onAdd }: { cl: Checklist | null; editing: boolean; onToggle: (id: string) => void; onAdd: (text: string) => void }) {
  const k = useMotionK();
  const items = cl?.items ?? [];
  const d = items.filter((c) => c.done).length;
  const all = items.length > 0 && d === items.length;
  const [bar] = useState(() => new Animated.Value(items.length ? d / items.length : 0));
  const [yay] = useState(() => new Animated.Value(all ? 1 : 0));
  const [adding, setAdding] = useState(false);
  const [val, setVal] = useState('');
  const [seen] = useState(() => items.map((c) => c.id));
  const [burst, setBurst] = useState<{ id: string; n: number } | null>(null);
  const toggle = (id: string) => {
    const willAll = items.length > 0 && items.every((c) => (c.id === id ? !c.done : c.done));
    if (willAll) setBurst((b) => ({ id, n: (b?.n ?? 0) + 1 }));
    onToggle(id);
  };
  useEffect(() => {
    const a = Animated.parallel([
      Animated.timing(bar, { toValue: items.length ? d / items.length : 0, duration: 450 * k, easing: curve.ease, useNativeDriver: false }),
      Animated.timing(yay, { toValue: all ? 1 : 0, duration: 300 * k, easing: curve.ease, useNativeDriver: false }),
    ]);
    a.start();
    return () => a.stop();
  }, [d, items.length, all, bar, yay, k]);
  return (
    <View style={st.wb}>
      <WidgetTitle id="check" title="체크리스트" right={<Text style={st.ckp}>{`${d} / ${items.length} 완료`}</Text>} />
      <View style={st.pbar}>
        <Animated.View style={[st.pbarI, { width: bar.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] }) }]} />
      </View>
      {items.map((c) => (
        <CheckRow key={c.id} text={c.text} done={c.done} isNew={!seen.includes(c.id)} onPress={() => !editing && toggle(c.id)} burst={burst?.id === c.id ? burst.n : 0} />
      ))}
      <Animated.View style={{ height: yay.interpolate({ inputRange: [0, 1], outputRange: [0, 24] }), overflow: 'hidden' }}>
        <Text style={st.yay}>오늘 할 일을 다 했어요</Text>
      </Animated.View>
      {adding ? (
        <View style={st.cadd}>
          <View style={[st.cc, { borderWidth: 2 }]} />
          <TextInput
            autoFocus
            value={val}
            onChangeText={setVal}
            placeholder="할 일을 적고 Enter"
            placeholderTextColor={appColor.ink3}
            returnKeyType="done"
            submitBehavior="submit"
            onSubmitEditing={() => {
              const t = val.trim();
              if (t) {
                onAdd(t);
              }
              setVal('');
              setAdding(false);
            }}
            onBlur={() => setAdding(false)}
            style={st.caddIn}
          />
        </View>
      ) : (
        <Pressable onPress={() => !editing && setAdding(true)} accessibilityRole="button" style={st.cadd}>
          <Text style={st.caddT}>+ 항목 추가</Text>
        </Pressable>
      )}
    </View>
  );
}

/* ───────── 위젯 겉 (원본 .w: 흰 바탕 · 라운드 22) ───────── */
export function WidgetShell({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[st.w, style]}>{children}</View>;
}

const st = StyleSheet.create({
  w: { backgroundColor: appColor.surface, borderRadius: 22 },
  wb: { paddingTop: 18, paddingHorizontal: 18, paddingBottom: 16 },
  wt: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 14 },
  bx: { width: 32, height: 32, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  wtT: { ...ft(17), fontWeight: '700', color: appColor.ink },
  wtR: { marginLeft: 'auto' },
  more: { ...ft(13), fontWeight: '700', color: appColor.deepPurple },
  ckp: { ...ft(13), fontWeight: '500', color: appColor.ink3 },
  /* 인사 카드 */
  hero: { borderRadius: 22, overflow: 'hidden', backgroundColor: '#E9EBEF' },
  note: { position: 'absolute', right: 14, top: 12, ...ft(11.5), color: appColor.ink3 },
  hg: { ...ft(13), color: appColor.ink2 },
  htBox: { marginTop: 4, marginBottom: 14 },
  ht: { ...ft(21, 1.4), fontWeight: '800', color: appColor.ink },
  htSub: { ...ft(13), color: appColor.ink2, marginTop: 4 },
  htRow: { flexDirection: 'row', alignItems: 'center' },
  htOdo: { fontSize: 21, fontWeight: '800', color: appColor.ink },
  stats: { flexDirection: 'row', gap: 8 },
  st: { flex: 1, backgroundColor: appColor.surface, borderRadius: 14, paddingVertical: 10, paddingHorizontal: 12 },
  stS: { ...ft(12), color: appColor.ink3 },
  stB: { ...ft(20), fontWeight: '700', color: appColor.ink, marginTop: 2 },
  cta2: { alignSelf: 'flex-start', marginTop: 14, minHeight: 38, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 19, backgroundColor: appColor.ink, flexDirection: 'row', alignItems: 'center', gap: 4 },
  cta2T: { ...ft(13.5), fontWeight: '700', color: '#FFFFFF' },
  /* 시장 */
  mk3: { flexDirection: 'row', gap: 10 },
  mcCol: { flex: 1, minWidth: 0 },
  mc: { marginHorizontal: -6, marginVertical: -6, paddingTop: 6, paddingHorizontal: 6, paddingBottom: 4, borderRadius: 14 },
  mcS: { ...ft(13), color: appColor.ink2 },
  mcB: { ...ft(18), fontWeight: '700', color: appColor.ink, marginTop: 4 },
  mcC: { ...ft(12) },
  mcSvg: { marginTop: 8, overflow: 'visible' },
  mcT: { ...ft(11), color: appColor.ink3, marginTop: 4 },
  err: { alignItems: 'center', paddingTop: 10, paddingBottom: 4 },
  plug: { marginTop: 4, marginBottom: 8 },
  errT: { ...ft(14), color: appColor.ink2, textAlign: 'center' },
  retry: { marginTop: 10, minHeight: 36, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 18, backgroundColor: appColor.accentSoft, flexDirection: 'row', alignItems: 'center', gap: 8 },
  retryT: { ...ft(13.5), fontWeight: '700', color: appColor.deepPurple },
  /* 업데이트 */
  ur: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: appColor.row, borderRadius: 16, padding: 12, marginTop: 8 },
  urMid: { flex: 1, minWidth: 0 },
  urB: { ...ft(15), fontWeight: '700', color: appColor.ink },
  urS: { ...ft(12.5), color: appColor.ink3 },
  urChev: { marginLeft: 'auto', ...ft(15), color: appColor.ink3 },
  nb: { marginLeft: 'auto', width: 24, height: 24, borderRadius: 12, backgroundColor: appColor.red, alignItems: 'center', justifyContent: 'center' },
  nbT: { ...ft(12.5), fontWeight: '700', color: '#FFFFFF' },
  /* 뉴스 */
  nf: { backgroundColor: appColor.row, borderRadius: 16, padding: 14 },
  nfTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  src: { backgroundColor: appColor.surface, borderRadius: 6, paddingVertical: 2, paddingHorizontal: 7 },
  srcT: { ...ft(11.5), fontWeight: '700', color: appColor.ink },
  nfTm: { ...ft(12), color: appColor.deepPurple },
  nfB: { ...ft(16), fontWeight: '700', color: appColor.ink, marginTop: 10, marginBottom: 6 },
  nfO: { ...ft(13), fontWeight: '700', color: appColor.deepPurple },
  nr: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#EEF0F3' },
  nrT: { width: 38, ...ft(12.5), color: appColor.ink3, paddingTop: 2 },
  nrMid: { flex: 1, minWidth: 0 },
  nrB: { fontSize: 14.5, lineHeight: 18.42, fontWeight: '600', color: appColor.ink },
  nrS: { ...ft(12), color: appColor.ink3, marginTop: 4 },
  nrAr: { marginLeft: 'auto', ...ft(14.5), color: appColor.ink2 },
  /* 체크리스트 */
  pbar: { height: 6, borderRadius: 3, backgroundColor: '#EEF0F3', overflow: 'hidden', marginTop: -4, marginBottom: 10 },
  pbarI: { height: '100%', borderRadius: 3, backgroundColor: appColor.accent },
  ci: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 44 },
  cc: { width: 24, height: 24, borderRadius: 12, borderColor: '#C9CDD4', alignItems: 'center', justifyContent: 'center' },
  txWrap: { flexShrink: 1, justifyContent: 'center' },
  tx: { ...ft(14.5) },
  strike: { position: 'absolute', left: 0, top: '52%', height: 1.5, backgroundColor: appColor.ink3 },
  yay: { ...ft(13), fontWeight: '700', color: appColor.deepPurple },
  cadd: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 44 },
  caddT: { ...ft(14), fontWeight: '700', color: appColor.deepPurple },
  caddIn: { flex: 1, ...ft(14.5), color: appColor.ink, borderBottomWidth: 1.5, borderBottomColor: appColor.accent, paddingVertical: 6, paddingHorizontal: 0 },
});
