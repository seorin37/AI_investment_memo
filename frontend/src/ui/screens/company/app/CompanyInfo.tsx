import React, { useEffect, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import type { ChartRange } from '@/types/models';
import { BackChevron } from '@/ui/icons/MemoGlyphs';
import { Skeleton } from '@/ui/motion/Skeleton';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { NudgePill } from '@/ui/shared/NudgePill';
import { PillSeg } from '@/ui/shared/PillSeg';
import { Sheet } from '@/ui/shared/Sheet';
import { AppStockCard } from '@/ui/shared/StockHead';
import { appColor, curve, ft } from '@/ui/theme';
import type { CompanyInfoProps } from '../CompanyInfo.types';
import { HEALTH_KEYS, TERM_TIP, TERMS, appQuoteRows, healthScore, healthVal, mdOf, mmddOf, won, yoyAt, type FinKey, type TermKey } from '../companyFormat';
import { useProgress } from '@/ui/motion/useProgress';
import { CANDLE_H, CandleChart, GrowthChart, ProfitChart, Radar } from './CompanyCharts';
import { useNudge } from '@/store/nudge';

const RANGES: { key: ChartRange; label: string }[] = [
  { key: '1W', label: '1주' },
  { key: '1M', label: '1달' },
  { key: '3M', label: '3달' },
  { key: '1Y', label: '1년' },
];
/* 원본 GCOL (Page 2.5 기업정보 색) */
const GCOL = ['#B9AED8', '#51C38B', '#E8CF7E'];
const GTABS: { key: FinKey; label: string }[] = [
  { key: 'revenue', label: '매출' },
  { key: 'op', label: '영업이익' },
  { key: 'net', label: '순이익' },
];
/* 11.18 결정: 앱 수익성은 ROA 빼고 3개 */
const PROF: { name: string; color: string; key: 'op_margin' | 'net_margin' | 'roe'; term: TermKey }[] = [
  { name: '영업이익률', color: '#16171A', key: 'op_margin', term: 'opm' },
  { name: '순이익률', color: '#3D73F0', key: 'net_margin', term: 'npm' },
  { name: 'ROE', color: '#E5484D', key: 'roe', term: 'roe' },
];

/**
 * 앱 기업정보 (원본 company.html 09.1 · 11.17 웹 통일판)
 * 머리 56 (뒤로 · 이름 18px → 요약 카드가 지나가면 이름 15px + 가격 12px 로 바뀜 · 스크롤하면 아래 선)
 * 요약 카드 · [메모 보드 | 기업정보] · 주가·거래량 (캔들 · 누른 채 훑기 · 1주/1달/3달/1년) · 시세·투자정보 (52주 막대 · 12칸 · ?)
 * 기업 개요 · 재무 [분기] · 성장성 (막대 + 전년 동기 대비 선 · 칸 누르기) · 수익성 (범례 켜고 끄기) · 기업 건전성 (레이더 + 목록) · 출처
 * 카드는 화면에 들어올 때 아래 14에서 올라오고 그때 차트가 그려짐. ? 를 누르면 용어 시트.
 */
export function AppCompanyInfo(p: CompanyInfoProps) {
  const insets = useSafeAreaInsets();
  const { width: W, height: VH } = useWindowDimensions();
  const k = useMotionK();
  const [ready, setReady] = useState(false);
  const [y, setY] = useState(0);
  const [sumH, setSumH] = useState(200);
  const [locked, setLocked] = useState(false);
  const [range, setRange] = useState<ChartRange>('1M');
  const [hover, setHover] = useState<number | null>(null);
  const [gtab, setGtab] = useState(0);
  const [gsel, setGsel] = useState(7);
  const [gpick, setGpick] = useState(false);
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const [term, setTerm] = useState<TermKey | null>(null);
  /* 넛지 닫은 상태는 한 곳(store/nudge)에 — 다시 들어와도 안 뜸 · 사용법 안내 중엔 숨김 */
  const nudgeS = useNudge('info');
  const nudge = nudgeS.show;
  const setNudge = (v: boolean) => {
    if (!v) nudgeS.hide();
  };
  /* 원본 body(skel): 기업정보를 처음 열면 0.65초 뼈대 */
  useEffect(() => {
    const t = setTimeout(() => setReady(true), 650 * k);
    return () => clearTimeout(t);
  }, [k]);

  const cw = W - 32 - 32; // 카드 안쪽 폭 (좌우 16 + 안쪽 16)
  const pr = p.profile;
  const candles = p.candles[range];
  const all = p.quarters;
  const healthKeys = HEALTH_KEYS.filter((h) => p.health[h.key] != null);
  const shown = all.slice(-8);
  const last = shown[shown.length - 1];
  const gkey = GTABS[gtab].key;
  const gv = shown.map((q) => q[gkey]);
  const gi = Math.min(gsel, gv.length - 1);
  const Y = yoyAt(all, gkey, all.length - 8 + gi);
  const termCtx = { p: pr, price: p.stock.price, last, health: p.health };
  const compact = y > sumH - 10;
  const asOf = mmddOf(p.quote_as_of);

  const tab = (
    <PillSeg
      options={[
        { key: 'board', label: '메모 보드' },
        { key: 'company', label: '기업정보' },
      ]}
      value="company"
      onChange={(t) => t === 'board' && p.onChangeTab('board')}
      bg="#E3E5EA"
      pad={4}
      radius={14}
      pillRadius={11}
      height={40}
      fontSize={14.5}
      style={st.seg2}
    />
  );

  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <Header name={p.stock.name} price={p.stock.price} pct={p.stock.change_pct} compact={compact} line={y > 8} onBack={p.onBack} onMore={p.onMore} />
      <ScrollView
        style={st.flex}
        contentContainerStyle={st.content}
        scrollEnabled={!locked}
        onScroll={(e) => setY(e.nativeEvent.contentOffset.y)}
        scrollEventThrottle={16}
        showsVerticalScrollIndicator={false}
      >
        <View style={st.sum} onLayout={(e) => setSumH(e.nativeEvent.layout.height)}>
          <AppStockCard {...p.stock} />
        </View>
        {tab}
        {!ready ? (
          <View>
            {[230, 300, 110].map((h) => (
              <View key={h} style={st.cd}>
                <Skeleton style={{ width: '38%', height: 18, marginBottom: 12 }} radius={8} />
                <Skeleton style={{ height: h - 60 }} radius={8} />
              </View>
            ))}
          </View>
        ) : p.preparing ? (
          <Preparing name={p.stock.name} onBoard={() => p.onChangeTab('board')} />
        ) : (
          <>
            {/* 주가 · 거래량 */}
            <Section i={0} scrollY={y} vh={VH}>
              {(seen) => (
                <View style={st.cd}>
                  <View style={st.h3row}>
                    <Text style={st.h3}>주가 · 거래량</Text>
                    <Text style={st.h3small}>{range === '1Y' ? '주봉' : '일봉'}</Text>
                  </View>
                  <Text style={st.d}>차트를 누른 채 움직이면 그날 시세가 보여요</Text>
                  <View style={st.chw}>
                    <CandleChart candles={candles} width={cw + 4} visible={seen} onHover={setHover} onLock={setLocked} />
                    {hover != null ? (
                      <View style={[st.dchip, { left: Math.max(20, Math.min(cw - 16, ((cw + 4) / candles.length) * hover + (cw + 4) / candles.length / 2)) }]}>
                        <Text style={st.dchipT}>{mdOf(candles[hover].date)}</Text>
                      </View>
                    ) : null}
                  </View>
                  <View style={st.ax}>
                    <Text style={st.axT}>{mdOf(candles[0].date)}</Text>
                    <Text style={st.axT}>{mdOf(candles[candles.length - 1].date)}</Text>
                  </View>
                  <PillSeg options={RANGES} value={range} onChange={setRange} bg="#F1F2F4" pad={3} radius={12} pillRadius={9} height={34} fontSize={13.5} style={{ marginTop: 12 }} />
                  {/* [11.12] 말풍선은 카드 머리를 덮음 (차트를 가리지 않게) */}
                  {hover != null ? <Tip c={candles[hover]} prev={candles[hover - 1]?.close} unit={range === '1Y' ? '주봉' : '일봉'} /> : null}
                </View>
              )}
            </Section>
            {/* 시세 · 투자정보 */}
            <Section i={1} scrollY={y} vh={VH}>
              {(seen) => (
                <View style={st.cd}>
                  <View style={st.h3row}>
                    <Text style={st.h3}>시세 · 투자정보</Text>
                    <Text style={st.h3small}>{asOf} 종가 기준</Text>
                  </View>
                  <View style={st.rng}>
                    <Text style={[st.rngT, { color: appColor.down }]}>52주 최저 {won(pr.week52_low)}</Text>
                    <Text style={[st.rngT, { color: appColor.up }]}>52주 최고 {won(pr.week52_high)}</Text>
                  </View>
                  <RangeBar pos={Math.max(0, Math.min(1, (p.stock.price - pr.week52_low) / (pr.week52_high - pr.week52_low || 1)))} run={seen} />
                  <View style={st.kv}>
                    {appQuoteRows(pr).map(([label, val, tk]) => (
                      <View key={label} style={st.kvCell}>
                        <View style={st.kvL}>
                          <Text style={st.kvLT}>{label}</Text>
                          {tk ? <Q onPress={() => setTerm(tk)} label={label} /> : null}
                        </View>
                        <Text style={st.kvV}>{val}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              )}
            </Section>
            {/* 기업 개요 */}
            <Section i={2} scrollY={y} vh={VH}>
              {() => (
                <View style={st.cd}>
                  <Text style={st.h3}>기업 개요</Text>
                  <Text style={st.ov}>{pr.overview}</Text>
                </View>
              )}
            </Section>
            {/* 재무 머리 */}
            <Section i={3} scrollY={y} vh={VH}>
              {() => (
                <View>
                  <View style={st.fh}>
                    <Text style={st.h2}>재무</Text>
                    <View style={st.fq}>
                      <Text style={st.fqT}>분기</Text>
                    </View>
                  </View>
                  <Text style={st.fsrc}>금융감독원 DART 정기보고서(사업·반기·분기) 기준 · 연결</Text>
                  {p.financial ? <Text style={st.finfo}>금융업은 재무 구조가 달라 매출·이익률·유동비율 같은 지표를 따로 보여 드리지 않아요. 값이 없는 칸은 — 로 보여 드려요</Text> : null}
                </View>
              )}
            </Section>
            {/* 성장성 */}
            <Section i={4} scrollY={y} vh={VH}>
              {(seen) => (
                <View style={st.cd}>
                  <Text style={st.h3}>성장성</Text>
                  <PillSeg
                    options={GTABS.map((g, i) => ({ key: String(i), label: g.label }))}
                    value={String(gtab)}
                    onChange={(i) => {
                      setGtab(Number(i));
                      setGsel(7);
                      setGpick(false);
                    }}
                    bg="#F1F2F4"
                    pad={3}
                    radius={12}
                    pillRadius={9}
                    height={34}
                    fontSize={13.5}
                    style={{ marginVertical: 12 }}
                  />
                  <View style={st.big}>
                    <CountTo key={`${gtab}-${gi}`} to={gv[gi]} run={seen} />
                    {Y.t === 'none' ? null : Y.t === 'pct' ? (
                      <Text style={[st.bigS, { color: Y.v >= 0 ? appColor.up : appColor.down }]}>
                        전년 동기 대비 {Y.v >= 0 ? '+' : ''}
                        {Y.v.toFixed(1)}%
                      </Text>
                    ) : (
                      <Text style={[st.bigS, { color: Y.t === '흑자 전환' ? appColor.up : appColor.down }]}>전년 동기 대비 {Y.t}</Text>
                    )}
                  </View>
                  <Text style={st.cap}>{shown[gi].label} 기준 · 꺾은선 = 전년 같은 분기 대비 증감률</Text>
                  <GrowthChart
                    all={all}
                    k={gkey}
                    color={GCOL[gtab]}
                    width={cw}
                    visible={seen}
                    sel={gi}
                    picked={gpick}
                    emptyText={`이 종목은 ${GTABS[gtab].label}을 공시하지 않아요`}
                    onPick={(i, how) => {
                      /* [11.11] 같은 막대를 다시 누르면 최신 분기로 */
                      if (how === 'tap' && gpick && i === gi) {
                        setGpick(false);
                        setGsel(7);
                      } else {
                        setGpick(true);
                        setGsel(i);
                      }
                    }}
                  />
                </View>
              )}
            </Section>
            {/* 수익성 */}
            <Section i={5} scrollY={y} vh={VH}>
              {(seen) => (
                <View style={st.cd}>
                  <View style={st.h3row}>
                    <Text style={st.h3}>수익성</Text>
                    <Text style={st.h3small}>분기</Text>
                  </View>
                  <View style={st.lg}>
                    {PROF.map((pf) => {
                      const nul = shown.every((q) => q[pf.key] == null);
                      const off = !!hidden[pf.name];
                      return (
                        <View key={pf.name} style={[st.lgBtn, off && { opacity: 0.35 }]}>
                          <Pressable disabled={nul} onPress={() => setHidden((h) => ({ ...h, [pf.name]: !h[pf.name] }))} accessibilityRole="button" accessibilityState={{ selected: !off, disabled: nul }} style={[st.lgBtn, st.lgHit]}>
                            <View style={[st.lgDot, { backgroundColor: pf.color }, nul && { opacity: 0.35 }]} />
                            <Text style={[st.lgT, nul && { color: '#B5B8BF' }]}>
                              {pf.name}
                              {nul ? ' —' : ''}
                            </Text>
                          </Pressable>
                          <Q onPress={() => setTerm(pf.term)} label={pf.name} />
                        </View>
                      );
                    })}
                  </View>
                  <ProfitChart series={PROF.map((pf) => ({ name: pf.name, color: pf.color, values: shown.map((q) => q[pf.key]), hidden: !!hidden[pf.name] }))} labels={shown.map((q) => q.q)} width={cw} visible={seen} />
                </View>
              )}
            </Section>
            {/* 기업 건전성 */}
            <Section i={6} scrollY={y} vh={VH}>
              {(seen) => (
                <View style={st.cd}>
                  <View style={st.h3row}>
                    <Text style={st.h3}>기업 건전성</Text>
                    <Text style={st.h3small}>
                      {p.health_as_of.slice(0, 4)}년 {Number(p.health_as_of.slice(5, 7))}월 기준
                    </Text>
                  </View>
                  {/* 값이 있는 축만 (11-21 결정 ②: 금융사는 부채비율·유보율 두 축 = 선 하나) */}
                  <Radar labels={healthKeys.map((h) => h.k)} scores={healthKeys.map((h) => healthScore(h.key, p.health[h.key]))} width={cw} visible={seen} />
                  <View style={st.hl}>
                    {healthKeys.map((h, i) => (
                      <View key={h.k} style={[st.hli, i === healthKeys.length - 1 && { borderBottomWidth: 0 }]}>
                        <View style={st.kvL}>
                          <Text style={st.hliT}>{h.k}</Text>
                          <Q onPress={() => setTerm(h.term)} label={h.k} />
                        </View>
                        <Text style={st.hliV}>{healthVal(h.key, p.health[h.key])}</Text>
                      </View>
                    ))}
                  </View>
                  <Text style={st.note}>바깥쪽으로 갈수록 재무가 안정적이에요.</Text>
                </View>
              )}
            </Section>
            <Text style={st.src}>주가 KIS · 시가총액·상장주수 KRX · 재무 DART · 투자 권유가 아니에요</Text>
          </>
        )}
        <View style={{ height: nudge && p.onNudge ? 76 : 0 }} />
      </ScrollView>
      {nudge && p.onNudge && ready && !p.preparing ? (
        <View style={st.nudgeWrap} pointerEvents="box-none">
          <NudgePill text="공시·재무 읽기 어려우셨죠? 핵심만 정리해 드려요" onGo={p.onNudge} onClose={() => setNudge(false)} />
        </View>
      ) : null}
      <TermSheet k={term} ctx={termCtx} name={p.stock.name} onClose={() => setTerm(null)} />
    </View>
  );
}

/** 머리 (원본 .ph2: 56 · 이름 18px ↔ 이름 15px + 가격 12px 600 · .28s 위아래로 바뀜) */
function Header({ name, price, pct, compact, line, onBack, onMore }: { name: string; price: number; pct: number; compact: boolean; line: boolean; onBack: () => void; onMore?: () => void }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: compact ? 1 : 0, duration: 280 * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [compact, v, k]);
  const up = pct >= 0;
  return (
    <View style={[st.ph2, line && st.ph2Line]}>
      <Pressable onPress={onBack} accessibilityRole="button" accessibilityLabel="뒤로" style={st.ib}>
        <BackChevron />
      </Pressable>
      <View style={st.tt}>
        <Animated.View style={[st.ttIn, { opacity: v.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }), transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [0, -40] }) }] }]}>
          <Text style={st.ttB} numberOfLines={1}>
            {name}
          </Text>
        </Animated.View>
        <Animated.View style={[st.ttIn, st.mini, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [40, 0] }) }] }]}>
          <Text style={st.miniB} numberOfLines={1}>
            {name}
          </Text>
          <Text style={[st.miniS, { color: up ? appColor.up : appColor.down }]}>
            {won(price)}원 {up ? '+' : ''}
            {pct.toFixed(2)}%
          </Text>
        </Animated.View>
      </View>
      <Pressable onPress={onMore} accessibilityRole="button" accessibilityLabel="종목 메뉴" style={st.ib}>
        <Svg width={20} height={20} viewBox="0 0 24 24" fill="#16171A">
          <Circle cx={12} cy={5.5} r={2} />
          <Circle cx={12} cy={12} r={2} />
          <Circle cx={12} cy={18.5} r={2} />
        </Svg>
      </Pressable>
    </View>
  );
}

