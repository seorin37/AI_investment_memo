/**
 * 기업정보 (모바일) — 종목 요약 카드 + [메모 보드 | 기업정보]
 *  주가·거래량(일봉 캔들 + 거래량 막대 · 1주/1달/3달/1년) → 시세·투자정보 → 기업 개요 → 재무 분기(성장성 · 수익성 · 건전성)
 *  시범 4종목 밖이면 "준비 중" 카드.
 * 체험판 company.html — 움직임:
 *  - 캔들이 왼쪽부터 차례로 자라남 · 기간/종류를 바꾸면 다시 (.9s)
 *  - 차트를 옆으로 끌면 가장 가까운 날의 종가 · 거래량 (#096) — 손을 떼면 사라짐
 *  - 기간 · 성장성 칩은 알약이 미끄러짐 (#039 · #047)
 *  - 지표 숫자가 올라가며 보임 (#098) · 막대가 아래에서 자람 · 선이 그려짐(1.2s) · 레이더가 가운데에서 펼쳐짐
 *  - 불러오는 동안 빛줄기 뼈대 (#079)
 */
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import { Text } from '@/components/ui/AppText';
import Svg, { Circle, G, Line, Path, Polygon, Rect, Text as SvgText } from 'react-native-svg';
import type { ChartRange } from '@/types/models';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { StockSummaryCard } from '@/components/mobile/StockSummaryCard';
import { Appear } from '@/components/motion/Appear';
import { lineLength, useDraw, useScrub } from '@/components/motion/ChartMotion';
import { CountUpText } from '@/components/motion/CountUp';
import { EASE, LINEAR, SPRING, useProgress } from '@/components/motion/motion';
import { Shimmer, SkeletonSwap } from '@/components/motion/Skeleton';
import { SlidingPill } from '@/components/motion/SlidingPill';
import type { CompanyCandle, CompanyHealthItem, CompanyOverviewProps, CompanySeries } from '@/features/company/CompanyOverview.types';

const C = {
  appBg: '#F3F4F6',
  card: '#FFFFFF',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  up: '#E5484D',
  down: '#2F6BDB',
  upSoft: 'rgba(229,72,77,0.45)',
  downSoft: 'rgba(47,107,219,0.45)',
  grid: '#F1F2F4',
  segBg: '#F3F4F6',
  white: '#FFFFFF',
  dark: '#16171A',
  accent: '#8569E3',
  accentDeep: '#6A42AB',
  accentSoft: '#EEE9FB',
  bar: '#B9A8DA',
  radarFill: 'rgba(133,105,227,0.18)',
  radarLine: '#DADDE2',
  line: '#EEF0F3',
  cross: '#16171A',
  tip: '#16171A',
  skeleton: '#EEF0F3',
  shadow: '#000000',
} as const;
const PAD = 16;
const GAP = 14;
const R = { card: 20, seg: 12 };
const RANGES: { key: ChartRange; label: string }[] = [{ key: '1W', label: '1주' }, { key: '1M', label: '1달' }, { key: '3M', label: '3달' }, { key: '1Y', label: '1년' }];

