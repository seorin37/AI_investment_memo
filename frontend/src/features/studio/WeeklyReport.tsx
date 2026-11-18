/**
 * AI 주간보고서 — 어두운 표지(종목 1개면 큰 가격 + 폭 전체 주가 선) · 이번 주 한눈에 · (01 증시 핫이슈) · 종목별 흐름 · 출처.
 * 체험판 studio.html 주간보고서 v3. 상단 바(‹ 주간보고서)는 TopBar 로 따로.
 * 움직임: 장마다 차례로 떠오름(rvin 60ms) · 주가 선이 그려지고(1.2s) 소식 번호가 .9초 뒤 나타나며 두 번 톡(hit)
 *        · 숫자가 올라감(#098) · [메모에 추가] → "✓ 추가됨"으로 바뀜(#051)
 */
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, G, Line, Path, Text as SvgText } from 'react-native-svg';
import { AddButton } from '@/components/motion/AddButton';
import { Appear } from '@/components/motion/Appear';
import { lineLength, useDraw } from '@/components/motion/ChartMotion';
import { CountUpText } from '@/components/motion/CountUp';
import { EASE, LINEAR, useProgress } from '@/components/motion/motion';
import type { ReportStock, WeeklyReportProps } from '@/features/studio/WeeklyReport.types';

const C = {
  appBg: '#F3F4F6',
  card: '#FFFFFF',
  coverBg: '#221B33',
  coverCard: 'rgba(255,255,255,0.07)',
  coverLine: 'rgba(255,255,255,0.12)',
  coverText: '#FFFFFF',
  coverSub: '#C9C3D9',
  coverTag: '#B9A8F5',
  coverChip: 'rgba(255,255,255,0.14)',
  coverUp: '#FF6B6B',
  coverDown: '#5B9BFF',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  line: '#EEF0F3',
  up: '#E5484D',
  down: '#2F6BDB',
  accent: '#8569E3',
  accentDeep: '#6A42AB',
  accentSoft: '#EEE9FB',
  evDisc: '#7C5CE0',
  evNews: '#3D73F0',
  dash: '#C9CDD4',
  white: '#FFFFFF',
  statBg: '#F6F7F9',
  doneBg: '#E3F5EA',
  doneText: '#1B7A45',
} as const;
const PAD = 16;
const GAP = 14;
const R = { card: 20, inner: 14 };
const DAYS = ['월', '화', '수', '목', '금'];
const pc = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;