/** 화면에 들어오면 한 번 보여 줌 (원본 .rv: 아래 14 → 제자리 .45s · 처음 셋은 70ms 차례) */
function Section({ i, scrollY, vh, children }: { i: number; scrollY: number; vh: number; children: (seen: boolean) => React.ReactNode }) {
  const k = useMotionK();
  const [top, setTop] = useState<number | null>(null);
  const [seen, setSeen] = useState(false);
  if (!seen && top != null && top < scrollY + vh * 0.8) setSeen(true);
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!seen) return;
    const a = Animated.timing(v, { toValue: 1, duration: 450 * k, delay: (i < 3 ? i * 70 : 0) * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [seen, v, k, i]);
  return (
    <Animated.View onLayout={(e) => setTop(e.nativeEvent.layout.y)} style={{ opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [14, 0] }) }] }}>
      {children(seen)}
    </Animated.View>
  );
}

/** ? (원본 .q 11.13: 18 · 라운드 9 · #EEE9FB · #6A42AB 12px 800 · 누르는 칸은 사방 13 더 넓게) */
function Q({ onPress, label }: { onPress: () => void; label: string }) {
  return (
    <Pressable onPress={onPress} hitSlop={13} accessibilityRole="button" accessibilityLabel={`${label} 설명`} style={({ pressed }) => [st.q, pressed && { transform: [{ scale: 0.85 }] }]}>
      <Text style={st.qT}>?</Text>
    </Pressable>
  );
}