export function CompanyOverview(p: CompanyOverviewProps) {
  const [growthKey, setGrowthKey] = useState(p.growth[0]?.key ?? '');
  return (
    <ScrollView style={st.root} contentContainerStyle={st.body}>
      <View style={st.headWrap}><StockSummaryCard stock={p.stock} tab="company" onChangeTab={p.onChangeTab} /></View>

      <SkeletonSwap loading={!!p.loading} skeleton={<CompanySkeleton />}>
      {p.not_ready ? (
        <Appear kind="up" style={[st.card, st.ready]}>
          <View style={st.readyIc}><MobileIcon name="chart" size={26} color={C.accentDeep} /></View>
          <Text style={st.readyTitle}>{p.stock.name} 기업정보는 준비 중이에요</Text>
          <Text style={st.readyText}>지금은 시범 4종목부터 차트·재무·공시를 보여 드려요.{'\n'}삼성전자 · SK하이닉스 · 네이버 · KB금융{'\n'}시세는 위처럼 매일 종가로 볼 수 있고,{'\n'}메모는 지금도 남길 수 있어요.</Text>
          <Pressable style={st.readyBtn} onPress={p.onGoBoard}><Text style={st.readyBtnText}>메모 보드로 가기</Text></Pressable>
        </Appear>
      ) : (
        <>
          <View style={st.card}>
            <View style={st.ch}><Text style={st.cTitle}>주가 · 거래량</Text><Text style={st.cRight}>일봉</Text></View>
            <CandleChart candles={p.candles} replay={`${p.stock.stock_code}|${p.range}`} />
            <SlidingPill items={RANGES} value={p.range} onChange={p.onChangeRange} equal style={st.seg} itemStyle={st.segBtn} pillStyle={st.segOn} textStyle={st.segText} textOnStyle={st.segTextOn} />
          </View>

          <View style={st.card}>
            <View style={st.ch}><Text style={st.cTitle}>시세 · 투자정보</Text><Text style={st.cRight}>{p.stock.close_date} 종가 기준</Text></View>
            <View style={st.w52}><Text style={st.w52Text}>52주 최저 {p.week52_low}</Text><Text style={st.w52Text}>52주 최고 {p.week52_high}</Text></View>
            <View style={st.qGrid}>
              {p.quote_rows.map((q) => (
                <View key={q.label} style={st.qCell}><Text style={st.kvK}>{q.label}</Text><CountUpText text={q.value} style={st.kvV} /></View>
              ))}
            </View>
            <View style={st.mGrid}>
              {p.metrics.map((m) => (
                <View key={m.key} style={st.mCell}>
                  <View style={st.mHead}>
                    <Text style={st.kvK}>{m.label}</Text>
                    {m.has_help && <HelpBtn onPress={() => p.onHelp(m.key)} />}
                  </View>
                  {m.value ? <CountUpText text={m.value} style={st.mVal} /> : <Text style={st.mVal}>—</Text>}
                </View>
              ))}
            </View>
          </View>

          <View style={st.card}>
            <Text style={st.cTitle}>기업 개요</Text>
            <Text style={st.overview}>{p.overview}</Text>
          </View>

          <View style={st.finHead}>
            <Text style={st.finTitle}>재무 <Text style={st.finQ}>분기</Text></Text>
            <Text style={st.finSub}>금융감독원 DART 정기보고서(사업·반기·분기) 기준 · 연결</Text>
          </View>

          <View style={st.card}>
            <Text style={st.cTitle}>성장성</Text>
            <SlidingPill items={p.growth.map((g) => ({ key: g.key, label: g.label }))} value={growthKey} onChange={setGrowthKey} gap={8} hitSlop={6}
              style={st.legend} itemStyle={st.lgBtn} pillStyle={st.lgOn} textStyle={st.lgText} textOnStyle={st.lgTextOn} />
            <BarChart quarters={p.quarters} series={p.growth.find((g) => g.key === growthKey) ?? p.growth[0]} />
          </View>

          <View style={st.card}>
            <View style={st.ch}><Text style={st.cTitle}>수익성</Text><Text style={st.cRight}>분기</Text></View>
            <View style={st.legend}>
              {p.profitability.map((s) => (
                <View key={s.key} style={st.lgItem}>
                  <View style={[st.lgDot, { backgroundColor: s.color }]} />
                  <Text style={[st.lgPlain, s.values.every((v) => v === null) && { color: C.muted }]}>{s.label}</Text>
                  <HelpBtn onPress={() => p.onHelp(s.key)} />
                </View>
              ))}
            </View>
            <LineChart quarters={p.quarters} series={p.profitability} />
          </View>

          <View style={st.card}>
            <View style={st.ch}><Text style={st.cTitle}>기업 건전성</Text><Text style={st.cRight}>{p.health_basis}</Text></View>
            <Radar items={p.health} />
            {p.health.map((h) => (
              <View key={h.key} style={st.hRow}>
                <Text style={st.hLabel}>{h.label}</Text>
                <HelpBtn onPress={() => p.onHelp(h.key)} />
                <View style={st.flex} />
                <CountUpText text={h.value} style={st.hVal} />
              </View>
            ))}
            <Text style={st.foot}>바깥쪽으로 갈수록 재무가 안정적이에요. 화면 예시 수치예요.</Text>
          </View>
          <Text style={st.source}>주가 KIS · 시가총액·상장주수 KRX · 재무 DART · 투자 권유가 아니에요</Text>
        </>
      )}
      </SkeletonSwap>
    </ScrollView>
  );
}