export function WeeklyReport({ week_label, period_label, created_label, summary, stocks, market, sources, onAddWatch, onOpenMemo }: WeeklyReportProps) {
  const one = stocks.length === 1;
  const disc = stocks.reduce((a, s) => a + s.items.filter((i) => i.kind === 'disclosure').length, 0);
  const news = stocks.reduce((a, s) => a + s.items.filter((i) => i.kind === 'news').length, 0);
  const linked = stocks.filter((s) => s.memo_link).length;
  let sec = 0;
  const no = () => String(++sec).padStart(2, '0');

  return (
    <ScrollView style={st.root} contentContainerStyle={st.body}>
      <Appear kind="up" index={0} style={st.cover}>
        <View style={st.coverTop}>
          <Text style={st.coverTag}>MEMO'S WEEKLY REPORT</Text>
          <View style={st.weekChip}><Text style={st.weekText}>{week_label}</Text></View>
        </View>
        <Text style={st.coverTitle}>주간보고서</Text>
        <Text style={st.coverSub}>{period_label} · {stocks.length}종목 · {created_label}</Text>
        {one ? <OneCover s={stocks[0]} /> : (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={st.miniRow}>
            {stocks.map((s) => (
              <View key={s.stock_code} style={st.mini}>
                <View style={st.miniHead}>
                  <View style={[st.miniLogo, { backgroundColor: s.logo_bg }]}><Text style={[st.miniLogoText, { color: s.logo_fg ?? C.white }]}>{s.logo_text}</Text></View>
                  <Text style={st.miniName} numberOfLines={1}>{s.name}</Text>
                </View>
                <Text style={[st.miniChg, { color: s.weekly_change >= 0 ? C.coverUp : C.coverDown }]}>{pc(s.weekly_change)}</Text>
                <Spark values={s.closes} color={s.weekly_change >= 0 ? C.coverUp : C.coverDown} w={58} h={20} />
                <Text style={st.miniSub} numberOfLines={1}>{s.count_label}</Text>
              </View>
            ))}
          </ScrollView>
        )}
        {one ? (linked > 0 && <Text style={st.totals}>메모와 연결 <Text style={st.totalsB}>{linked}개</Text></Text>) : (
          <Text style={st.totals}>공시 <Text style={st.totalsB}>{disc}건</Text>   뉴스 <Text style={st.totalsB}>{news}건</Text>   메모와 연결 <Text style={st.totalsB}>{linked}개</Text></Text>
        )}
      </Appear>

      <Appear kind="up" index={1} style={st.sum}>
        <Text style={st.sumHead}>이번 주 한눈에</Text>
        <Text style={st.sumText}>{summary}</Text>
      </Appear>

      {market && (
        <Appear kind="up" index={2} style={st.gapCol}>
          <SectionHead no={no()} title="증시 핫이슈" />
          <View style={st.card}>
            <View style={st.mk3}>
              {market.indices.map((m) => (
                <View key={m.name} style={st.mkCell}>
                  <Text style={st.mkName}>{m.name}</Text>
                  <CountUpText text={m.value} style={st.mkVal} />
                  <Text style={[st.mkChg, { color: m.change >= 0 ? C.up : C.down }]}>{pc(m.change)}</Text>
                </View>
              ))}
            </View>
            {market.headlines.map((h) => (
              <View key={h.ref} style={st.hl}>
                <Text style={st.hlDate}>{h.date}</Text>
                <Text style={st.hlText}>{h.text} <Text style={st.ref}>{h.ref}</Text></Text>
              </View>
            ))}
          </View>
        </Appear>
      )}

      <Appear kind="up" index={3}><SectionHead no={no()} title="종목별 흐름" /></Appear>
      {stocks.map((s, i) => <Appear key={s.stock_code} kind="up" index={4 + i}><StockFlow s={s} onAddWatch={(k) => onAddWatch(s.stock_code, k)} onOpenMemo={() => onOpenMemo(s.stock_code)} /></Appear>)}

      <Appear kind="up" index={4 + stocks.length} style={st.gapCol}>
        <SectionHead no={no()} title="출처" />
        <View style={st.card}>
          {sources.map((t) => <Text key={t} style={st.src}>{t}</Text>)}
        </View>
      </Appear>
      <Text style={st.disclaimer}>투자 권유가 아닌 참고 정보예요 · AI는 틀릴 수 있어 원문을 꼭 확인해 주세요</Text>
    </ScrollView>
  );
}

function OneCover({ s }: { s: ReportStock }) {
  const up = s.weekly_change >= 0;
  return (
    <View style={st.one}>
      <View style={st.miniHead}>
        <View style={[st.miniLogo, { backgroundColor: s.logo_bg }]}><Text style={[st.miniLogoText, { color: s.logo_fg ?? C.white }]}>{s.logo_text}</Text></View>
        <Text style={st.oneName}>{s.name}</Text>
        <View style={st.oneOwn}><Text style={st.oneOwnText}>{s.status === 'holding' ? '보유' : '관심'}</Text></View>
      </View>
      <View style={st.onePrice}>
        <Text style={st.onePriceText}>{s.close_label}</Text>
        <Text style={[st.oneChg, { color: up ? C.coverUp : C.coverDown }]}>{pc(s.weekly_change)}</Text>
        <View style={st.flex} />
        <Text style={st.oneWeek}>이번 주</Text>
      </View>
      <Spark values={s.closes} color={up ? C.coverUp : C.coverDown} w={300} h={64} stretch />
      <View style={st.days}>{DAYS.map((d) => <Text key={d} style={st.day}>{d}</Text>)}</View>
      <View style={st.oneStats}>
        <View style={st.flex}><Text style={st.oneK}>주간 최고</Text><Text style={st.oneV}>{s.week_high}</Text></View>
        <View style={st.flex}><Text style={st.oneK}>주간 최저</Text><Text style={st.oneV}>{s.week_low}</Text></View>
        <View style={st.flex}><Text style={st.oneK}>이번 주 소식</Text><Text style={st.oneV} numberOfLines={1}>{s.items.length ? s.count_label : '없음'}</Text></View>
      </View>
    </View>
  );
}

