/**
 * 켜고 끄는 스위치 — 손잡이가 .4s spring 으로 튀며 넘어가고, 바탕색이 .25s 로 바뀜 (체험판 .sw).
 * AI 연결 스위치 등. 다크 모드는 SkySwitch(#021).
 */
import { useEffect } from 'react';
import { Animated, Pressable, StyleSheet } from 'react-native';
import { EASE, ND, SPRING, tween, useValue } from '@/components/motion/motion';

const M = { off: '#C9CDD4', knob: '#FFFFFF', shadow: '#000000' } as const;
const W = 52, H = 30, K = 24, P = 3;

export interface ToggleProps {
  value: boolean;
  onChange: (v: boolean) => void;
  onColor: string;
  offColor?: string;
  disabled?: boolean;
  accessibilityLabel?: string;
}

export function Toggle({ value, onChange, onColor, offColor = M.off, disabled, accessibilityLabel }: ToggleProps) {
  const knob = useValue(value ? 1 : 0);
  const tint = useValue(value ? 1 : 0);
  useEffect(() => {
    Animated.parallel([tween(knob, value ? 1 : 0, 400, SPRING, ND), tween(tint, value ? 1 : 0, 250, EASE, false)]).start();
  }, [value, knob, tint]);
  const translateX = knob.interpolate({ inputRange: [0, 1], outputRange: [0, W - K - P * 2] });
  const backgroundColor = tint.interpolate({ inputRange: [0, 1], outputRange: [offColor, onColor] });
  return (
    <Pressable onPress={() => onChange(!value)} disabled={disabled} hitSlop={7} style={disabled && st.dim}
      accessibilityRole="switch" accessibilityState={{ checked: value, disabled }} accessibilityLabel={accessibilityLabel}>
      <Animated.View style={[st.track, { backgroundColor }]}>
        <Animated.View style={[st.knob, { transform: [{ translateX }] }]} />
      </Animated.View>
    </Pressable>
  );
}

const st = StyleSheet.create({
  track: { width: W, height: H, borderRadius: H / 2, padding: P },
  knob: { width: K, height: K, borderRadius: K / 2, backgroundColor: M.knob, shadowColor: M.shadow, shadowOpacity: 0.2, shadowRadius: 2, shadowOffset: { width: 0, height: 1 }, elevation: 2 },
  dim: { opacity: 0.45 },
});
