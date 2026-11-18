/**
 * 뼈대 → 내용 (Lucian #079)
 *  - Shimmer: 회색 뼈대 위로 흰 빛줄기가 1.1초마다 왼쪽 → 오른쪽 (체험판 .sk · shim)
 *    여러 뼈대가 한 줄기처럼 지나가도록 offset_x(뼈대의 화면 x)를 넘기면 맞춰짐.
 *  - SkeletonSwap: 불러오는 동안 뼈대 → 다 오면 뼈대가 .25초 걷히고 → 그 다음에 내용이 나타남.
 *    (11.17 검수: 빈 보드 안내가 뼈대 밑에 겹쳐 보이지 않게 순서대로)
 * 빛줄기는 그라데이션 패키지 없이 투명도가 다른 세로 띠 7개로 만듦.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { Animated, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Appear } from '@/components/motion/Appear';
import { EASE, LINEAR, ND, tween, useReduceMotion, useValue } from '@/components/motion/motion';

const M = { base: '#EEF0F3', shine: '#FFFFFF' } as const;
const SWEEP = 412;
const BAND = [0.08, 0.3, 0.6, 0.9, 0.6, 0.3, 0.08];
const STRIP = 24;

export function Shimmer({ style, offset_x = 0, color = M.base }: { style?: StyleProp<ViewStyle>; offset_x?: number; color?: string }) {
  const t = useValue(0);
  const still = useReduceMotion();
  useEffect(() => {
    if (still) return;
    const loop = Animated.loop(tween(t, 1, 1100, LINEAR, ND));
    loop.start();
    return () => loop.stop();
  }, [t, still]);
  const translateX = t.interpolate({ inputRange: [0, 1], outputRange: [-SWEEP - offset_x, SWEEP - offset_x] });
  return (
    <View style={[st.base, { backgroundColor: color }, style]}>
      {!still && (
        <Animated.View pointerEvents="none" style={[st.band, { transform: [{ translateX }, { skewX: '-10deg' }] }]}>
          {BAND.map((o, i) => <View key={i} style={[st.strip, { opacity: o }]} />)}
        </Animated.View>
      )}
    </View>
  );
}

export function SkeletonSwap({ loading, skeleton, children }: { loading: boolean; skeleton: ReactNode; children: ReactNode }) {
  const [sk, setSk] = useState(loading);
  const o = useValue(loading ? 1 : 0);
  useEffect(() => {
    if (loading) { setSk(true); o.setValue(1); return; }
    const a = tween(o, 0, 250, EASE);
    a.start(({ finished }) => { if (finished) setSk(false); });
    return () => a.stop();
  }, [loading, o]);
  if (sk) return <Animated.View style={{ opacity: o }}>{skeleton}</Animated.View>;
  return <Appear kind="fade">{children}</Appear>;
}

const st = StyleSheet.create({
  base: { overflow: 'hidden' },
  band: { position: 'absolute', top: 0, bottom: 0, left: SWEEP / 2 - (BAND.length * STRIP) / 2, flexDirection: 'row' },
  strip: { width: STRIP, height: '100%', backgroundColor: M.shine },
});
