import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Path, Rect, Stop, Text as SvgText } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import type { Memo, MemoVersion } from '@/types/models';
import { EvIcon } from '@/ui/icons/MemoGlyphs';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { PaperBox } from '@/ui/shared/PaperBox';
import { mmdd } from '@/ui/shared/memoFormat';
import { appColor, curve, ft } from '@/ui/theme';
import type { MemoFeedItem } from './MemoDetail.types';
import { won } from './memoTimeline';
import { usePaper } from '@/ui/shared/Dark';

/* 근거 상세 내용 (원본 memo.html 13.1 · 13.2 · 13.3 openEv) — 앱 화면과 웹 메모 창이 같이 씀 */

const md = (iso: string) => {
  const m = iso.match(/-(\d\d)-(\d\d)T/);
  return m ? `${Number(m[1])}월 ${Number(m[2])}일` : '';
};
/* 원본 evk 칩 */
const KCHIP = { 공시: { bg: '#FFE9E9', ink: '#B42318' }, 뉴스: { bg: '#E4ECFF', ink: '#2F6BDB' }, 주가: { bg: '#E3F5EA', ink: '#1B7A45' } } as const;
/* 가격 상태 배지 색 (원본: 근접 #C98A00 · 기본 #1B7A45). ④-2 결정: 배지 글은 '조건까지 +4.5%'처럼 숫자로만 */
const TONE = { near: '#C98A00', reached: '#1B7A45' } as const;
const toCond = (gap: string) => `조건까지 ${gap.match(/\(([^)]+)\)/)?.[1] ?? gap}`;

/** 머리 제목 (원본 #evt) */
export const evidenceTitle = (f: MemoFeedItem) => (f.kind === '공시' ? '업데이트 근거' : f.kind === '뉴스' ? '뉴스 근거' : '가격 조건');

/** 아래 버튼 (원본 #evbar): 공시 [메모 보기][DART에서 보고서 찾기 ↗] · 뉴스 [메모 보기][원문 기사 보기 ↗] · 가격 [연결된 메모 보기] */
export const evidenceActions = (f: MemoFeedItem): { label: string; a: 'memo' | 'out'; gray?: boolean }[] =>
  f.kind === '주가'
    ? [{ label: '연결된 메모 보기', a: 'memo' }]
    : [
        { label: '메모 보기', a: 'memo', gray: true },
        { label: f.kind === '공시' ? 'DART에서 보고서 찾기 ↗' : '원문 기사 보기 ↗', a: 'out' },
      ];

