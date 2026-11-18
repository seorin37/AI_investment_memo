/**
 * 모바일 홈 — 인사 카드(오늘 내 생각에 붙은 소식 N건 · 보유/관심/AI 메모) · 시장 한눈에 보기 · 업데이트 · 뉴스.
 * 체험판 home.html. 위젯 순서 바꾸기·빼기(홈 편집)는 이번 범위 밖.
 * 움직임: 위젯이 차례로 떠오름 · 숫자가 올라감(#098) · 작은 주가 선이 그려짐 · 시장 정보 실패 시 흔들림 + 다시 시도 돌개(#090)
 *        · 당겨서 새로고침(#085) · 아래 검정 알약 넛지(#252) · 버튼 누름 spring
 */
import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import Svg, { Path } from 'react-native-svg';
import { MobileIcon, type MobileIconName } from '@/components/icons/MobileIcons';
import { Appear } from '@/components/motion/Appear';
import { lineLength, useDraw } from '@/components/motion/ChartMotion';
import { CountUp } from '@/components/motion/CountUp';
import { NudgePill } from '@/components/motion/NudgePill';
import { ErrorRetry, usePressScale } from '@/components/motion/StateMotion';
import type { HomeMarketItem, MobileHomeProps } from '@/features/home/MobileHome.types';

const C = {
  appBg: '#F3F4F6',
  card: '#FFFFFF',
  hero: '#ECEEF1',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  up: '#E5484D',
  down: '#2F6BDB',
  dark: '#16171A',
  white: '#FFFFFF',
  row: '#F6F7F9',
  red: '#E5484D',
  accentDeep: '#6A42AB',
  icMarketBg: '#E4ECFF', icMarket: '#3D73F0',
  icUpdBg: '#EEE8FF', icUpd: '#7046F5',
  icNewsBg: '#FFE8E8', icNews: '#E5484D',
  line: '#EEF0F3',
} as const;
const PAD = 16;
const GAP = 14;
const R = { card: 20, inner: 14, btn: 12 };

const fmt = (v: number, d = 2) => v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });

