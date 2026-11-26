import React, { useEffect, useState } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';
import Svg, { Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { appColor } from '@/ui/theme';
import type { IntroPageKey } from '../Auth.types';

/**
 * 앱 소개 그림 3장 = 원본 app/login.html `.iart` 안 (.ix-fl / .ix-att / .ix-sts) 값 그대로.
 * 웹은 원본이 따로라 '@/ui/screens/auth/IntroArtwork'를 계속 쓴다.
 */
export function AppIntroArtwork({ page }: { page: IntroPageKey }) {
  if (page === 'flood') return <Flood />;
  if (page === 'attach') return <Attach />;
  return <Studio />;
}

/* .ix-rise: m-up .45s cubic-bezier(.2,.8,.2,1), delay i*70ms + .18s, translateY 10 → 0 */
function Rise({ i, style, children }: { i: number; style?: object; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(k ? 0 : 1));
  useEffect(() => {
    if (!k) return;
    const a = Animated.timing(v, { toValue: 1, duration: 450 * k, delay: (i * 70 + 180) * k, easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [i, k, v]);
  return <Animated.View style={[style, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }) }] }]}>{children}</Animated.View>;
}

/* 그림 1 — 끝없이 올라오는 공시·뉴스·리포트 */
type Kind = 'gs' | 'ns' | 'rp' | 'pr';
const FLOWS: readonly (readonly [Kind, number, number])[][] = [
  [['gs', 50, 31], ['ns', 42, 54], ['rp', 55, 36], ['ns', 38, 47], ['gs', 53, 29], ['pr', 35, 50]],
  [['ns', 47, 38], ['rp', 54, 30], ['gs', 40, 53], ['pr', 49, 34], ['ns', 43, 55], ['gs', 56, 37]],
  [['pr', 37, 48], ['gs', 54, 35], ['ns', 44, 52], ['rp', 52, 32], ['ns', 41, 46], ['gs', 48, 40]],
];
const KIND: Record<Kind, { label: string; bg: string; ink: string }> = {
  gs: { label: '공시', bg: '#FBEDED', ink: '#E5484D' },
  ns: { label: '뉴스', bg: '#E8EDF5', ink: '#000000' },
  pr: { label: '주가', bg: '#E6F0E2', ink: '#1E8E4E' },
  rp: { label: '리포트', bg: '#F1EEFB', ink: '#5E5668' },
};
const CARD_PITCH = 48 + 10; /* .ix-cd height 48 + margin-bottom 10 */
const DURATIONS = [22000, 17000, 26000];

function Flood() {
  const k = useMotionK();
  const [values] = useState(() => [new Animated.Value(0), new Animated.Value(0), new Animated.Value(0)]);
  useEffect(() => {
    if (!k) return;
    const loops = values.map((value, i) => {
      value.setValue(0);
      /* translateY(-50%) = 카드 6장 */
      return Animated.loop(Animated.timing(value, { toValue: -CARD_PITCH * 6, duration: DURATIONS[i] * k, easing: Easing.linear, useNativeDriver: NATIVE }));
    });
    loops.forEach((loop) => loop.start());
    return () => loops.forEach((loop) => loop.stop());
  }, [k, values]);
  return (
    <View style={StyleSheet.absoluteFill}>
      <View style={a1.fl}>
        {FLOWS.map((flow, ci) => (
          <Animated.View key={ci} style={[a1.col, { transform: [{ translateY: values[ci] }] }]}>
            {[...flow, ...flow].map(([kind, w1, w2], i) => (
              <View key={i} style={a1.cd}>
                <View style={[a1.kd, { backgroundColor: KIND[kind].bg }]}><Text style={[a1.kdT, { color: KIND[kind].ink }]}>{KIND[kind].label}</Text></View>
                <View style={a1.bars}>
                  <View style={[a1.bar, { width: `${w1}%`, backgroundColor: '#C9CDD4' }]} />
                  <View style={[a1.bar, { width: `${w2}%`, backgroundColor: '#E3E6EA' }]} />
                </View>
              </View>
            ))}
          </Animated.View>
        ))}
      </View>
      <Fade edge="top" />
      <Fade edge="bottom" />
    </View>
  );
}

