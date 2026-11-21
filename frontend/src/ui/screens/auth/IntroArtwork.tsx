import React, { useEffect, useState } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import type { IntroPageKey } from './Auth.types';

export function IntroArtwork({ page, compact }: { page: IntroPageKey; compact: boolean }) {
  if (page === 'flood') return <Flood compact={compact} />;
  if (page === 'attach') return <Attach compact={compact} />;
  return <Studio compact={compact} />;
}

const FLOWS = [
  [['공시', 52, 31], ['뉴스', 42, 54], ['리포트', 55, 36], ['뉴스', 38, 47], ['공시', 53, 29], ['주가', 35, 50]],
  [['뉴스', 47, 38], ['리포트', 54, 30], ['공시', 40, 53], ['주가', 49, 34], ['뉴스', 43, 55], ['공시', 56, 37]],
  [['주가', 37, 48], ['공시', 54, 35], ['뉴스', 44, 52], ['리포트', 52, 32], ['뉴스', 41, 46], ['공시', 48, 40]],
] as const;
const KIND: Record<string, { bg: string; ink: string }> = {
  공시: { bg: '#FBEDED', ink: '#E5484D' },
  뉴스: { bg: '#E8EDF5', ink: '#16171A' },
  주가: { bg: '#E6F0E2', ink: '#1E8E4E' },
  리포트: { bg: '#F1EEFB', ink: '#5E5668' },
};

function Flood({ compact }: { compact: boolean }) {
  const k = useMotionK();
  const [values] = useState(() => [new Animated.Value(0), new Animated.Value(0), new Animated.Value(0)]);
  const cardH = compact ? 56 : 52;
  const gap = compact ? 12 : 12;
  const loopH = (cardH + gap) * 6;
  useEffect(() => {
    const loops = values.map((value, i) => {
      value.setValue(0);
      return Animated.loop(Animated.timing(value, {
        toValue: -loopH,
        duration: [22000, 17000, 26000][i] * k,
        easing: Easing.linear,
        useNativeDriver: NATIVE,
      }));
    });
    loops.forEach((loop) => loop.start());
    return () => loops.forEach((loop) => loop.stop());
  }, [k, loopH, values]);
  return (
    <View style={art.flood}>
      <View style={[art.columns, { gap: compact ? 10 : 16, paddingHorizontal: compact ? 8 : 8 }]}>
        {FLOWS.map((flow, ci) => (
          <Animated.View key={ci} style={{ flex: 1, gap, transform: [{ translateY: values[ci] }] }}>
            {[...flow, ...flow].map(([kind, a, b], i) => (
              <View key={i} style={[art.flowCard, { minHeight: cardH, paddingHorizontal: compact ? 9 : 12, gap: compact ? 8 : 10 }]}>
                <View style={[art.kind, { backgroundColor: KIND[kind].bg }]}>
                  <Text style={[art.kindText, { color: KIND[kind].ink }]}>{kind}</Text>
                </View>
                <View style={art.bars}>
                  <View style={[art.bar, { width: `${a}%`, backgroundColor: '#C9CDD4' }]} />
                  <View style={[art.bar, { width: `${b}%` }]} />
                </View>
              </View>
            ))}
          </Animated.View>
        ))}
      </View>
      <View pointerEvents="none" style={[art.fade, art.fadeTop]} />
      <View pointerEvents="none" style={[art.fade, art.fadeBottom]} />
    </View>
  );
}