/** 52주 막대 (원본 .rbar: 6 · #ECEDF1 · 채움 #C9BEF5 · 점 16 흰 + 테두리 3 #8569E3 · 들어오면 .15s 뒤 .9s 로 현재 위치까지) */
function RangeBar({ pos, run }: { pos: number; run: boolean }) {
  const t = useProgress(run, 1050);
  const e = curve.ease(Math.max(0, Math.min(1, (t * 1050 - 150) / 900)));
  const [w, setW] = useState(0);
  return (
    <View style={st.rbar} onLayout={(ev) => setW(ev.nativeEvent.layout.width)}>
      <View style={[st.rbarFill, { width: w * pos * e }]} />
      <View style={[st.rbarDot, { left: w * pos * e - 8 }]} />
    </View>
  );
}

/** 숫자 굴리기 (원본 countTo #098: .6s · 끝이 느려짐) — 조원 */
function CountTo({ to, run }: { to: number | null; run: boolean }) {
  const t = useProgress(run && to != null, 600);
  if (to == null) return <Text style={st.bigB}>—</Text>;
  const e = 1 - Math.pow(1 - t, 3);
  const v = (to / 10000) * e;
  return <Text style={st.bigB}>{v.toFixed(to / 10000 < 10 ? 2 : 1)}조원</Text>;
}