function HelpBtn({ onPress }: { onPress: () => void }) {
  return (
    <Pressable onPress={onPress} hitSlop={13} style={st.help} accessibilityRole="button" accessibilityLabel="설명 보기">
      <Text style={st.helpText}>?</Text>
    </Pressable>
  );
}

function CandleChart({ candles, replay }: { candles: CompanyCandle[]; replay: string }) {
  const W = 340, PH = 170, VH = 60, GAPH = 10;
  const [box, setBox] = useState(0);
  const grow = useProgress(replay, 900, LINEAR);
  const scrub = useScrub(candles.length, box);
  if (!candles.length) return null;
  const n = candles.length;
  const hi = Math.max(...candles.map((c) => c.high)), lo = Math.min(...candles.map((c) => c.low));
  const vmax = Math.max(...candles.map((c) => c.volume));
  const cw = W / n;
  const y = (v: number) => 8 + (PH - 16) * (1 - (v - lo) / (hi - lo || 1));
  const sel = scrub.index === null ? null : candles[scrub.index];
  const selX = scrub.index === null ? 0 : (scrub.index + 0.5) / n;
  return (
    <View>
      <View onLayout={(e: LayoutChangeEvent) => setBox(e.nativeEvent.layout.width)} {...scrub.panHandlers}
        accessibilityLabel={`일봉 차트, ${candles[0].date}부터 ${candles[n - 1].date}까지. 옆으로 끌면 그날 종가를 볼 수 있어요`}>
        <Svg width="100%" height={PH + GAPH + VH} viewBox={`0 0 ${W} ${PH + GAPH + VH}`} preserveAspectRatio="none">
          {[0.25, 0.5, 0.75].map((f) => <Line key={f} x1={0} x2={W} y1={PH * f} y2={PH * f} stroke={C.grid} />)}
          {candles.map((c, i) => {
            /** 왼쪽부터 한 개씩 자라남: 이 캔들의 몫(0~1) */
            const g = EASE(Math.max(0, Math.min(1, grow * (1 + 0.04 * (n - 1)) - i * 0.04)));
            if (g <= 0) return null;
            const up = c.close >= c.open;
            const col = up ? C.up : C.down;
            const x = i * cw + cw / 2;
            const mid = y((c.open + c.close) / 2);
            const top = mid + (y(Math.max(c.open, c.close)) - mid) * g, bot = mid + (y(Math.min(c.open, c.close)) - mid) * g;
            const vh = (c.volume / vmax) * (VH - 4) * g;
            const dim = sel && scrub.index !== i ? 0.35 : 1;
            return (
              <G key={c.date} opacity={dim}>
                <Line x1={x} x2={x} y1={mid + (y(c.high) - mid) * g} y2={mid + (y(c.low) - mid) * g} stroke={col} strokeWidth={1} />
                <Rect x={x - cw * 0.32} y={top} width={cw * 0.64} height={Math.max(1.5, bot - top)} fill={col} />
                <Rect x={x - cw * 0.32} y={PH + GAPH + VH - vh} width={cw * 0.64} height={vh} fill={up ? C.upSoft : C.downSoft} />
              </G>
            );
          })}
          {sel && <Line x1={selX * W} x2={selX * W} y1={0} y2={PH + GAPH + VH} stroke={C.cross} strokeWidth={1} strokeDasharray="3 3" />}
        </Svg>
        {sel && (
          <View pointerEvents="none" style={[st.tipBox, selX > 0.5 ? { right: (1 - selX) * box + 8 } : { left: selX * box + 8 }]}>
            <Text style={st.tipDate}>{sel.date} 종가</Text>
            <Text style={st.tipVal}>{sel.close.toLocaleString('ko-KR')}원</Text>
            <Text style={st.tipSub}>거래량 {sel.volume.toLocaleString('ko-KR')}주</Text>
          </View>
        )}
      </View>
      <View style={st.axis}><Text style={st.axisText}>{candles[0].date}</Text><Text style={st.axisText}>{sel ? '옆으로 끌어 보기' : candles[n - 1].date}</Text></View>
    </View>
  );
}