/* .ix-fade-t / -b: height 48, linear-gradient(#F4F5F7 ↔ transparent) */
function Fade({ edge }: { edge: 'top' | 'bottom' }) {
  const id = `ixfade${edge}`;
  return (
    <View pointerEvents="none" style={[a1.fade, edge === 'top' ? { top: 0 } : { bottom: 0 }]}>
      <Svg width="100%" height="100%" preserveAspectRatio="none">
        <Defs>
          <LinearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#F4F5F7" stopOpacity={edge === 'top' ? 1 : 0} />
            <Stop offset="1" stopColor="#F4F5F7" stopOpacity={edge === 'top' ? 0 : 1} />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill={`url(#${id})`} />
      </Svg>
    </View>
  );
}

/* 그림 2 — 메모 한 줄 → AI가 붙여 주는 소식 */
function Attach() {
  const k = useMotionK();
  const [dot] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!k) return;
    dot.setValue(0);
    /* v2-dotrun: calc(1.6s*max(k,1)) cubic-bezier(.2,.8,.2,1) infinite — left 0 → 100%-6px, 0~15% 나타남 · 85~100% 사라짐 */
    const loop = Animated.loop(Animated.timing(dot, { toValue: 1, duration: 1600 * Math.max(k, 1), easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: NATIVE }));
    loop.start();
    return () => loop.stop();
  }, [dot, k]);
  return (
    <View style={a2.att}>
      <Rise i={0} style={a2.mpaper}>
        <View style={a2.pp}>
          <View style={a2.r}>
            <Text style={a2.rT}>내 메모</Text>
            <View style={a2.plug}>
              <Svg width={14} height={14} viewBox="0 0 14 14" fill="none">
                <Path d="M5.25 1.75V4.08333M8.75 1.75V4.08333" stroke="#000000" strokeWidth={1.2} strokeLinecap="round" />
                <Path d="M3.7915 4.08301H10.2082V6.41634C10.2082 7.26724 9.87015 8.0833 9.26847 8.68498C8.66679 9.28665 7.85074 9.62467 6.99984 9.62467C6.14893 9.62467 5.33288 9.28665 4.7312 8.68498C4.12952 8.0833 3.7915 7.26724 3.7915 6.41634V4.08301Z" fill="#16161C" />
                <Path d="M7 9.625V12.25" stroke="#000000" strokeWidth={1.2} strokeLinecap="round" />
              </Svg>
            </View>
          </View>
          <Text keepAll style={a2.b}>HBM 수요 계속 갈까?</Text>
        </View>
        <View style={a2.fold}>
          <Svg width={28} height={28} viewBox="0 0 30 30" fill="none">
            <Path d="M30 0V30H0L30 0Z" fill="#F4F5F7" />
            <Path d="M0 9C0 3 3 0 9 0H30L0 30V9Z" fill="#EFBF2A" />
          </Svg>
        </View>
      </Rise>
      <View style={a2.lnk}>
        <Animated.View style={[a2.dot, {
          opacity: dot.interpolate({ inputRange: [0, 0.15, 0.85, 1], outputRange: [0, 1, 1, 0] }),
          transform: [{ translateX: dot.interpolate({ inputRange: [0, 1], outputRange: [0, 18 - 6] }) }],
        }]} />
      </View>
      <View style={a2.ncs}>
        <Note i={2} kind="뉴스" text="HBM4 공급 확대 소식이 나왔어요" bg="#E3EDFF" bar="#3D73F0" />
        <Note i={3} kind="공시" text="3분기 실적 발표가 예정돼 있어요" bg="#EEE8FF" bar="#7046F5" />
      </View>
    </View>
  );
}

function Note({ i, kind, text, bg, bar }: { i: number; kind: string; text: string; bg: string; bar: string }) {
  return (
    <Rise i={i} style={[a2.nc, { backgroundColor: bg }]}>
      <View style={[a2.ncBar, { backgroundColor: bar }]} />
      <Text style={a2.ncS} numberOfLines={1}>{kind} · AI가 찾아 붙임</Text>
      <Text keepAll style={a2.ncB}>{text}</Text>
    </Rise>
  );
}

/* 그림 3 — 라디오와 주간보고서 */
const WAVE = [14, 26, 18, 34, 22, 30, 12, 28, 20, 32];