/** 차트 말풍선 (원본 .tip: 카드 머리를 덮음 · 왼·오른·위 12 · #16171A 라운드 10 · 12px 줄 1.6) */
function Tip({ c, prev, unit }: { c: { date: string; open: number; high: number; low: number; close: number; volume: number }; prev?: number; unit: string }) {
  const p = prev ? ((c.close - prev) / prev) * 100 : 0;
  return (
    <View style={st.tip} pointerEvents="none">
      <Text style={st.tipT}>
        <Text style={st.tipB}>
          {mdOf(c.date)} {unit}
          {'  '}
        </Text>
        종가 {won(c.close)} <Text style={{ color: p < 0 ? '#8FB0FF' : '#FF8A8E' }}>{`${p >= 0 ? '+' : ''}${p.toFixed(2)}%`}</Text>
        {'\n'}시 {won(c.open)} · 고 {won(c.high)} · 저 {won(c.low)} · 거래량 {won(c.volume)}주
      </Text>
    </View>
  );
}

/** 용어 시트 (원본 #336 .tsh: 제목 20 · 풀이 12.5 · 설명 14.5 줄 1.65 · '지금 값' 상자 · 안내 · [확인] 52 #8569E3) */
function TermSheet({ k, ctx, name, onClose }: { k: TermKey | null; ctx: Parameters<(typeof TERMS)['per'][3]>[0]; name: string; onClose: () => void }) {
  const [last, setLast] = useState<TermKey>('per');
  if (k && k !== last) setLast(k);
  const t = TERMS[k ?? last];
  return (
    <Sheet open={!!k} onClose={onClose} label="용어 설명">
      <View style={st.tsh}>
        <Text style={st.tshH}>{t[0]}</Text>
        <Text style={st.tshF}>{t[1] || ' '}</Text>
        <Text style={st.tshP}>{t[2]}</Text>
        <View style={st.now}>
          <Text style={st.nowS}>{name} 지금 값</Text>
          <Text style={st.nowB}>{t[3](ctx)}</Text>
        </View>
        <Text style={st.tip2}>{TERM_TIP}</Text>
        <Pressable onPress={onClose} accessibilityRole="button" style={({ pressed }) => [st.ok, pressed && { transform: [{ scale: 0.97 }] }]}>
          <Text style={st.okT}>확인</Text>
        </Pressable>
      </View>
    </Sheet>
  );
}

