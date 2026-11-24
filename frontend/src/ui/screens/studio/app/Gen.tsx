import React, { useEffect, useState } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { PressScale } from '@/ui/motion/PressScale';
import type { GenJob, StepState } from '@/store/studioPlayer';
import { Head } from '../../my/app/parts';

/**
 * 앱 만드는 중 = 원본 studio.html #pgGen (07 · 오디오 / 주간보고서는 빨간 문서 아이콘)
 * 동그라미 90(#DCE7FF · 물결 고리 · 막대 5개 움직임 / 실패면 빨강 !) · 제목 19 · 조건 13 ·
 * 단계 카드(44 줄 · 대기/진행 중/완료/실패) · 안내 12.5 · [다른 화면 보기 | 다시 시도] · 아래 안내 12
 */
const C = { a: '#8569E3', a2: '#6A42AB', ink: '#16171A', ink2: '#575B63', ink3: '#9A9EA7' };
const LABEL: Record<StepState, string> = { wait: '대기', run: '진행 중', done: '완료', bad: '실패' };

export function AppGen({ job, steps, onBack, onAway, onRetry }: { job: GenJob; steps: string[]; onBack: () => void; onAway: () => void; onRetry: () => void }) {
  const insets = useSafeAreaInsets();
  const fail = job.status === 'fail';
  const doc = job.kind === 'report';
  const T = doc ? { head: 'AI 주간보고서', ing: '보고서를 만드는 중이에요', bad: '보고서를 만들지 못했어요' } : { head: 'AI 오디오', ing: '오디오를 만드는 중이에요', bad: '오디오를 만들지 못했어요' };
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <Head title={T.head} onBack={onBack} />
      <View style={st.gw}>
        <View style={[st.gic, doc && { backgroundColor: '#FFE1E1' }, fail && { backgroundColor: '#FFE4E4' }]}>
          {!fail ? <Ripple color={doc ? '#FFE1E1' : '#DCE7FF'} /> : null}
          {fail ? <Svg width={34} height={34} viewBox="0 0 24 24" fill="none" stroke="#E5484D" strokeWidth={2.4} strokeLinecap="round"><Path d="M12 7v6M12 16.5h.01" /></Svg> : doc ? <Doc /> : <Eq />}
        </View>
        <Text style={st.h}>{fail ? T.bad : T.ing}</Text>
        <Text style={st.gs}>{job.sub}</Text>
        <View style={st.steps}>
          {steps.map((t, i) => {
            const s = job.steps[i];
            return (
              <View key={t} style={st.st} accessibilityLabel={`${t} ${LABEL[s]}`}>
                <View style={[st.sti, s === 'done' && { backgroundColor: '#1F8A4C', borderWidth: 0 }, s === 'bad' && { backgroundColor: '#E5484D', borderWidth: 0 }, s === 'run' && { borderColor: C.a }]}>
                  {s === 'done' ? <Svg width={14} height={14} viewBox="0 0 14 14" fill="none"><Path d="M3 7.3l2.6 2.6L11 4.4" stroke="#fff" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" /></Svg> : s === 'run' ? <Spin /> : null}
                </View>
                <Text style={[st.stT, (s === 'run' || s === 'done') && { color: C.ink }, s === 'bad' && { color: '#C2262E' }]}>{t}</Text>
                <Text style={[st.stS, s === 'run' && { color: C.a2 }, s === 'done' && { color: '#1B7A45' }, s === 'bad' && { color: '#C2262E' }, s === 'wait' && { color: '#B0B4BB' }]}>{LABEL[s]}</Text>
              </View>
            );
          })}
        </View>
        <Text style={[st.note, fail && { color: '#1F8A4C', fontWeight: '700' }]}>{fail ? '사용량은 그대로 돌려드렸어요' : '만들지 못하면 사용량은 그대로 돌려드려요'}</Text>
        <View style={{ alignSelf: 'stretch' }}>
          <PressScale onPress={fail ? onRetry : onAway} accessibilityRole="button" style={st.cta}><Text style={st.ctaT}>{fail ? '다시 시도' : '다른 화면 보기'}</Text></PressScale>
        </View>
        <Text style={st.cap}>{fail ? '잠시 뒤 다시 해 보거나 종목을 줄여 보세요' : '다 되면 알려 드리고, 스튜디오 탭에 점을 표시해요'}</Text>
      </View>
    </View>
  );
}

