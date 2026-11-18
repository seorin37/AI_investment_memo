/**
 * 넛지 검정 알약 (Lucian #252 announcement-pill) — 체험판 x/app 스타일의 .mx-nudge 값.
 *  - 아래 탭 위 가운데에서 26px 아래 · .95배 → 제자리 (.45s spring) · 투명도 .2s
 *  - 1.6초 뒤부터 4초마다 빛줄기가 왼쪽 → 오른쪽으로 훑음 (한 번 훑는 데 .9s)
 *  - 누르면 화살표가 3px 앞으로 (.3s) · 오른쪽 × 로 닫음
 *  - 알림(스낵)이 떠 있으면 bottom 을 올려 그 위로 비켜 섬 (.3s)
 * 문구 예: "이번 주 내 종목, 한 장으로 볼까요?" (웹 nudge.tsx 와 같은 문구는 화면이 넘김)
 */
import { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { EASE, ND, SPRING, tween, useReduceMotion, useTweenNumber, useValue } from '@/components/motion/motion';

const M = { bg: '#15171A', text: '#FFFFFF', sep: 'rgba(255,255,255,0.2)', shine: '#FFFFFF', x: '#9A9EA7', shadow: '#14171A' } as const;
const BAND = [0.06, 0.18, 0.32, 0.18, 0.06];

export function NudgePill({ text, visible, onPress, onClose, bottom = 96 }: { text: string; visible: boolean; onPress: () => void; onClose: () => void; bottom?: number }) {
  const t = useValue(0);
  const sh = useValue(0);
  const arrow = useValue(0);
  const [w, setW] = useState(0);
  const still = useReduceMotion();
  const b = useTweenNumber(bottom, 300, EASE);
  useEffect(() => { tween(t, visible ? 1 : 0, visible ? 450 : 200, visible ? SPRING : EASE, ND).start(); }, [visible, t]);
  useEffect(() => {
    if (!visible || still || !w) return;
    sh.setValue(0);
    const loop = Animated.sequence([Animated.delay(1600), Animated.loop(Animated.sequence([tween(sh, 1, 900, EASE, ND), Animated.delay(3100), tween(sh, 0, 0, EASE, ND)]))]);
    loop.start();
    return () => loop.stop();
  }, [visible, still, w, sh]);

  return (
    <Animated.View pointerEvents={visible ? 'box-none' : 'none'} style={[st.wrap, { bottom: b, opacity: t.interpolate({ inputRange: [0, 1], outputRange: [0, 1], extrapolate: 'clamp' }),
      transform: [{ translateY: t.interpolate({ inputRange: [0, 1], outputRange: [26, 0] }) }, { scale: t.interpolate({ inputRange: [0, 1], outputRange: [0.95, 1] }) }] }]}>
      <View style={st.pill} onLayout={(e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width)}>
        <Animated.View pointerEvents="none" style={[st.band, { transform: [{ translateX: sh.interpolate({ inputRange: [0, 1], outputRange: [-80, w * 1.2] }) }, { skewX: '-18deg' }] }]}>
          {BAND.map((o, i) => <View key={i} style={[st.strip, { opacity: o }]} />)}
        </Animated.View>
        <Pressable style={st.go} onPress={onPress} accessibilityRole="button"
          onPressIn={() => tween(arrow, 1, 150, EASE, ND).start()} onPressOut={() => tween(arrow, 0, 300, SPRING, ND).start()}>
          <Text style={st.text} numberOfLines={1}>{text}</Text>
          <Animated.View style={{ transform: [{ translateX: arrow.interpolate({ inputRange: [0, 1], outputRange: [0, 3] }) }] }}>
            <MobileIcon name="arrow_right" size={18} color={M.text} strokeWidth={2.2} />
          </Animated.View>
        </Pressable>
        <View style={st.sep} />
        <Pressable style={st.x} onPress={onClose} accessibilityRole="button" accessibilityLabel="닫기"><MobileIcon name="close" size={16} color={M.x} /></Pressable>
      </View>
    </Animated.View>
  );
}

const st = StyleSheet.create({
  wrap: { position: 'absolute', left: 16, right: 16, alignItems: 'center' },
  pill: { flexDirection: 'row', alignItems: 'center', height: 48, maxWidth: 380, borderRadius: 24, backgroundColor: M.bg, overflow: 'hidden', shadowColor: M.shadow, shadowOpacity: 0.25, shadowRadius: 15, shadowOffset: { width: 0, height: 12 }, elevation: 8 },
  band: { position: 'absolute', top: 0, bottom: 0, left: 0, flexDirection: 'row' },
  strip: { width: 12, height: '100%', backgroundColor: M.shine },
  go: { flexDirection: 'row', alignItems: 'center', gap: 8, height: 48, paddingLeft: 16, paddingRight: 12, flexShrink: 1 },
  text: { flexShrink: 1, fontSize: 15, lineHeight: 23, fontWeight: '700', color: M.text },
  sep: { width: 1, height: 20, backgroundColor: M.sep },
  x: { width: 44, height: 48, alignItems: 'center', justifyContent: 'center' },
});