function CompanySkeleton() {
  return (
    <View style={st.skWrap}>
      <Shimmer style={st.skChart} offset_x={PAD} color={C.skeleton} />
      <Shimmer style={st.skCard} offset_x={PAD} color={C.skeleton} />
      <Shimmer style={st.skCard} offset_x={PAD} color={C.skeleton} />
    </View>
  );
}

function BarChart({ quarters, series }: { quarters: string[]; series?: CompanySeries }) {
  const W = 340, H = 150;
  if (!series) return null;
  const vals = series.values.map((v) => v ?? 0);
  const mx = Math.max(...vals, 1);
  const bw = W / quarters.length;
  return <Bars quarters={quarters} series={series} vals={vals} mx={mx} bw={bw} W={W} H={H} />;
}

/** 막대가 아래에서 차례로 자람 (.7s spring · 고른 지표가 바뀌면 다시) */
function Bars({ quarters, series, vals, mx, bw, W, H }: { quarters: string[]; series: CompanySeries; vals: number[]; mx: number; bw: number; W: number; H: number }) {
  const g = useProgress(series.key, 700, LINEAR);
  return (
    <View>
      <Svg width="100%" height={H + 22} viewBox={`0 0 ${W} ${H + 22}`} preserveAspectRatio="none">
        {vals.map((v, i) => {
          /** 차례로(80ms 차이) 자라며 살짝 넘쳤다 멈춤 · 끝값은 정확히 1 */
          const k = SPRING(Math.max(0, Math.min(1, g * (1 + 0.12 * (vals.length - 1)) - i * 0.12)));
          const h = (v / mx) * (H - 24) * k;
          return (
            <G key={quarters[i]}>
              <Rect x={i * bw + bw * 0.18} y={H - h} width={bw * 0.64} height={h} rx={3} fill={series.color} />
              <SvgText x={i * bw + bw / 2} y={H - h - 5} fontSize={10} fill={C.sub} textAnchor="middle">{series.values[i] === null ? '—' : v.toFixed(1)}</SvgText>
            </G>
          );
        })}
      </Svg>
      <QuarterAxis quarters={quarters} />
      <Text style={st.unit}>단위 조원</Text>
    </View>
  );
}