export function EvidenceBody({ item: f, memo, version, onOpenSource, onOpenHistory, onSuggestMemo }: { item: MemoFeedItem; memo: Memo; version?: MemoVersion; onOpenSource: (f: MemoFeedItem) => void; onOpenHistory: (v: number) => void; onSuggestMemo?: (text: string) => void }) {
  const kc = KCHIP[f.kind];
  const memoCard = <MemoCard memo={memo} version={version} onPress={() => onOpenHistory(version?.version ?? 1)} />;
  if (f.kind === '주가' && f.price) {
    const p = f.price;
    const tone = { bg: TONE[p.tone], t: toCond(p.gap) };
    return (
      <Rv>
        <View style={[st.ecd, st.priceTop]}>
          <GradientBg />
          <View style={[st.evk, { marginTop: 0, marginHorizontal: 0 }]}>
            <View style={[st.kchip, { backgroundColor: kc.bg }]}>
              <Text style={[st.kchipT, { color: kc.ink }]}>가격 조건</Text>
            </View>
            <Text style={st.evkT}>{mmdd(f.at)} 종가 기준</Text>
          </View>
          <Text style={st.pH}>{f.headline}</Text>
          <View style={st.pRow}>
            <CountUp to={p.close} />
            <View style={[st.badge, { backgroundColor: tone.bg }]}>
              <Text style={st.badgeT}>{tone.t}</Text>
            </View>
          </View>
          <PriceChart closes={p.closes} cond={p.cond} from={p.from} to={p.to} />
          <Text style={st.sm}>
            점선 · 조건가 {won(p.cond)}원 {p.direction}
          </Text>
        </View>
        <View style={st.ecd}>
          <CardHead icon={<EvIcon k="line" color="#2F6BDB" />} bg="#E4ECFF" title="판정 근거" />
          <Kv k="판정 기준" v="전일 종가" />
          <Kv k="조건가" v={`${won(p.cond)}원 ${p.direction}`} />
          <Kv k="전일 종가" v={`${won(p.close)}원`} />
          <Kv k="조건과의 차이" v={p.gap} color="#2F6BDB" />
          <Kv k="시세 기준일" v={`${f.at.slice(0, 4)}. ${f.at.slice(5, 7)}. ${f.at.slice(8, 10)}.`} />
          <Kv k="데이터 출처" v="KIS (한국투자증권)" last />
          <Text style={st.sm}>코드로 계산한 값이에요.</Text>
        </View>
        {memoCard}
        <Text style={st.ainfo}>✦ 가격 조건은 종가로 계산해요. 공시·뉴스 근거와는 따로 구분해요.</Text>
      </Rv>
    );
  }
  const head = (
    <>
      <View style={st.evk}>
        <View style={[st.kchip, { backgroundColor: kc.bg }]}>
          <Text style={[st.kchipT, { color: kc.ink }]}>{f.kind}</Text>
        </View>
        <Text style={st.evkT}>{md(f.at)}</Text>
      </View>
      <Text style={st.evh}>{f.headline}</Text>
    </>
  );
  /* 질문 답 아래 새 메모 제안 (2026-11-25): "140만원 넘으면 알려드릴까요?" [알림 받기] → 글을 채운 새 메모 창 */
  const suggest =
    f.suggest && onSuggestMemo ? (
      <View style={[st.ecd, st.sug]}>
        <Text style={st.sugT}>🔔 {f.suggest.label}</Text>
        <Pressable onPress={() => onSuggestMemo(f.suggest!.memo_text)} accessibilityRole="button" style={({ pressed }) => [st.sugB, pressed && { opacity: 0.7 }]}>
          <Text style={st.sugBT}>{f.suggest.button}</Text>
        </Pressable>
      </View>
    ) : null;
  const ai = (t: string, s: string) => (
    <>
      <View style={st.ecd}>
        <CardHead icon={<Text style={st.spark}>✦</Text>} bg="#EEE9FB" title={t} />
        <Text style={st.p}>{f.summary}</Text>
        <Text style={[st.sm, { marginTop: 6 }]}>{s}</Text>
      </View>
      {suggest}
    </>
  );
  if (f.kind === '공시')
    return (
      <Rv>
        {head}
        {ai('AI가 요약했어요', '메모에서 확인하려던 주제와 관련된 부분을 연결했어요.')}
        {memoCard}
        <View style={st.ecd}>
          <CardHead icon={<EvIcon k="doc" color="#B42318" />} bg="#FFE9E9" title="근거 1 · 금융감독원 DART" />
          {f.report ? <Kv k="보고서" v={f.report} /> : null}
          <Kv k="공시일" v={f.source.replace(/^DART · /, '')} last />
          {f.quote ? (
            <View style={st.qt}>
              <Text style={st.qtT}>
                {'"'}
                {splitMark(f.quote, f.quote_mark).map((x, i) => (
                  <Text key={i} style={x.mark ? st.mark : null}>
                    {x.t}
                  </Text>
                ))}
                {'"'}
              </Text>
            </View>
          ) : null}
          <View style={st.vchipL}>
            <Text style={st.vchipT}>원문 일부</Text>
          </View>
          <Text style={[st.sm, { marginTop: 6 }]}>보고서명·공시일·관련 문장을 원문에서 함께 확인하세요.</Text>
        </View>
      </Rv>
    );
  /* 뉴스: 제목·언론사·날짜·링크만 (기사 본문은 보여 주지 않음) */
  const [press, ...rest] = f.source.split(' · ');
  return (
    <Rv>
      {head}
      {ai('메모와 연결된 이유', '기사 내용은 원문 링크에서 확인해요.')}
      <View style={st.ecd}>
        <CardHead icon={<EvIcon k="news" color="#B42318" />} bg="#FFE9E9" title="기사 출처" />
        <View style={st.art}>
          <View style={st.artTop}>
            <View style={st.press}>
              <Text style={st.pressT}>{press}</Text>
            </View>
            <Text style={st.artAt}>{rest.join(' · ')}</Text>
          </View>
          <Text style={st.artT}>{f.article_title}</Text>
          <Pressable onPress={() => onOpenSource(f)} accessibilityRole="link" style={st.selfStart}>
            <Text style={st.artLink}>원문 읽기 ↗</Text>
          </Pressable>
        </View>
        <Kv k="제공" v={f.provider ?? press} top />
        <Text style={st.sm}>기사 본문은 화면에 보여 주지 않고 제목·언론사·날짜·링크만 보여 줘요.</Text>
      </View>
      {memoCard}
    </Rv>
  );
}