export function MobileHome(p: MobileHomeProps) {
  /** 실패할 때마다 흔들림: 처음 실패 · 다시 시도가 끝났는데 또 실패 */
  const [fails, setFails] = useState(0);
  const wasRetrying = useRef(false);
  useEffect(() => {
    if (p.market_error && (!wasRetrying.current || !p.market_retrying)) setFails((f) => f + 1);
    wasRetrying.current = !!p.market_retrying;
  }, [p.market_error, p.market_retrying]);
  const hero = usePressScale(0.95);
  return (
    <View style={st.root}>
    <ScrollView style={st.root} contentContainerStyle={st.body} onScroll={p.onScroll} scrollEventThrottle={16}
      refreshControl={p.onRefresh ? <RefreshControl refreshing={!!p.refreshing} onRefresh={p.onRefresh} tintColor={C.accentDeep} colors={[C.accentDeep]} /> : undefined}>
      <Appear kind="up" index={0} style={st.hero}>
        <Text style={st.hello}>안녕하세요, {p.user_name}님</Text>
        {p.new_count ? (
          <Text style={st.heroTitle}>오늘 내 생각에{'\n'}붙은 소식 <CountUp value={p.new_count} style={st.heroTitle} />건</Text>
        ) : <Text style={st.heroTitle}>{'오늘은 내 생각에\n붙은 새 소식이 없어요'}</Text>}
        <View style={st.stats}>
          <Stat label="보유" value={p.holding_count} />
          <Stat label="관심" value={p.watching_count} />
          <Stat label="AI 메모" value={p.ai_memo_count} />
        </View>
        <Pressable onPress={p.onOpenUpdates} onPressIn={hero.onPressIn} onPressOut={hero.onPressOut} accessibilityRole="button" style={st.heroHit}>
          <Animated.View style={[st.heroBtn, { transform: [{ scale: hero.scale }] }]}><Text style={st.heroBtnText}>업데이트 확인하기 ›</Text></Animated.View>
        </Pressable>
      </Appear>

      <Appear kind="up" index={1} style={st.card}>
        <WidgetTitle icon="chart" bg={C.icMarketBg} fg={C.icMarket} title="시장 한눈에 보기" />
        {p.market_error ? (
          <ErrorRetry message="시장 정보를 불러오지 못했어요" retrying={!!p.market_retrying} onRetry={p.onRetryMarket} fail_count={fails}
            style={st.err} textStyle={st.errText} buttonStyle={st.retry} buttonTextStyle={st.retryText} iconColor={C.text} />
        ) : (
          <Appear kind="fade" style={st.mk3}>
            {p.market.map((m) => <MarketCell key={m.key} m={m} onPress={() => p.onOpenMarket(m.key)} />)}
          </Appear>
        )}
      </Appear>

      <Appear kind="up" index={2} style={st.card}>
        <WidgetTitle icon="updates" bg={C.icUpdBg} fg={C.icUpd} title="업데이트" right="전체 보기 ›" onRight={p.onOpenUpdates} />
        {p.updates.map((u) => (
          <Pressable key={u.stock_code} style={st.ur} onPress={() => p.onOpenStockUpdates(u.stock_code)} accessibilityRole="button">
            <View style={[st.logo, { backgroundColor: u.logo_bg }]}><Text style={[st.logoText, { color: u.logo_fg ?? C.white }]}>{u.logo_text}</Text></View>
            <View style={st.flex}>
              <Text style={st.urName} numberOfLines={1}>{u.name}</Text>
              <Text style={st.urSub}>{u.status === 'holding' ? '보유' : '관심'} · {u.new_count ? `새 업데이트 ${u.new_count}건` : '모두 확인했어요'}</Text>
            </View>
            {u.new_count > 0 ? <View style={st.nb}><Text style={st.nbText}>{u.new_count}</Text></View> : <MobileIcon name="chevron_right" size={16} color={C.muted} />}
          </Pressable>
        ))}
      </Appear>

      <Appear kind="up" index={3} style={st.card}>
        <WidgetTitle icon="news" bg={C.icNewsBg} fg={C.icNews} title="뉴스" right={`오늘 · ${p.news_total_today}건`} />
        {p.news.map((n, i) => (
          <Pressable key={n.id} style={[st.nr, i === 0 && st.nrFirst]} onPress={() => p.onOpenNews(n.id)} accessibilityRole="link">
            <Text style={st.nrMeta}>{n.source} · {n.time}</Text>
            <Text style={[st.nrTitle, i === 0 && st.nrTitleFirst]} numberOfLines={2}>{n.title}</Text>
            {i === 0 && <Text style={st.nrLink}>원문 읽기 ↗</Text>}
          </Pressable>
        ))}
      </Appear>
    </ScrollView>
    <NudgePill visible={!!p.nudge} text={p.nudge?.text ?? ''} onPress={() => p.nudge?.onPress()} onClose={() => p.nudge?.onClose()} bottom={16} />
    </View>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <View style={st.stat}>
      <Text style={st.statLabel}>{label}</Text>
      <CountUp value={value} style={st.statValue} />
    </View>
  );
}

function WidgetTitle({ icon, bg, fg, title, right, onRight }: { icon: MobileIconName; bg: string; fg: string; title: string; right?: string; onRight?: () => void }) {
  return (
    <View style={st.wt}>
      <View style={[st.wtIc, { backgroundColor: bg }]}><MobileIcon name={icon} size={18} color={fg} /></View>
      <Text style={st.wtText}>{title}</Text>
      {!!right && (onRight ? (
        <Pressable style={st.wtRightBtn} onPress={onRight}><Text style={st.wtRightLink}>{right}</Text></Pressable>
      ) : <Text style={st.wtRight}>{right}</Text>)}
    </View>
  );
}

