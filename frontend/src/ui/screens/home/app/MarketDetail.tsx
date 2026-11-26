import React, { useEffect, useMemo, useState } from 'react';
import { Animated, PanResponder, StyleSheet, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, ClipPath, Defs, Line, LinearGradient, Path, Rect, Stop } from 'react-native-svg';
import { useMiniSpace } from '@/ui/screens/studio/app/MiniBar';
import { Text } from '@/components/ui/AppText';
import { useMotionK } from '@/ui/motion/useMotion';
import { useProgress } from '@/ui/motion/useProgress';
import { NudgePill } from '@/ui/shared/NudgePill';
import { PillSeg } from '@/ui/shared/PillSeg';
import { appColor, curve, ft } from '@/ui/theme';
import type { MarketDetailProps } from '../Home.types';
import { APP_PERIODS, basisText, nf, pointText, spark, type AppPeriod } from '../homeFormat';
import { useNudge } from '@/store/nudge';

const CH = 230;
let seq = 0;
const nextKey = () => ++seq;

/**
 * 앱 지수 자세히 (원본 home.html #324 #096 #047 .page2 #mkt)
 * 큰 값 34/800 · 등락 14/600 · 기준 12.5 · 선 230 (좌우 20) · 손가락으로 훑으면 왼쪽만 색이 남고 위 숫자가 그날 값
 * 기간(1주·1달·3달·1년)을 바꾸면 숫자가 세어 가며 선이 새로 그려짐 (.7s). 전일 확정 종가 기준.
 */