function StockFlow({ s, onAddWatch, onOpenMemo }: { s: ReportStock; onAddWatch: (i: number) => void; onOpenMemo: () => void }) {
  const up = s.weekly_change >= 0;
  return (
    <View style={st.card}>
      <View style={st.sfHead}>
        <View style={[st.sfLogo, { backgroundColor: s.logo_bg }]}><Text style={[st.miniLogoText, { color: s.logo_fg ?? C.white }]}>{s.logo_text}</Text></View>
        <Text style={st.sfName} numberOfLines={1}>{s.name}</Text>
        <View style={st.sfOwn}><Text style={st.sfOwnText}>{s.status === 'holding' ? '보유' : '관심'}</Text></View>
        <View style={st.flex} />
        <View style={st.sfPriceCol}>
          <Text style={st.sfPrice}>{s.close_label}</Text>
          <Text style={[st.sfChg, { color: up ? C.up : C.down }]}>{pc(s.weekly_change)}</Text>
        </View>
      </View>
      <View style={st.stats}>
        {[['주간 등락', pc(s.weekly_change)], ['주간 최고', s.week_high], ['주간 최저', s.week_low], ['거래량', s.volume_change]].map(([k, v], i) => (
          <View key={k} style={st.stat}>
            <Text style={st.statK}>{k}</Text>
            <Text style={[st.statV, i === 0 && { color: up ? C.up : C.down }]}>{v}</Text>
          </View>
        ))}
      </View>
      <FlowChart s={s} />
      <Text style={st.legend}>● 공시  ● 뉴스  ┄ 지난주 종가 · 번호는 아래 소식·출처 번호예요</Text>
      <Text style={st.narr}>{s.narrative}</Text>

      {s.items.length > 0 && (
        <>
          <Text style={st.subHead}>이번 주 소식</Text>
          {s.items.map((it) => (
            <View key={it.no} style={st.item}>
              <View style={[st.no, { backgroundColor: it.kind === 'disclosure' ? C.evDisc : C.evNews }]}><Text style={st.noText}>{it.no}</Text></View>
              <View style={st.flex}>
                <Text style={st.itemMeta}>{it.kind === 'disclosure' ? '공시' : '뉴스'} · {it.date} · {it.source}</Text>
                <Text style={st.itemTitle}>{it.title}</Text>
              </View>
            </View>
          ))}
        </>
      )}

      {s.memo_link && (
        <>
          <View style={st.subRow}><Text style={st.subHead}>내 메모와의 연결</Text><Pressable onPress={onOpenMemo} hitSlop={10}><Text style={st.link}>원본 메모 보기 ›</Text></Pressable></View>
          <View style={[st.memoCard, { backgroundColor: s.memo_link.paper }]}>
            <Text style={st.memoTitle}>{s.memo_link.title}</Text>
            <Text style={st.memoMeta}>{s.memo_link.meta}</Text>
          </View>
          <Text style={st.memoText}>{s.memo_link.text}</Text>
        </>
      )}

      <Text style={st.subHead}>앞으로 지켜볼 것</Text>
      {s.watch.map((w, i) => (
        <View key={w.text} style={st.watch}>
          <View style={st.flex}>
            <Text style={st.watchText}>{w.text}</Text>
            <Text style={st.watchBasis}>근거 · {w.basis}</Text>
          </View>
          <AddButton added={!!w.added} onPress={() => onAddWatch(i)} label="메모에 추가" addedLabel="추가됨" addedColor={C.doneText}
            style={st.addBtn} addedStyle={st.addDone} textStyle={st.addText} addedTextStyle={[st.addText, st.addDoneText]} />
        </View>
      ))}
    </View>
  );
}