function MarketCell({ m, onPress }: { m: HomeMarketItem; onPress: () => void }) {
  const up = m.change >= 0;
  const col = up ? C.up : C.down;
  const W = 100, H = 46;
  const mn = Math.min(...m.closes), mx = Math.max(...m.closes);
  const xy = m.closes.map((v, i) => [(i / (m.closes.length - 1)) * W, H - 4 - ((v - mn) / (mx - mn || 1)) * (H - 8)] as [number, number]);
  const pts = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const draw = useDraw(m.closes.join('|'));
  return (
    <Pressable style={st.mc} onPress={onPress} accessibilityRole="button">
      <Text style={st.mcName}>{m.name}</Text>
      <CountUp value={m.value} format={(v) => fmt(v)} from={m.value * 0.97} style={st.mcValue} numberOfLines={1} />
      <Text style={[st.mcChg, { color: col }]} numberOfLines={1}>{up ? '+' : ''}{fmt(m.change)} ({Math.abs(m.change_rate).toFixed(2)}%)</Text>
      <Svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <Path d={`${pts} L${W} ${H} L0 ${H}Z`} fill={col} fillOpacity={0.1} />
        <Path d={pts} stroke={col} strokeWidth={1.4} fill="none" {...draw(lineLength(xy))} />
      </Svg>
      <Text style={st.mcDate}>{m.close_date} 종가</Text>
    </Pressable>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.appBg },
  flex: { flex: 1, minWidth: 0 },
  body: { padding: PAD, gap: GAP, paddingBottom: 40 },
  hero: { backgroundColor: C.hero, borderRadius: R.card, padding: 18 },
  hello: { fontSize: 14, color: C.sub },
  heroTitle: { fontSize: 23, fontWeight: '800', color: C.text, lineHeight: 32, marginTop: 6 },
  stats: { flexDirection: 'row', gap: 8, marginTop: 16 },
  stat: { flex: 1, backgroundColor: C.card, borderRadius: R.inner, padding: 12 },
  statLabel: { fontSize: 12.5, color: C.sub },
  statValue: { fontSize: 22, fontWeight: '800', color: C.text, marginTop: 4 },
  heroHit: { alignSelf: 'flex-start', marginTop: 16 },
  heroBtn: { height: 44, borderRadius: 22, backgroundColor: C.dark, paddingHorizontal: 18, justifyContent: 'center' },
  heroBtnText: { fontSize: 14.5, fontWeight: '800', color: C.white },
  card: { backgroundColor: C.card, borderRadius: R.card, padding: 18 },
  wt: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 14 },
  wtIc: { width: 34, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  wtText: { flex: 1, fontSize: 18, fontWeight: '800', color: C.text },
  wtRight: { fontSize: 12.5, color: C.muted },
  wtRightBtn: { minHeight: 44, justifyContent: 'center' },
  wtRightLink: { fontSize: 13.5, fontWeight: '700', color: C.accentDeep },
  mk3: { flexDirection: 'row', gap: 10 },
  mc: { flex: 1, minWidth: 0 },
  mcName: { fontSize: 13, color: C.sub },
  mcValue: { fontSize: 18, fontWeight: '800', color: C.text, marginTop: 2 },
  mcChg: { fontSize: 12, marginTop: 2, marginBottom: 4 },
  mcDate: { fontSize: 11, color: C.muted, marginTop: 4 },
  err: { alignItems: 'center', paddingVertical: 18, gap: 10 },
  errText: { fontSize: 14, color: C.sub },
  retry: { flexDirection: 'row', alignItems: 'center', gap: 6, height: 44, paddingHorizontal: 16, borderRadius: R.btn, borderWidth: 1, borderColor: C.line },
  retryText: { fontSize: 14, fontWeight: '700', color: C.text },
  ur: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: C.row, borderRadius: 16, padding: 12, marginBottom: 8, minHeight: 62 },
  logo: { width: 38, height: 38, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
  logoText: { fontSize: 15, fontWeight: '800' },
  urName: { fontSize: 15.5, fontWeight: '800', color: C.text },
  urSub: { fontSize: 12.5, color: C.sub, marginTop: 2 },
  nb: { minWidth: 24, height: 24, borderRadius: 12, backgroundColor: C.red, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6 },
  nbText: { fontSize: 12.5, fontWeight: '700', color: C.white },
  nr: { paddingVertical: 12, borderTopWidth: 1, borderTopColor: C.line, minHeight: 44 },
  nrFirst: { borderTopWidth: 0, backgroundColor: C.row, borderRadius: 16, padding: 14, marginBottom: 4 },
  nrMeta: { fontSize: 12, color: C.muted },
  nrTitle: { fontSize: 14.5, fontWeight: '600', color: C.text, marginTop: 3, lineHeight: 21 },
  nrTitleFirst: { fontSize: 16, fontWeight: '800' },
  nrLink: { fontSize: 13, fontWeight: '700', color: C.accentDeep, marginTop: 8 },
});