function LineChart({ quarters, series }: { quarters: string[]; series: CompanySeries[] }) {
  const W = 340, H = 130;
  const draw = useDraw(series.map((q) => q.key).join('|'));
  const dots = useProgress(series.length, 600, EASE, 900);
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== null));
  if (!all.length) return <Text style={st.unit}>값이 없는 지표예요</Text>;
  const mx = Math.ceil(Math.max(...all) / 20) * 20;
  const x = (i: number) => 12 + (i * (W - 24)) / (quarters.length - 1);
  const y = (v: number) => 8 + (H - 16) * (1 - v / (mx || 1));
  return (
    <View>
      <Svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        {[0, 0.5, 1].map((f) => <Line key={f} x1={0} x2={W} y1={y(mx * f)} y2={y(mx * f)} stroke={C.grid} />)}
        {series.map((s) => {
          const pts = s.values.map((v, i) => (v === null ? null : [x(i), y(v)] as const)).filter((q): q is readonly [number, number] => q !== null);
          if (pts.length < 2) return null;
          const d = pts.map((q, i) => `${i ? 'L' : 'M'}${q[0].toFixed(1)} ${q[1].toFixed(1)}`).join(' ');
          return (
            <G key={s.key}>
              <Path d={d} stroke={s.color} strokeWidth={2} fill="none" {...draw(lineLength(pts.map((q) => [q[0], q[1]])))} />
              {pts.map((q, i) => <Circle key={i} cx={q[0]} cy={q[1]} r={3} fill={C.white} stroke={s.color} strokeWidth={1.6} opacity={dots} />)}
            </G>
          );
        })}
      </Svg>
      <QuarterAxis quarters={quarters} />
      <Text style={st.unit}>단위 % · 0 ~ {mx}%</Text>
    </View>
  );
}

function QuarterAxis({ quarters }: { quarters: string[] }) {
  return (
    <View style={st.qAxis}>
      {quarters.map((q) => <Text key={q} style={st.qAxisText} numberOfLines={1}>{q}</Text>)}
    </View>
  );
}