/** 가격 카드 바탕 (원본 linear-gradient(165deg, #F3F4F6, #E4E6EB)) — 크기를 재서 그림 */
function GradientBg() {
  const [b, setB] = useState<{ w: number; h: number } | null>(null);
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none" onLayout={(e) => setB({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })}>
      {b ? (
        <Svg width={b.w} height={b.h}>
          <Defs>
            <LinearGradient id="ptop" x1="0.37" y1="0" x2="0.63" y2="1">
              <Stop offset="0" stopColor="#F3F4F6" />
              <Stop offset="1" stopColor="#E4E6EB" />
            </LinearGradient>
          </Defs>
          <Rect x={0} y={0} width={b.w} height={b.h} fill="url(#ptop)" />
        </Svg>
      ) : null}
    </View>
  );
}

/** 연결된 내 메모 (원본 memoCard: '연결된 내 메모' + '버전 N' · 메모지 (라운드 14 · 접힌 18) · 누르면 그 버전 이력) */
function MemoCard({ memo, version, onPress }: { memo: Memo; version?: MemoVersion; onPress: () => void }) {
  const paper = usePaper();
  const pc = paper[memo.color];
  const title = version?.title ?? memo.title;
  const body = version?.body ?? memo.body;
  return (
    <View style={st.ecd}>
      <View style={st.h4}>
        <Text style={st.h4T}>연결된 내 메모</Text>
        <View style={st.vchip}>
          <Text style={st.vchipT}>버전 {version?.version ?? 1}</Text>
        </View>
      </View>
      <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={`버전 ${version?.version ?? 1} 이력 보기`}>
        <PaperBox bg={pc.bg} accent={pc.accent} radius={14} cut={18} style={st.mnote}>
          <Text style={st.mnoteB}>{title}</Text>
          {body ? <Text style={st.mnoteP}>{body}</Text> : null}
        </PaperBox>
      </Pressable>
      <Text style={[st.sm, { marginTop: 8 }]}>이 업데이트가 만들어질 당시의 메모 내용이에요 · 누르면 그 버전 이력</Text>
    </View>
  );
}

function CardHead({ icon, bg, title }: { icon: React.ReactNode; bg: string; title: string }) {
  return (
    <View style={st.h4}>
      <View style={[st.ix, { backgroundColor: bg }]}>{icon}</View>
      <Text style={st.h4T}>{title}</Text>
    </View>
  );
}
function Kv({ k, v, color, last, top }: { k: string; v: string; color?: string; last?: boolean; top?: boolean }) {
  return (
    <View style={[st.kvr, last && { borderBottomWidth: 0 }, top && { marginTop: 6 }]}>
      <Text style={st.kvK}>{k}</Text>
      <Text style={[st.kvV, color ? { color } : null]}>{v}</Text>
    </View>
  );
}
function splitMark(q: string, mark?: string) {
  if (!mark || !q.includes(mark)) return [{ t: q, mark: false }];
  const i = q.indexOf(mark);
  return [
    { t: q.slice(0, i), mark: false },
    { t: mark, mark: true },
    { t: q.slice(i + mark.length), mark: false },
  ];
}

/** 원본 .rv: 카드가 아래 12 에서 차례로 (.45s · 60ms) */
function Rv({ children }: { children: React.ReactNode }) {
  const kids = React.Children.toArray(children);
  return (
    <View>
      {kids.map((c, i) => (
        <RvItem key={i} i={i}>
          {c}
        </RvItem>
      ))}
    </View>
  );
}
function RvItem({ i, children }: { i: number; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: 1, duration: 450 * k, delay: i * 60 * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [v, k, i]);
  return <Animated.View style={{ opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }) }] }}>{children}</Animated.View>;
}

/** 원본 countUp: 90% 에서 끝값까지 .7s (끝이 느려짐) */
function CountUp({ to }: { to: number }) {
  const k = useMotionK();
  const [n, setN] = useState(to * 0.9);
  useEffect(() => {
    const t0 = Date.now();
    const D = 700 * k || 1;
    const id = setInterval(() => {
      const q = Math.min(1, (Date.now() - t0) / D);
      const e = 1 - Math.pow(1 - q, 3);
      setN(to * e + to * 0.9 * (1 - e));
      if (q >= 1) clearInterval(id);
    }, 16);
    return () => clearInterval(id);
  }, [to, k]);
  return <Text style={st.price}>{won(n)}원</Text>;
}