/** 시범 종목 밖 (원본 .rdy: 56 #EEE9FB 그림 · 17px 800 · 13.5px 줄 1.65 · [메모 보드로 가기]) */
function Preparing({ name, onBoard }: { name: string; onBoard: () => void }) {
  return (
    <View style={[st.cd, st.rdy]}>
      <View style={st.ri}>
        <Svg width={26} height={26} viewBox="0 0 24 24" fill="none" stroke="#6A42AB" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round">
          <Rect x={3.5} y={4} width={17} height={16} rx={3} />
          <Path d="M7.5 15l3-3.5 2.5 2 3.5-4.5" />
        </Svg>
      </View>
      <Text style={st.rdyB}>{name} 기업정보는 준비 중이에요</Text>
      <Text style={st.rdyP}>
        {'지금은 시범 4종목부터 차트·재무·공시를 보여 드려요.\n'}
        <Text style={{ color: '#9A9EA7' }}>{'삼성전자 · SK하이닉스 · 네이버 · KB금융\n'}</Text>
        {'시세는 위처럼 매일 종가로 볼 수 있고,\n메모는 지금도 남길 수 있어요.'}
      </Text>
      <Pressable onPress={onBoard} accessibilityRole="button" style={st.rdyBtn}>
        <Text style={st.rdyBtnT}>메모 보드로 가기</Text>
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: appColor.bg },
  flex: { flex: 1 },
  content: { paddingBottom: 28 },
  ph2: { height: 56, flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 6, backgroundColor: appColor.bg, zIndex: 2 },
  ph2Line: { borderBottomWidth: 1, borderBottomColor: appColor.line, marginBottom: -1 },
  ib: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  tt: { flex: 1, height: 40, overflow: 'hidden' },
  ttIn: { position: 'absolute', left: 0, top: 0, height: 40, justifyContent: 'center' },
  ttB: { ...ft(18), fontWeight: '700', color: appColor.ink },
  mini: { alignItems: 'flex-start' },
  miniB: { ...ft(15, 1.2), fontWeight: '700', color: appColor.ink },
  miniS: { ...ft(12), fontWeight: '600' },
  sum: { marginTop: 4, marginHorizontal: 16, marginBottom: 14 },
  seg2: { marginHorizontal: 16, marginBottom: 14 },
  cd: { backgroundColor: '#FFFFFF', borderRadius: 22, marginHorizontal: 16, marginBottom: 14, paddingTop: 18, paddingHorizontal: 16, paddingBottom: 16 },
  h3row: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  h3: { ...ft(17), fontWeight: '700', color: appColor.ink },
  h3small: { marginLeft: 'auto', ...ft(12), fontWeight: '500', color: appColor.ink3 },
  d: { ...ft(12), color: appColor.ink3, marginTop: 4, marginBottom: 8 },
  chw: { marginHorizontal: -2, height: CANDLE_H },
  dchip: { position: 'absolute', bottom: -4, transform: [{ translateX: -24 }], backgroundColor: appColor.ink, borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 },
  dchipT: { ...ft(11), fontWeight: '700', color: '#FFFFFF' },
  ax: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  axT: { ...ft(11), color: appColor.ink3 },
  tip: { position: 'absolute', left: 12, right: 12, top: 12, backgroundColor: appColor.ink, borderRadius: 10, paddingVertical: 8, paddingHorizontal: 12, zIndex: 3 },
  tipT: { ...ft(12, 1.6), color: '#FFFFFF' },
  tipB: { fontWeight: '800' },
  rng: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 12 },
  rngT: { ...ft(12) },
  rbar: { height: 6, borderRadius: 3, backgroundColor: '#ECEDF1', marginTop: 10, marginBottom: 16 },
  rbarFill: { position: 'absolute', left: 0, top: 0, bottom: 0, borderRadius: 3, backgroundColor: '#C9BEF5' },
  rbarDot: { position: 'absolute', top: -5, width: 16, height: 16, borderRadius: 8, backgroundColor: '#FFFFFF', borderWidth: 3, borderColor: appColor.accent },
  kv: { flexDirection: 'row', flexWrap: 'wrap', columnGap: 16 },
  kvCell: { width: '47%', flexGrow: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: '#F1F2F4' },
  kvL: { flexDirection: 'row', alignItems: 'center', gap: 4, flexShrink: 1 },
  kvLT: { ...ft(13), color: appColor.ink2 },
  kvV: { ...ft(13.5), fontWeight: '700', color: appColor.ink, fontVariant: ['tabular-nums'] },
  q: { width: 18, height: 18, borderRadius: 9, backgroundColor: appColor.accentSoft, alignItems: 'center', justifyContent: 'center' },
  qT: { ...ft(12, 1), fontWeight: '800', color: appColor.deepPurple },
  ov: { ...ft(14, 1.7), color: appColor.ink, marginTop: 10 },
  fh: { flexDirection: 'row', alignItems: 'center', marginTop: 18, marginHorizontal: 18, marginBottom: 2 },
  h2: { ...ft(19), fontWeight: '700', color: appColor.ink },
  fq: { marginLeft: 6, backgroundColor: appColor.accentSoft, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 2 },
  fqT: { ...ft(13), fontWeight: '700', color: appColor.deepPurple },
  fsrc: { ...ft(11.5), color: appColor.ink3, marginHorizontal: 18, marginBottom: 10 },
  finfo: { backgroundColor: '#EAF1FF', color: appColor.down, ...ft(12.5, 1.55), borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12, marginHorizontal: 16, marginBottom: 12, overflow: 'hidden' },
  big: { flexDirection: 'row', alignItems: 'baseline', gap: 8 },
  bigB: { ...ft(24), fontWeight: '700', color: appColor.ink, letterSpacing: -0.3 },
  bigS: { ...ft(13), fontWeight: '600' },
  cap: { ...ft(11.5), color: appColor.ink3, marginTop: 4, marginBottom: 6 },
  lg: { flexDirection: 'row', flexWrap: 'wrap', columnGap: 12, rowGap: 6, marginTop: 10, marginBottom: 4 },
  lgBtn: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  lgHit: { alignSelf: 'stretch' },
  lgDot: { width: 8, height: 8, borderRadius: 4 },
  lgT: { ...ft(12), color: appColor.ink },
  hl: { marginTop: 10 },
  hli: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: '#F1F2F4' },
  hliT: { ...ft(13.5), color: appColor.ink },
  hliV: { ...ft(13.5), fontWeight: '700', color: appColor.ink, fontVariant: ['tabular-nums'] },
  note: { backgroundColor: '#F4F5F7', borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12, ...ft(12, 1.6), color: appColor.ink3, marginTop: 10, overflow: 'hidden' },
  src: { textAlign: 'center', ...ft(11.5, 1.6), color: appColor.ink3, marginTop: 4, marginHorizontal: 16, marginBottom: 8 },
  nudgeWrap: { position: 'absolute', left: 16, right: 16, bottom: 16, alignItems: 'center' },
  tsh: { paddingTop: 4, paddingHorizontal: 22 },
  tshH: { ...ft(20), fontWeight: '700', color: appColor.ink },
  tshF: { ...ft(12.5), color: appColor.ink3, marginTop: 2, marginBottom: 12 },
  tshP: { ...ft(14.5, 1.65), color: appColor.ink, marginBottom: 14 },
  now: { backgroundColor: '#F4F5F7', borderRadius: 14, paddingVertical: 12, paddingHorizontal: 14, marginBottom: 12 },
  nowS: { ...ft(12), color: appColor.ink3 },
  nowB: { ...ft(16), fontWeight: '700', color: appColor.ink, marginTop: 2, fontVariant: ['tabular-nums'] },
  tip2: { ...ft(12.5, 1.6), color: appColor.ink3, marginBottom: 14 },
  ok: { minHeight: 52, borderRadius: 14, backgroundColor: appColor.accent, alignItems: 'center', justifyContent: 'center', paddingVertical: 14 },
  okT: { ...ft(15.5), fontWeight: '700', color: '#FFFFFF' },
  rdy: { alignItems: 'center', paddingTop: 30, paddingHorizontal: 22, paddingBottom: 26 },
  ri: { width: 56, height: 56, borderRadius: 18, backgroundColor: appColor.accentSoft, alignItems: 'center', justifyContent: 'center', marginBottom: 14 },
  rdyB: { ...ft(17), fontWeight: '800', color: appColor.ink, textAlign: 'center' },
  rdyP: { ...ft(13.5, 1.65), color: '#6B7079', marginTop: 8, marginBottom: 16, textAlign: 'center' },
  rdyBtn: { minHeight: 44, paddingHorizontal: 18, borderRadius: 12, backgroundColor: appColor.ink, justifyContent: 'center' },
  rdyBtnT: { ...ft(14.5), fontWeight: '800', color: '#FFFFFF' },
});