function SectionHead({ no, title }: { no: string; title: string }) {
  return <View style={st.sec}><Text style={st.secNo}>{no}</Text><Text style={st.secTitle}>{title}</Text><View style={st.secLine} /></View>;
}

function Spark({ values, color, w, h, stretch }: { values: number[]; color: string; w: number; h: number; stretch?: boolean }) {
  const draw = useDraw(values.join('|'));
  const fill = useProgress(values.join('|'), 600, EASE, 900);
  const mn = Math.min(...values), mx = Math.max(...values);
  const x = (i: number) => 4 + (i * (w - 8)) / (values.length - 1);
  const y = (v: number) => 4 + (h - 10) * (1 - (v - mn) / (mx - mn || 1));
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const len = lineLength(values.map((v, i) => [x(i), y(v)]));
  return (
    <Svg width={stretch ? '100%' : w} height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      {stretch && <Path d={`${d} L${x(values.length - 1)} ${h} L${x(0)} ${h}Z`} fill={color} fillOpacity={0.2 * fill} />}
      <Path d={d} stroke={color} strokeWidth={stretch ? 2.2 : 1.6} fill="none" {...draw(len)} />
    </Svg>
  );
}

/** 소식 번호 원: 선이 다 그려질 즈음 나타나 두 번 톡 (체험판 .hit: r 4 → 9 → 4, 1.6s × 2, 1.3초 뒤) */
function useHit(replay: string) {
  const show = useProgress(replay, 600, EASE, 900);
  const p = useProgress(replay, 3200, LINEAR, 1300);
  const ph = (p * 2) % 1;
  const k = p >= 1 ? 0 : ph < 0.4 ? ph / 0.4 : 1 - (ph - 0.4) / 0.6;
  return { show, ring: 1 + k * 1.25, ringOpacity: 0.35 * k };
}