/**
 * 가격 차트 (원본 priceChart: 높이 150 · 종가 선 #3D73F0 2.2 · 아래 면 .22 → 0 · 조건가 빨간 점선 4 4 + '조건 N원'
 * 마지막 점 r4 흰 + 테두리 2.4 · 아래 처음·끝 날짜 11px #9A9EA7). 선은 1.2s 그려지고 면은 .9s 뒤 나타남. 폭은 칸에 맞춤.
 */
export function PriceChart({ closes: P, cond, from, to }: { closes: number[]; cond: number; from: string; to: string }) {
  const k = useMotionK();
  const [W, setW] = useState(0);
  const H = 150;
  const [draw] = useState(() => new Animated.Value(0));
  const [area] = useState(() => new Animated.Value(0));
  const [hit] = useState(() => new Animated.Value(0));
  /* SVG 를 Animated 로 감싸면 웹에서 collapsable 속성이 DOM 에 새어 나가서, 값만 받아 다시 그림 */
  const [f, setF] = useState({ d: 0, a: 0, h: 0 });
  useEffect(() => {
    const s1 = draw.addListener(({ value }) => setF((o) => ({ ...o, d: value })));
    const s2 = area.addListener(({ value }) => setF((o) => ({ ...o, a: value })));
    const s3 = hit.addListener(({ value }) => setF((o) => ({ ...o, h: value })));
    return () => {
      draw.removeListener(s1);
      area.removeListener(s2);
      hit.removeListener(s3);
    };
  }, [draw, area, hit]);
  useEffect(() => {
    if (!W) return;
    const a = Animated.parallel([
      Animated.timing(draw, { toValue: 1, duration: 1200 * k, delay: 150, easing: curve.ease, useNativeDriver: false }),
      Animated.timing(area, { toValue: 1, duration: 600 * k, delay: 900 * k, easing: Easing.linear, useNativeDriver: false }),
      Animated.sequence([Animated.delay(1300 * k), Animated.loop(Animated.timing(hit, { toValue: 1, duration: 1600 * k, easing: Easing.out(Easing.quad), useNativeDriver: false }), { iterations: 2 })]),
    ]);
    a.start();
    return () => a.stop();
  }, [W, draw, area, hit, k]);
  const lo = Math.min(...P, cond) * 0.985;
  const hi = Math.max(...P, cond) * 1.012;
  const x = (i: number) => 8 + (i * (W - 24)) / (P.length - 1);
  const y = (v: number) => 10 + (H - 28) * (1 - (v - lo) / (hi - lo));
  const d = P.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const cy = y(cond);
  const lx = x(P.length - 1);
  const ly = y(P[P.length - 1]);
  return (
    <View style={st.chart} onLayout={(e) => setW(Math.round(e.nativeEvent.layout.width))}>
      {W ? (
        <Svg width={W} height={H}>
          <Defs>
            <LinearGradient id="pg2" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor="#3D73F0" stopOpacity={0.22} />
              <Stop offset="1" stopColor="#3D73F0" stopOpacity={0} />
            </LinearGradient>
          </Defs>
          <Path d={`${d} L${lx} ${H - 18} L${x(0)} ${H - 18}Z`} fill="url(#pg2)" opacity={f.a} />
          <Path d={`M0 ${cy}H${W}`} stroke="#E5484D" strokeDasharray="4 4" />
          <SvgText x={W - 4} y={cy - 6} fontSize={11} fill="#E5484D" textAnchor="end">
            {`조건 ${won(cond)}원`}
          </SvgText>
          <Path d={d} fill="none" stroke="#3D73F0" strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round" strokeDasharray="900" strokeDashoffset={900 * (1 - f.d)} />
          {/* 원본 .hit: r 4 → 9 → 4 · 불투명 1 → .35 → 1 (40% 지점) */}
          <Circle cx={lx} cy={ly} r={f.h < 0.4 ? 4 + 5 * (f.h / 0.4) : 9 - 5 * ((f.h - 0.4) / 0.6)} fill="#FFFFFF" stroke="#3D73F0" strokeWidth={2.4} opacity={f.h < 0.4 ? 1 - 0.65 * (f.h / 0.4) : 0.35 + 0.65 * ((f.h - 0.4) / 0.6)} />
          <SvgText x={x(0)} y={H - 2} fontSize={11} fill="#9A9EA7">
            {from}
          </SvgText>
          <SvgText x={lx} y={H - 2} fontSize={11} fill="#9A9EA7" textAnchor="end">
            {to}
          </SvgText>
        </Svg>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  selfStart: { alignSelf: 'flex-start' },
  evk: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 2, marginHorizontal: 2, marginBottom: 6 },
  kchip: { borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 },
  kchipT: { ...ft(11.5), fontWeight: '800' },
  evkT: { ...ft(12.5), color: appColor.ink3 },
  evh: { ...ft(21, 1.4), fontWeight: '800', color: appColor.ink, marginHorizontal: 2, marginBottom: 14 },
  ecd: { backgroundColor: '#FFFFFF', borderRadius: 20, padding: 16, marginBottom: 12 },
  h4: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  h4T: { ...ft(15.5), fontWeight: '700', color: appColor.ink, flexShrink: 1 },
  ix: { width: 28, height: 28, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  spark: { ...ft(14, 1), color: '#6A42AB' },
  p: { ...ft(14, 1.7), color: appColor.ink },
  sm: { ...ft(12), color: appColor.ink3 },
  kvr: { flexDirection: 'row', justifyContent: 'space-between', gap: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#F2F3F5' },
  kvK: { ...ft(13.5), color: appColor.ink2 },
  kvV: { ...ft(13.5), fontWeight: '700', color: appColor.ink, flexShrink: 1, textAlign: 'right' },
  qt: { backgroundColor: '#F5F6F8', borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12, marginTop: 10, marginBottom: 6, borderLeftWidth: 3, borderLeftColor: appColor.red },
  qtT: { ...ft(13.5, 1.65), color: appColor.ink },
  mark: { backgroundColor: 'rgba(255,211,0,0.5)' },
  vchip: { marginLeft: 'auto', backgroundColor: '#EEF0F3', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  vchipL: { alignSelf: 'flex-start', backgroundColor: '#EEF0F3', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  vchipT: { ...ft(11.5), fontWeight: '700', color: appColor.ink2 },
  mnote: { paddingTop: 12, paddingHorizontal: 14, paddingBottom: 16 },
  mnoteB: { ...ft(14.5), fontWeight: '700', color: appColor.ink },
  mnoteP: { ...ft(12.5, 1.5), color: '#2E2E38', marginTop: 2 },
  art: { backgroundColor: '#F3F2F8', borderRadius: 14, paddingVertical: 12, paddingHorizontal: 14 },
  artTop: { flexDirection: 'row', alignItems: 'center' },
  press: { backgroundColor: '#FFFFFF', borderRadius: 6, paddingHorizontal: 7, paddingVertical: 1 },
  pressT: { ...ft(12), fontWeight: '700', color: appColor.ink },
  artAt: { marginLeft: 'auto', ...ft(12), color: '#6A42AB' },
  artT: { ...ft(15.5, 1.4), fontWeight: '800', color: appColor.ink, marginTop: 8, marginBottom: 6 },
  artLink: { ...ft(13), fontWeight: '700', color: '#6A42AB' },
  sug: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  sugT: { ...ft(14, 1.5), color: appColor.ink, flex: 1, fontWeight: '600' },
  sugB: { backgroundColor: '#2F6BDB', borderRadius: 12, paddingVertical: 9, paddingHorizontal: 14 },
  sugBT: { ...ft(13), color: '#FFFFFF', fontWeight: '700' },
  ainfo: { backgroundColor: '#F3EFFD', borderRadius: 14, paddingVertical: 12, paddingHorizontal: 14, ...ft(12.5, 1.6), color: '#4B2D93', marginTop: 6, overflow: 'hidden' },
  priceTop: { backgroundColor: '#ECEDF1', overflow: 'hidden' },
  pH: { ...ft(16), fontWeight: '700', color: appColor.ink },
  pRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6, marginBottom: 2 },
  price: { ...ft(26), fontWeight: '700', color: appColor.ink },
  badge: { borderRadius: 7, paddingHorizontal: 8, paddingVertical: 3 },
  badgeT: { ...ft(11.5), fontWeight: '800', color: '#FFFFFF' },
  chart: { marginTop: 6, marginHorizontal: -4, marginBottom: 2, height: 150 },
});