function Radar({ items }: { items: CompanyHealthItem[] }) {
  const S = 220, cx = S / 2, cy = S / 2 + 6, r = 78;
  const n = items.length;
  const pt = (i: number, f: number) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    return [cx + Math.cos(a) * r * f, cy + Math.sin(a) * r * f] as const;
  };
  const g = useProgress(items.map((h) => h.score).join('|'), 800, SPRING, 200);
  const ring = (f: number) => items.map((_, i) => pt(i, f).join(',')).join(' ');
  const sc = (h: CompanyHealthItem) => Math.max(0.08, Math.min(1, h.score)) * g;
  const shape = items.map((h, i) => pt(i, sc(h)).join(',')).join(' ');
  return (
    <View style={st.radarWrap}>
      <Svg width={S} height={S + 12} viewBox={`0 0 ${S} ${S + 12}`}>
        {[1, 0.66, 0.33].map((f) => <Polygon key={f} points={ring(f)} fill="none" stroke={C.radarLine} />)}
        {items.map((_, i) => { const [ex, ey] = pt(i, 1); return <Line key={i} x1={cx} y1={cy} x2={ex} y2={ey} stroke={C.radarLine} />; })}
        <Polygon points={shape} fill={C.radarFill} stroke={C.accent} strokeWidth={2} />
        {items.map((h, i) => { const [px, py] = pt(i, sc(h)); return <Circle key={h.key} cx={px} cy={py} r={3.5} fill={C.accent} />; })}
        {items.map((h, i) => { const [lx, ly] = pt(i, 1.24); return <SvgText key={`t${h.key}`} x={lx} y={ly + 4} fontSize={11} fill={C.sub} textAnchor="middle">{h.label}</SvgText>; })}
      </Svg>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.appBg },
  flex: { flex: 1 },
  body: { paddingBottom: 40, gap: GAP },
  headWrap: { paddingTop: 8, backgroundColor: C.appBg },
  card: { backgroundColor: C.card, borderRadius: R.card, padding: 18, marginHorizontal: PAD },
  ch: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' },
  cTitle: { fontSize: 18, fontWeight: '800', color: C.text },
  cRight: { fontSize: 12.5, color: C.muted },
  seg: { backgroundColor: C.segBg, borderRadius: R.seg, padding: 4, marginTop: 12 },
  segBtn: { height: 36 },
  segOn: { backgroundColor: C.card, borderRadius: 10, shadowColor: C.shadow, shadowOpacity: 0.08, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  segText: { fontSize: 14, color: C.sub },
  segTextOn: { fontWeight: '800', color: C.text },
  axis: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  tipBox: { position: 'absolute', top: 6, backgroundColor: C.tip, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 7 },
  tipDate: { fontSize: 11.5, color: C.muted },
  tipVal: { fontSize: 15, fontWeight: '800', color: C.white, marginTop: 1 },
  tipSub: { fontSize: 11.5, color: C.white, opacity: 0.8, marginTop: 1 },
  skWrap: { gap: GAP, paddingHorizontal: PAD },
  skChart: { height: 300, borderRadius: R.card },
  skCard: { height: 180, borderRadius: R.card },
  axisText: { fontSize: 11, color: C.muted },
  w52: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 12, marginBottom: 6 },
  w52Text: { fontSize: 12.5, color: C.sub },
  qGrid: { flexDirection: 'row', flexWrap: 'wrap', borderTopWidth: 1, borderTopColor: C.line, paddingTop: 6 },
  qCell: { width: '50%', flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, paddingRight: 10 },
  kvK: { fontSize: 13, color: C.sub },
  kvV: { fontSize: 13, fontWeight: '700', color: C.text },
  mGrid: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 8, borderTopWidth: 1, borderTopColor: C.line, paddingTop: 8 },
  mCell: { width: '50%', paddingVertical: 8, paddingRight: 10 },
  mHead: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  mVal: { fontSize: 16, fontWeight: '800', color: C.text, marginTop: 2 },
  help: { width: 18, height: 18, borderRadius: 9, backgroundColor: C.accentSoft, alignItems: 'center', justifyContent: 'center' },
  helpText: { fontSize: 12, fontWeight: '800', color: C.accentDeep },
  overview: { fontSize: 14, lineHeight: 23, color: C.sub, marginTop: 8 },
  finHead: { paddingHorizontal: PAD, marginTop: 6 },
  finTitle: { fontSize: 20, fontWeight: '800', color: C.text },
  finQ: { fontSize: 13, fontWeight: '700', color: C.accentDeep },
  finSub: { fontSize: 12, color: C.muted, marginTop: 4 },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10, marginBottom: 8 },
  lgBtn: { height: 32, paddingHorizontal: 12, borderRadius: 16, backgroundColor: C.segBg },
  lgOn: { backgroundColor: C.dark, borderRadius: 16 },
  lgText: { fontSize: 13, fontWeight: '700', color: C.sub },
  lgTextOn: { color: C.white },
  lgItem: { flexDirection: 'row', alignItems: 'center', gap: 5, minHeight: 32 },
  lgDot: { width: 8, height: 8, borderRadius: 4 },
  lgPlain: { fontSize: 13, color: C.text },
  qAxis: { flexDirection: 'row' },
  qAxisText: { flex: 1, fontSize: 11, color: C.muted, textAlign: 'center' },
  unit: { fontSize: 11, color: C.muted, marginTop: 6, textAlign: 'right' },
  radarWrap: { alignItems: 'center', marginVertical: 6 },
  hRow: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 9, borderTopWidth: 1, borderTopColor: C.line },
  hLabel: { fontSize: 14, color: C.text },
  hVal: { fontSize: 14, fontWeight: '800', color: C.text },
  foot: { fontSize: 12, color: C.muted, marginTop: 8 },
  source: { fontSize: 11.5, color: C.muted, textAlign: 'center', paddingHorizontal: PAD },
  ready: { alignItems: 'center', paddingVertical: 30 },
  readyIc: { width: 56, height: 56, borderRadius: 18, backgroundColor: C.accentSoft, alignItems: 'center', justifyContent: 'center', marginBottom: 14 },
  readyTitle: { fontSize: 17, fontWeight: '800', color: C.text, textAlign: 'center' },
  readyText: { fontSize: 13.5, lineHeight: 22, color: C.sub, textAlign: 'center', marginTop: 8, marginBottom: 16 },
  readyBtn: { height: 44, paddingHorizontal: 18, borderRadius: 12, backgroundColor: C.dark, justifyContent: 'center' },
  readyBtnText: { fontSize: 14.5, fontWeight: '800', color: C.white },
});