function Studio() {
  return (
    <View style={a3.sts}>
      <Rise i={0} style={a3.stc}>
        <View style={a3.h}>
          <View style={[a3.ic, { backgroundColor: '#D6E4FF' }]}>
            <Svg width={20} height={20} viewBox="0 0 22 22" fill="none">
              <Path d="M3.66675 9.16675V12.8334M7.33341 6.41675V15.5834M11.0001 3.66675V18.3334M14.6667 7.33341V14.6667M18.3334 10.0834V11.9167" stroke="#2F6BDB" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
            </Svg>
          </View>
          <View style={a3.hText}><Text style={a3.hB} numberOfLines={1}>AI 오디오</Text><Text style={a3.hS} numberOfLines={1}>내 종목 라디오</Text></View>
        </View>
        <View style={a3.wv}>{WAVE.map((h, i) => <WaveBar key={i} h={h} delay={i * 90} />)}</View>
        <View style={a3.pl}>
          <View style={a3.play}>
            <Svg width={14} height={14} viewBox="0 0 24 24" fill="none"><Path d="M8 5.5v13a1 1 0 0 0 1.5.9l10-6.5a1 1 0 0 0 0-1.7l-10-6.5A1 1 0 0 0 8 5.5Z" fill="#FFFFFF" /></Svg>
          </View>
          <View style={a3.track}><View style={a3.trackOn} /></View>
        </View>
      </Rise>
      <Rise i={1} style={a3.stc}>
        <View style={a3.h}>
          <View style={[a3.ic, { backgroundColor: '#FFDADB' }]}>
            <Svg width={20} height={20} viewBox="0 0 22 22" fill="none">
              <Path d="M6.41667 2.75H12.8333L17.4167 7.33333V18.3333C17.4167 18.5764 17.3201 18.8096 17.1482 18.9815C16.9763 19.1534 16.7431 19.25 16.5 19.25H6.41667C6.17355 19.25 5.94039 19.1534 5.76849 18.9815C5.59658 18.8096 5.5 18.5764 5.5 18.3333V3.66667C5.5 3.42355 5.59658 3.19039 5.76849 3.01849C5.94039 2.84658 6.17355 2.75 6.41667 2.75Z" stroke="#D6404A" strokeWidth={1.8} strokeLinejoin="round" />
              <Path d="M12.8333 2.75V7.33333H17.4166" stroke="#D6404A" strokeWidth={1.8} strokeLinejoin="round" />
              <Path d="M8.70825 15.5834V13.7501M11.4583 15.5834V11.9167M14.2083 15.5834V12.8334" stroke="#D6404A" strokeWidth={1.8} strokeLinecap="round" />
            </Svg>
          </View>
          <View style={a3.hText}><Text style={a3.hB} numberOfLines={1}>AI 주간보고서</Text><Text style={a3.hS} numberOfLines={1}>한 주를 한 장으로</Text></View>
        </View>
        <Svg width="100%" height={40} viewBox="0 0 200 40" preserveAspectRatio="none" fill="none">
          <Path d="M0 30L28 26L56 29L84 18L112 21L140 10L168 13L200 4V40H0Z" fill="#E5484D" fillOpacity={0.08} />
          <Path d="M0 30L28 26L56 29L84 18L112 21L140 10L168 13L200 4" stroke="#E5484D" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        </Svg>
        <View style={a3.br}><View style={[a3.brI, { width: '100%', backgroundColor: '#C9CDD4' }]} /><View style={[a3.brI, { width: '70%', backgroundColor: '#E3E6EA' }]} /></View>
      </Rise>
    </View>
  );
}

/* .ix-wv i: wave 1s ease-in-out infinite alternate, scaleY .35 ↔ 1, delay i*0.09s */
function WaveBar({ h, delay }: { h: number; delay: number }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(k ? 0.35 : 1));
  useEffect(() => {
    if (!k) return;
    const ease = Easing.inOut(Easing.ease);
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(v, { toValue: 1, duration: 1000 * k, easing: ease, useNativeDriver: NATIVE }),
      Animated.timing(v, { toValue: 0.35, duration: 1000 * k, easing: ease, useNativeDriver: NATIVE }),
    ]));
    const t = setTimeout(() => loop.start(), delay * k);
    return () => { clearTimeout(t); loop.stop(); };
  }, [delay, k, v]);
  return <Animated.View style={[a3.wvI, { height: h, transform: [{ scaleY: v }] }]} />;
}

