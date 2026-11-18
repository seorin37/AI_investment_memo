/**
 * 재생 ↔ 멈춤 (Lucian #007 play-pause-morph) — 스튜디오 라디오 카드.
 * 세모가 돌며 작아지고 두 막대가 커지며 나타남 (.32s ease) · 누르면 버튼이 .5s spring 으로 톡.
 */
import { useEffect } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { EASE, ND, SPRING, tween, useValue } from '@/components/motion/motion';

export function PlayPause({ playing, onPress, size = 44, bg, fg }: { playing: boolean; onPress: () => void; size?: number; bg: string; fg: string }) {
  const m = useValue(playing ? 1 : 0);
  const press = useValue(1);
  useEffect(() => { tween(m, playing ? 1 : 0, 320, EASE, ND).start(); }, [playing, m]);
  const tap = () => {
    Animated.sequence([tween(press, 0.88, 90, EASE, ND), tween(press, 1, 500, SPRING, ND)]).start();
    onPress();
  };
  const bar = { width: size * 0.12, height: size * 0.38, borderRadius: size * 0.04, backgroundColor: fg };
  return (
    <Pressable onPress={tap} hitSlop={4} accessibilityRole="button" accessibilityLabel={playing ? '멈춤' : '재생'}>
      <Animated.View style={[st.btn, { width: size, height: size, borderRadius: size / 2, backgroundColor: bg, transform: [{ scale: press }] }]}>
        <Animated.View style={[st.layer, { opacity: m.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }),
          transform: [{ rotate: m.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '90deg'] }) }, { scale: m.interpolate({ inputRange: [0, 1], outputRange: [1, 0.4] }) }] }]}>
          <MobileIcon name="play" size={size * 0.36} color={fg} />
        </Animated.View>
        <Animated.View style={[st.layer, st.bars, { gap: size * 0.1, opacity: m, transform: [{ scale: m.interpolate({ inputRange: [0, 1], outputRange: [0.4, 1] }) }] }]}>
          <View style={bar} /><View style={bar} />
        </Animated.View>
      </Animated.View>
    </Pressable>
  );
}

const st = StyleSheet.create({
  btn: { alignItems: 'center', justifyContent: 'center' },
  layer: { position: 'absolute', alignItems: 'center', justifyContent: 'center' },
  bars: { flexDirection: 'row' },
});