function FlowChart({ s }: { s: ReportStock }) {
  const W = 320, H = 130;
  const all = [...s.closes, s.prev_week_close];
  const mn = Math.min(...all), mx = Math.max(...all);
  const x = (i: number) => 18 + (i * (W - 36)) / (s.closes.length - 1);
  const y = (v: number) => 26 + (H - 46) * (1 - (v - mn) / (mx - mn || 1));
  const d = s.closes.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const col = s.weekly_change >= 0 ? C.up : C.down;
  const key = `${s.stock_code}|${s.closes.join(',')}`;
  const draw = useDraw(key);
  const hit = useHit(key);
  const len = lineLength(s.closes.map((v, i) => [x(i), y(v)]));
  return (
    <Svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`}>
      <Line x1={0} x2={W} y1={y(s.prev_week_close)} y2={y(s.prev_week_close)} stroke={C.dash} strokeDasharray="4 4" />
      <Path d={d} stroke={col} strokeWidth={2.2} fill="none" {...draw(len)} />
      {s.closes.map((v, i) => <Circle key={i} cx={x(i)} cy={y(v)} r={3} fill={C.white} stroke={col} strokeWidth={1.6} opacity={hit.show} />)}
      {s.events.map((e) => (
        <G key={e.no} opacity={hit.show}>
          <Line x1={x(e.day)} x2={x(e.day)} y1={14} y2={y(s.closes[e.day])} stroke={e.kind === 'disclosure' ? C.evDisc : C.evNews} strokeWidth={1} />
          <Circle cx={x(e.day)} cy={10} r={8 * hit.ring} fill={e.kind === 'disclosure' ? C.evDisc : C.evNews} opacity={hit.ringOpacity} />
          <Circle cx={x(e.day)} cy={10} r={8} fill={e.kind === 'disclosure' ? C.evDisc : C.evNews} />
          <SvgText x={x(e.day)} y={13.5} fontSize={10} fontWeight="700" fill={C.white} textAnchor="middle">{e.no}</SvgText>
        </G>
      ))}
      {DAYS.map((dd, i) => <SvgText key={dd} x={x(i)} y={H - 2} fontSize={11} fill={C.muted} textAnchor="middle">{dd}</SvgText>)}
    </Svg>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.appBg },
  flex: { flex: 1, minWidth: 0 },
  body: { paddingHorizontal: PAD, paddingBottom: 40, gap: GAP },
  gapCol: { gap: GAP },
  cover: { backgroundColor: C.coverBg, borderRadius: R.card, padding: 18 },
  coverTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  coverTag: { fontSize: 11.5, fontWeight: '800', letterSpacing: 0.6, color: C.coverTag, flexShrink: 1 },
  weekChip: { backgroundColor: C.coverChip, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  weekText: { fontSize: 12, fontWeight: '700', color: C.coverText },
  coverTitle: { fontSize: 26, fontWeight: '800', color: C.coverText, marginTop: 12 },
  coverSub: { fontSize: 12.5, color: C.coverSub, marginTop: 6 },
  miniRow: { gap: 10, paddingTop: 14 },
  mini: { width: 160, backgroundColor: C.coverCard, borderWidth: 1, borderColor: C.coverLine, borderRadius: R.inner, padding: 12 },
  miniHead: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  miniLogo: { width: 22, height: 22, borderRadius: 7, alignItems: 'center', justifyContent: 'center' },
  miniLogoText: { fontSize: 11, fontWeight: '800' },
  miniName: { flex: 1, fontSize: 13.5, fontWeight: '700', color: C.coverText },
  miniChg: { fontSize: 17, fontWeight: '800', marginTop: 6 },
  miniSub: { fontSize: 11, color: C.coverSub, marginTop: 6 },
  totals: { fontSize: 12.5, color: C.coverSub, borderTopWidth: 1, borderTopColor: C.coverLine, marginTop: 14, paddingTop: 12 },
  totalsB: { color: C.coverText, fontWeight: '800' },
  one: { marginTop: 14, backgroundColor: C.coverCard, borderWidth: 1, borderColor: C.coverLine, borderRadius: 16, padding: 14 },
  oneName: { fontSize: 14, fontWeight: '700', color: C.coverText },
  oneOwn: { backgroundColor: C.coverChip, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  oneOwnText: { fontSize: 11, fontWeight: '700', color: C.coverSub },
  onePrice: { flexDirection: 'row', alignItems: 'baseline', gap: 8, marginTop: 10, marginBottom: 8 },
  onePriceText: { fontSize: 26, fontWeight: '800', color: C.coverText },
  oneChg: { fontSize: 15, fontWeight: '800' },
  oneWeek: { fontSize: 11.5, color: C.coverSub },
  days: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 2 },
  day: { fontSize: 10.5, fontWeight: '600', color: C.coverSub },
  oneStats: { flexDirection: 'row', borderTopWidth: 1, borderTopColor: C.coverLine, marginTop: 12, paddingTop: 10 },
  oneK: { fontSize: 11, color: C.coverSub },
  oneV: { fontSize: 14, fontWeight: '800', color: C.coverText, marginTop: 2 },
  sum: { backgroundColor: C.card, borderRadius: R.card, padding: 16, borderLeftWidth: 4, borderLeftColor: C.accent },
  sumHead: { fontSize: 13, fontWeight: '800', color: C.accentDeep },
  sumText: { fontSize: 14.5, lineHeight: 23, color: C.text, marginTop: 6 },
  sec: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 },
  secNo: { fontSize: 13, fontWeight: '800', color: C.accentDeep },
  secTitle: { fontSize: 17, fontWeight: '800', color: C.text },
  secLine: { flex: 1, height: 1, backgroundColor: C.line },
  card: { backgroundColor: C.card, borderRadius: R.card, padding: 16 },
  mk3: { flexDirection: 'row', gap: 8 },
  mkCell: { flex: 1, backgroundColor: C.statBg, borderRadius: 12, padding: 10 },
  mkName: { fontSize: 12, color: C.sub },
  mkVal: { fontSize: 15, fontWeight: '800', color: C.text, marginTop: 2 },
  mkChg: { fontSize: 12.5, fontWeight: '700', marginTop: 2 },
  hl: { flexDirection: 'row', gap: 10, paddingTop: 12 },
  hlDate: { fontSize: 12.5, fontWeight: '700', color: C.sub, width: 62 },
  hlText: { flex: 1, fontSize: 13.5, lineHeight: 20, color: C.text },
  ref: { color: C.accentDeep, fontWeight: '700' },
  sfHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sfLogo: { width: 30, height: 30, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  sfName: { fontSize: 17, fontWeight: '800', color: C.text, flexShrink: 1 },
  sfOwn: { backgroundColor: C.statBg, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1 },
  sfOwnText: { fontSize: 11.5, fontWeight: '700', color: C.sub },
  sfPriceCol: { alignItems: 'flex-end' },
  sfPrice: { fontSize: 16, fontWeight: '800', color: C.text },
  sfChg: { fontSize: 13, fontWeight: '700' },
  stats: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 14 },
  stat: { width: '48%', flexGrow: 1, backgroundColor: C.statBg, borderRadius: 12, padding: 10 },
  statK: { fontSize: 12, color: C.sub },
  statV: { fontSize: 16, fontWeight: '800', color: C.text, marginTop: 2 },
  legend: { fontSize: 11.5, color: C.muted, marginTop: 4 },
  narr: { fontSize: 14, lineHeight: 22, color: C.text, marginTop: 12 },
  subHead: { fontSize: 14, fontWeight: '800', color: C.text, marginTop: 16, marginBottom: 6 },
  subRow: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' },
  link: { fontSize: 13, fontWeight: '700', color: C.accentDeep },
  item: { flexDirection: 'row', gap: 10, paddingVertical: 8, borderTopWidth: 1, borderTopColor: C.line },
  no: { width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginTop: 1 },
  noText: { fontSize: 11, fontWeight: '800', color: C.white },
  itemMeta: { fontSize: 12, color: C.muted },
  itemTitle: { fontSize: 14, fontWeight: '700', color: C.text, marginTop: 2 },
  memoCard: { borderRadius: 14, padding: 12 },
  memoTitle: { fontSize: 14.5, fontWeight: '800', color: C.text },
  memoMeta: { fontSize: 12, color: C.sub, marginTop: 2 },
  memoText: { fontSize: 13.5, lineHeight: 21, color: C.text, marginTop: 8 },
  watch: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderTopWidth: 1, borderTopColor: C.line },
  watchText: { fontSize: 14, fontWeight: '700', color: C.text, lineHeight: 20 },
  watchBasis: { fontSize: 12, color: C.muted, marginTop: 3 },
  addBtn: { height: 44, paddingHorizontal: 12, borderRadius: 12, backgroundColor: C.accentSoft, justifyContent: 'center' },
  addText: { fontSize: 13, fontWeight: '800', color: C.accentDeep },
  addDone: { backgroundColor: C.doneBg },
  addDoneText: { color: C.doneText },
  src: { fontSize: 12.5, lineHeight: 22, color: C.sub },
  disclaimer: { textAlign: 'center', fontSize: 12, lineHeight: 19, color: C.muted, marginTop: 6 },
});