function Attach({ compact }: { compact: boolean }) {
  const k = useMotionK();
  const [dot] = useState(() => new Animated.Value(0));
  useEffect(() => {
    dot.setValue(0);
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(dot, { toValue: 1, duration: 900 * k, easing: Easing.inOut(Easing.quad), useNativeDriver: NATIVE }),
      Animated.timing(dot, { toValue: 0, duration: 50 * k, useNativeDriver: NATIVE }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [dot, k]);
  return (
    <View style={[art.attach, { gap: compact ? 10 : 12, paddingHorizontal: compact ? 14 : 24 }]}>
      <View style={[art.memo, compact && art.memoCompact]}>
        <View style={art.memoHead}>
          <Text style={art.memoSmall}>내 메모</Text>
          <View style={art.plug}><Text style={art.plugText}>↕</Text></View>
        </View>
        <Text style={[art.memoTitle, compact && art.memoTitleCompact]}>HBM 수요 계속{compact ? '\n' : ' '}갈까?</Text>
        <View style={art.fold} />
      </View>
      <View style={[art.connector, { width: compact ? 25 : 36 }]}>
        <Animated.View style={[art.dot, { transform: [{ translateX: dot.interpolate({ inputRange: [0, 1], outputRange: [0, compact ? 21 : 32] }) }] }]} />
      </View>
      <View style={{ flex: 1, gap: compact ? 10 : 10 }}>
        <UpdateCard kind="뉴스" text="HBM4 공급 확대 소식이 나왔어요" bg="#E3EDFF" accent="#3D73F0" compact={compact} />
        <UpdateCard kind="공시" text="3분기 실적 발표가 예정돼 있어요" bg="#EEE8FF" accent="#7046F5" compact={compact} />
      </View>
    </View>
  );
}

function UpdateCard({ kind, text, bg, accent, compact }: { kind: string; text: string; bg: string; accent: string; compact: boolean }) {
  return (
    <View style={[art.update, { backgroundColor: bg, minHeight: compact ? 78 : 66, paddingLeft: compact ? 12 : 16 }]}>
      <View style={[art.updateAccent, { backgroundColor: accent }]} />
      <Text style={[art.updateSub, compact && art.updateSubCompact]}>{kind} · AI가 찾아 붙임</Text>
      <Text numberOfLines={compact ? 2 : 1} style={[art.updateTitle, compact && art.updateTitleCompact]}>{text}</Text>
    </View>
  );
}

function Studio({ compact }: { compact: boolean }) {
  return (
    <View style={[art.studio, { gap: compact ? 10 : 16, paddingHorizontal: compact ? 0 : 24 }]}>
      <StudioCard title="AI 오디오" sub="내 종목 라디오" color="#D6E4FF" icon="wave" compact={compact} />
      <StudioCard title="AI 주간보고서" sub="한 주를 한 장으로" color="#FFDADB" icon="report" compact={compact} />
    </View>
  );
}

function StudioCard({ title, sub, color, icon, compact }: { title: string; sub: string; color: string; icon: 'wave' | 'report'; compact: boolean }) {
  const bars = [10, 18, 14, 22, 16, 25, 13, 27, 19, 29];
  return (
    <View style={[art.studioCard, compact && art.studioCardCompact]}>
      <View style={art.studioHead}>
        <View style={[art.studioIcon, { backgroundColor: color }]}>
          {icon === 'wave' ? <View style={art.miniWave}>{[8, 16, 22, 14, 10].map((h, i) => <View key={i} style={{ width: 2, height: h, borderRadius: 2, backgroundColor: '#4D7FE8' }} />)}</View> : <Text style={art.reportIcon}>▥</Text>}
        </View>
        <View style={{ flex: 1 }}>
          <Text numberOfLines={1} style={[art.studioTitle, compact && art.studioTitleCompact]}>{title}</Text>
          <Text numberOfLines={1} style={art.studioSub}>{sub}</Text>
        </View>
      </View>
      {icon === 'wave' ? (
        <>
          <View style={art.wave}>{bars.map((h, i) => <View key={i} style={{ width: 4, height: h, borderRadius: 3, backgroundColor: '#4D7FE8' }} />)}</View>
          <View style={art.player}><View style={art.play}><Text style={art.playText}>▶</Text></View><View style={art.track}><View style={art.trackOn} /></View></View>
        </>
      ) : (
        <>
          <Svg width="100%" height={44} viewBox="0 0 190 44" preserveAspectRatio="none"><Path d="M0 32 28 28 56 31 84 20 112 23 140 12 166 15 190 6" fill="none" stroke="#E5484D" strokeWidth={2} /><Path d="M0 32 28 28 56 31 84 20 112 23 140 12 166 15 190 6v38H0Z" fill="#E5484D" opacity={0.08} /></Svg>
          <View style={art.reportBars}><View style={[art.reportBar, { width: '88%' }]} /><View style={[art.reportBar, { width: '60%' }]} /></View>
        </>
      )}
    </View>
  );
}

const art = StyleSheet.create({
  flood: { flex: 1, overflow: 'hidden', backgroundColor: '#F4F5F7' },
  columns: { position: 'absolute', left: 0, right: 0, top: 0, flexDirection: 'row' },
  flowCard: { flexDirection: 'row', alignItems: 'center', borderRadius: 12, borderWidth: 1, borderColor: '#E9EBEE', backgroundColor: '#FFFFFF' },
  kind: { borderRadius: 6, paddingHorizontal: 7, paddingVertical: 4 },
  kindText: { fontSize: 13, lineHeight: 16, fontWeight: '500' },
  bars: { flex: 1, gap: 6 },
  bar: { height: 7, borderRadius: 4, backgroundColor: '#E3E6EA' },
  fade: { position: 'absolute', left: 0, right: 0, height: 44, backgroundColor: 'rgba(244,245,247,0.78)' },
  fadeTop: { top: 0 },
  fadeBottom: { bottom: 0 },
  attach: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center' },
  memo: { width: 184, height: 152, borderRadius: 16, borderBottomRightRadius: 0, backgroundColor: '#FCEAAA', paddingHorizontal: 16, paddingTop: 14 },
  memoCompact: { width: 132, height: 150, paddingHorizontal: 13 },
  memoHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  memoSmall: { fontSize: 13, lineHeight: 20, color: '#4A4A55', fontWeight: '500' },
  plug: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.8)' },
  plugText: { fontSize: 14, lineHeight: 16, fontWeight: '700' },
  memoTitle: { marginTop: 8, fontSize: 20, lineHeight: 27, fontWeight: '700', color: '#16161C' },
  memoTitleCompact: { fontSize: 18, lineHeight: 25 },
  fold: { position: 'absolute', right: 0, bottom: 0, width: 30, height: 30, borderTopWidth: 30, borderLeftWidth: 30, borderTopColor: 'transparent', borderLeftColor: '#EFBF2A' },
  connector: { height: 2, backgroundColor: '#D5D8DD', borderRadius: 2 },
  dot: { position: 'absolute', left: -1, top: -2, width: 6, height: 6, borderRadius: 3, backgroundColor: '#111111' },
  update: { justifyContent: 'center', borderRadius: 14, paddingRight: 10, overflow: 'hidden' },
  updateAccent: { position: 'absolute', left: 0, top: 18, width: 3, height: 30, borderRadius: 2 },
  updateSub: { fontSize: 13, lineHeight: 20, color: '#575B63', fontWeight: '500' },
  updateSubCompact: { fontSize: 11, lineHeight: 16 },
  updateTitle: { fontSize: 15, lineHeight: 23, color: '#15171A', fontWeight: '700' },
  updateTitleCompact: { fontSize: 13, lineHeight: 19 },
  studio: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center' },
  studioCard: { flex: 1, height: 168, borderRadius: 18, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#FFFFFF', padding: 16, justifyContent: 'space-between' },
  studioCardCompact: { height: 188, padding: 14, borderRadius: 16 },
  studioHead: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  studioIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  miniWave: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  reportIcon: { fontSize: 19, lineHeight: 23, color: '#D6404A', fontWeight: '700' },
  studioTitle: { fontSize: 15, lineHeight: 23, color: '#16171A', fontWeight: '700' },
  studioTitleCompact: { fontSize: 14, lineHeight: 20 },
  studioSub: { fontSize: 13, lineHeight: 20, color: '#8E8A97' },
  wave: { height: 34, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5 },
  player: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  play: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: '#15171A' },
  playText: { fontSize: 12, lineHeight: 14, color: '#FFFFFF' },
  track: { flex: 1, height: 4, borderRadius: 2, backgroundColor: '#ECEEF1' },
  trackOn: { width: '38%', height: 4, borderRadius: 2, backgroundColor: '#15171A' },
  reportBars: { gap: 7 },
  reportBar: { height: 7, borderRadius: 4, backgroundColor: '#C9CDD4' },
});