/* .eq: 막대 5개(3.5 · 파랑) 위아래 */
function Eq() {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.loop(Animated.timing(v, { toValue: 1, duration: 900 * k, easing: Easing.inOut(Easing.ease), useNativeDriver: NATIVE }));
    a.start();
    return () => a.stop();
  }, [v, k]);
  const ph = [0, 0.22, 0.55, 0.11, 0.39];
  return (
    <View style={{ flexDirection: 'row', gap: 3, alignItems: 'center', height: 30 }}>
      {ph.map((p, i) => (
        <Animated.View key={i} style={{ width: 3.5, height: 30, borderRadius: 2, backgroundColor: '#3D73F0', transform: [{ scaleY: v.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0.33 + p * 0.3, 1 - p * 0.4, 0.33 + p * 0.3] }) }] }} />
      ))}
    </View>
  );
}

/* .gdoc: 빨간 문서 · 글줄이 차례로 써지는 느낌 (원본 wl 1.4s) */
function Doc() {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.loop(Animated.timing(v, { toValue: 1, duration: 1400 * k, easing: Easing.inOut(Easing.ease), useNativeDriver: NATIVE }));
    a.start();
    return () => a.stop();
  }, [v, k]);
  return (
    <View style={{ width: 34, height: 40 }}>
      <Svg width={34} height={40} viewBox="0 0 34 40" fill="none" style={{ position: 'absolute' }}><Path d="M4 2h18l8 8v28H4z" fill="#fff" stroke="#E5484D" strokeWidth={2.2} strokeLinejoin="round" /></Svg>
      {[17, 23, 29].map((y, i) => (
        <Animated.View key={y} style={{ position: 'absolute', left: 9, top: y - 1.2, height: 2.4, width: i === 2 ? 9 : 14, borderRadius: 1.2, backgroundColor: '#E5484D', transformOrigin: 'left', transform: [{ scaleX: v.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0.15 + i * 0.1, 1, 0.15 + i * 0.1] }) }] }} />
      ))}
    </View>
  );
}

/* .gic::after 물결 고리 (1.6s) */
function Ripple({ color }: { color: string }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.loop(Animated.timing(v, { toValue: 1, duration: 1600 * k, easing: Easing.out(Easing.ease), useNativeDriver: NATIVE }));
    a.start();
    return () => a.stop();
  }, [v, k]);
  return <Animated.View pointerEvents="none" style={[st.ring, { borderColor: color }, { opacity: v.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }), transform: [{ scale: v.interpolate({ inputRange: [0, 1], outputRange: [1, 1.25] }) }] }]} />;
}

function Spin() {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.loop(Animated.timing(v, { toValue: 1, duration: 800 * k, easing: Easing.linear, useNativeDriver: NATIVE }));
    a.start();
    return () => a.stop();
  }, [v, k]);
  return <Animated.View style={{ position: 'absolute', top: -2, left: -2, right: -2, bottom: -2, borderRadius: 12, borderWidth: 2, borderColor: '#E4DDFB', borderTopColor: C.a, transform: [{ rotate: v.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }] }} />;
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F3F4F6' },
  gw: { flex: 1, alignItems: 'center', paddingTop: 56, paddingHorizontal: 22 },
  gic: { width: 90, height: 90, borderRadius: 45, backgroundColor: '#DCE7FF', alignItems: 'center', justifyContent: 'center' },
  ring: { position: 'absolute', top: -8, left: -8, right: -8, bottom: -8, borderRadius: 53, borderWidth: 2, borderColor: '#DCE7FF' },
  h: { fontSize: 19, lineHeight: 26, fontWeight: '700', color: C.ink, marginTop: 18, marginBottom: 4 },
  gs: { fontSize: 13, lineHeight: 18, color: C.ink3 },
  steps: { alignSelf: 'stretch', backgroundColor: '#FFFFFF', borderRadius: 18, paddingVertical: 8, paddingHorizontal: 16, marginTop: 20, marginBottom: 12 },
  st: { flexDirection: 'row', alignItems: 'center', gap: 12, height: 44 },
  sti: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: '#D5D8DD', alignItems: 'center', justifyContent: 'center' },
  stT: { fontSize: 14.5, lineHeight: 20, fontWeight: '600', color: '#B0B4BB' },
  stS: { marginLeft: 'auto', fontSize: 12.5, lineHeight: 17, fontWeight: '600' },
  note: { fontSize: 12.5, lineHeight: 18, color: C.ink2, marginBottom: 16 },
  cta: { height: 50, borderRadius: 15, backgroundColor: '#ECEDF1', alignItems: 'center', justifyContent: 'center' },
  ctaT: { fontSize: 16, lineHeight: 22, fontWeight: '800', color: C.ink },
  cap: { fontSize: 12, lineHeight: 17, color: C.ink3, marginTop: 8 },
});