export function AppMarketDetail({ index: q, header, onNudge }: MarketDetailProps) {
  const k = useMotionK();
  const insets = useSafeAreaInsets();
  const { width: W } = useWindowDimensions();
  const [per, setPer] = useState<AppPeriod>('1주');
  const n = APP_PERIODS.find((x) => x.key === per)?.n ?? 6;
  const data = q.closes.slice(-n);
  const s = spark(data, W - 40, CH - 30);
  const first = data[0];
  const last = data[data.length - 1];
  const col = last < first ? appColor.down : appColor.up;
  const [idx, setIdx] = useState<number | null>(null);
  /* 넛지 닫은 상태는 한 곳(store/nudge)에 — 다시 들어와도 안 뜸 · 사용법 안내 중엔 숨김 */
  const miniSpace = useMiniSpace();
  const nudgeS = useNudge('lab');
  const nudge = nudgeS.show;
  const setNudge = (v: boolean) => {
    if (!v) nudgeS.hide();
  };
  /* 큰 숫자 세기 (원본 countTo 500ms · 1-(1-t)^3) */
  const [num] = useState(() => new Animated.Value(q.value));
  const [shown, setShown] = useState(q.value);
  useEffect(() => {
    const id = num.addListener(({ value }) => setShown(value));
    return () => num.removeListener(id);
  }, [num]);
  useEffect(() => {
    const a = Animated.timing(num, { toValue: last, duration: 500 * k, easing: (t) => 1 - Math.pow(1 - t, 3), useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [per, last, num, k]);
  /* 선 그리기 (기간을 바꿀 때 .7s) · 놓으면 색 구간이 끝까지 돌아감 (.45s) */
  const [drawn, setDrawn] = useState(0);
  const td = useProgress(drawn > 0, 700, drawn);
  const lineE = drawn ? curve.ease(td) : 1;
  const [back, setBack] = useState<{ from: number; key: number } | null>(null);
  const tb = useProgress(!!back, 450, back?.key ?? 0);
  const L = useMemo(() => s.pts.reduce((a, p, i) => (i ? a + Math.hypot(p[0] - s.pts[i - 1][0], p[1] - s.pts[i - 1][1]) : 0), 0), [s.pts]);
  const pan = useMemo(() => {
    const g = { cur: null as number | null };
    const pick = (x: number) => {
      g.cur = Math.max(0, Math.min(n - 1, Math.round(((x - 20) / (W - 40)) * (n - 1))));
      return g.cur;
    };
    return PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (e) => {
        num.stopAnimation();
        setBack(null);
        setIdx(pick(e.nativeEvent.pageX));
      },
      onPanResponderMove: (e) => setIdx(pick(e.nativeEvent.pageX)),
      onPanResponderRelease: () => {
        if (g.cur !== null) setBack({ from: g.cur, key: nextKey() });
        g.cur = null;
        setIdx(null);
      },
      onPanResponderTerminate: () => {
        g.cur = null;
        setIdx(null);
      },
      onPanResponderTerminationRequest: () => false,
    });
  }, [n, W, num]);
  useEffect(() => {
    if (idx === null) return;
    num.setValue(data[idx]);
  }, [idx, data, num]);
  useEffect(() => {
    if (!back) return;
    const a = Animated.timing(num, { toValue: last, duration: 500 * k, easing: (t) => 1 - Math.pow(1 - t, 3), useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [back, last, num, k]);

  const i = idx ?? data.length - 1;
  const v = idx === null ? shown : data[idx];
  const c = (idx === null ? last : data[idx]) - first;
  const pc = (c / first) * 100;
  const ago = data.length - 1 - i;
  /* 짚은 점의 실제 날짜 (그 지표 자신의 dates, 2026-11-21) */
  const pointDate = q.dates.slice(-n)[i];
  const p = s.pts[i];
  /* 색이 남는 구간: 훑는 중 = 손가락까지 · 놓은 뒤 = 그 자리에서 끝까지 늘어남 */
  const clipW = idx !== null ? p[0] + 20 : back ? s.pts[back.from][0] + 20 + (W - (s.pts[back.from][0] + 20)) * curve.ease(tb) : W;
  /* 안드로이드는 같은 id 의 clipPath 가 바뀌어도 다시 그리지 않아 폭마다 id 를 바꿈 */
  const cid = `mcl-${Math.round(clipW)}`;
  return (
    <View style={st.root}>
      {header}
      <View style={st.mdv}>
        <Text style={st.sub}>{q.sub}</Text>
        <Text style={st.big}>{nf(v)}</Text>
        <Text style={[st.chg, { color: c < 0 ? appColor.down : appColor.up }]}>
          {c > 0 ? '+' : ''}
          {nf(c)} ({c > 0 ? '+' : ''}
          {pc.toFixed(2)}%) · {per} 전보다
        </Text>
        <Text style={st.when}>{ago === 0 ? basisText(q) : pointText(q, pointDate) || `${ago}${q.key === 'usd' ? '번 전 관측값' : '거래일 전 종가'}`}</Text>
      </View>
      <View style={st.chart} {...pan.panHandlers} accessibilityLabel={`${q.name} ${per} 선 그래프`}>
        <Svg width={W} height={CH} viewBox={`-20 0 ${W} ${CH}`}>
          <Defs>
            <LinearGradient id="mga" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={col} stopOpacity={0.18} />
              <Stop offset="1" stopColor={col} stopOpacity={0} />
            </LinearGradient>
            <ClipPath id={cid}>
              <Rect x={-20} y={0} width={clipW} height={CH} />
            </ClipPath>
          </Defs>
          <Path d={s.area} fill="url(#mga)" clipPath={`url(#${cid})`} />
          <Path d={s.d} fill="none" stroke="#D5D8DD" strokeWidth={2} />
          <Path d={s.d} fill="none" stroke={col} strokeWidth={2.2} clipPath={`url(#${cid})`} strokeDasharray={`${L} ${L}`} strokeDashoffset={L * (1 - lineE)} />
          <Line x1={p[0]} x2={p[0]} y1={0} y2={CH} stroke="#C9CDD4" strokeDasharray="3 3" opacity={idx !== null ? 1 : 0} />
          <Circle r={5} fill="#FFFFFF" stroke={col} strokeWidth={2.4} cx={p[0]} cy={p[1]} />
        </Svg>
      </View>
      <PillSeg
        options={APP_PERIODS.map((x) => ({ key: x.key, label: x.key }))}
        value={per}
        onChange={(key) => {
          setPer(key);
          setIdx(null);
          setBack(null);
          setDrawn((d) => d + 1);
        }}
        bg={appColor.sf}
        pad={4}
        radius={13}
        pillRadius={10}
        height={36}
        fontSize={14}
        style={st.per}
      />
      <Text style={st.mfoot}>{q.key === 'usd' ? '선을 손가락으로 훑으면 그날의 값이 보여요. 한국은행(ECOS) 관측값이에요' : '선을 손가락으로 훑으면 그날의 값이 보여요. 전일 확정 종가 기준이에요'}</Text>
      {q.key === 'usd' && onNudge && nudge ? (
        <View style={[st.nudge, { bottom: 28 + insets.bottom + miniSpace }]} pointerEvents="box-none">
          <NudgePill text="환율이 바뀌면 내 종목은? 실험해 보기" onGo={onNudge} onClose={() => setNudge(false)} />
        </View>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#FFFFFF' },
  mdv: { paddingVertical: 6, paddingHorizontal: 20 },
  sub: { ...ft(15), color: appColor.ink2 },
  big: { fontSize: 34, lineHeight: 40, fontWeight: '800', letterSpacing: -0.5, color: appColor.ink, marginVertical: 2 },
  chg: { ...ft(15), fontWeight: '600' },
  when: { ...ft(13.5), color: '#6B7079', marginTop: 2, minHeight: 18 },
  chart: { marginTop: 14, height: CH },
  per: { marginTop: 14, marginHorizontal: 20 },
  mfoot: { ...ft(13, 1.7), color: '#6B7079', paddingVertical: 14, paddingHorizontal: 20 },
  nudge: { position: 'absolute', left: 16, right: 16, alignItems: 'center' },
});