const a1 = StyleSheet.create({
  fl: { position: 'absolute', left: 8, right: 8, top: 0, flexDirection: 'row', gap: 10 },
  col: { flex: 1, minWidth: 0 },
  cd: { height: 48, marginBottom: 10, borderRadius: 12, borderWidth: 1, borderColor: '#E9EBEE', backgroundColor: '#FFFFFF', flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 10 },
  kd: { height: 22, borderRadius: 6, paddingHorizontal: 6, justifyContent: 'center' },
  kdT: { fontSize: 13, lineHeight: 17.3, fontWeight: '600' },
  bars: { flex: 1, minWidth: 0, gap: 6 },
  bar: { height: 6, borderRadius: 3 },
  fade: { position: 'absolute', left: 0, right: 0, height: 48 },
});

const a2 = StyleSheet.create({
  att: { ...StyleSheet.absoluteFill, flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14 },
  mpaper: { width: 132, height: 150 },
  pp: { ...StyleSheet.absoluteFill, borderTopLeftRadius: 16, borderTopRightRadius: 16, borderBottomRightRadius: 0, borderBottomLeftRadius: 16, backgroundColor: '#FCEAAA', paddingVertical: 12, paddingHorizontal: 14, gap: 8 },
  r: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  rT: { fontSize: 13.5, lineHeight: 19.4, color: '#4A4A55', fontWeight: '500' },
  plug: { width: 26, height: 26, borderRadius: 13, backgroundColor: 'rgba(255,255,255,0.8)', alignItems: 'center', justifyContent: 'center' },
  b: { fontSize: 17, lineHeight: 23, fontWeight: '800', color: '#16161C' },
  fold: { position: 'absolute', right: 0, bottom: 0 },
  lnk: { height: 2, width: 18, borderRadius: 1, backgroundColor: '#D5D8DD' },
  dot: { position: 'absolute', left: 0, top: -2, width: 6, height: 6, borderRadius: 3, backgroundColor: appColor.accent },
  ncs: { flex: 1, minWidth: 0, gap: 10 },
  nc: { minHeight: 66, borderRadius: 14, paddingTop: 9, paddingBottom: 9, paddingRight: 10, paddingLeft: 14, justifyContent: 'center', gap: 2, overflow: 'hidden' },
  ncBar: { position: 'absolute', left: 0, top: '50%', marginTop: -15, width: 3, height: 30, borderRadius: 1.5 },
  ncS: { fontSize: 13, lineHeight: 19.5, color: '#575B63', fontWeight: '500', flexShrink: 1 },
  ncB: { fontSize: 15, lineHeight: 21.4, fontWeight: '700', color: '#15171A' },
});

const a3 = StyleSheet.create({
  sts: { ...StyleSheet.absoluteFill, flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16 },
  stc: { flex: 1, minWidth: 0, height: 180, borderRadius: 18, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#FFFFFF', padding: 14, justifyContent: 'space-between' },
  h: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  ic: { width: 36, height: 36, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
  hText: { flex: 1, minWidth: 0 },
  hB: { fontSize: 15, lineHeight: 22.5, fontWeight: '700', color: '#16171A', flexShrink: 1 },
  hS: { fontSize: 13, lineHeight: 19.5, color: '#6B7079', flexShrink: 1 },
  wv: { height: 36, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4 },
  wvI: { width: 4, borderRadius: 2, backgroundColor: '#2F6BDB', opacity: 0.85 },
  pl: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  play: { width: 30, height: 30, borderRadius: 15, backgroundColor: appColor.accent, alignItems: 'center', justifyContent: 'center' },
  track: { flex: 1, height: 4, borderRadius: 2, backgroundColor: '#ECEEF1' },
  trackOn: { width: '38%', height: 4, borderRadius: 2, backgroundColor: appColor.accent },
  br: { gap: 7 },
  brI: { height: 7, borderRadius: 4 },
});
