import React, { useEffect, useState } from 'react';
import { Animated, Pressable } from 'react-native';
import { useMotionK } from '@/ui/motion/useMotion';
import { appColor, curve, dur, tw } from '@/ui/theme';

const SPEC = {
  /* 원본 앱 .sw: 52×30 · 라운드 15 · 끔 #C9CDD4 · 켬 #8569E3 · 손잡이 24 (위·왼쪽 3) · 켜면 22 오른쪽 · 그림자 0 1px 3px .2 */
  app: { w: 52, h: 30, knob: 24, inset: 3, move: 22, off: '#C9CDD4', on: appColor.accent },
  /* 원본 웹 kit.tsx Toggle: 44×26 · 끔 zinc-300 · 켬 #111 · 손잡이 20 (위·왼쪽 3) · 켜면 18 오른쪽 */
  web: { w: 44, h: 26, knob: 20, inset: 3, move: 18, off: tw.zinc300, on: tw.black },
} as const;

/** 켜고 끄는 스위치 (손잡이 .4s spring · 바탕 .25s) */
export function Toggle({ on, onChange, label, variant, disabled }: { on: boolean; onChange: (v: boolean) => void; label: string; variant: 'app' | 'web'; disabled?: boolean }) {
  const s = SPEC[variant];
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(on ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: on ? 1 : 0, duration: 400 * k, easing: curve.spring, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [on, v, k]);
  return (
    <Pressable onPress={() => onChange(!on)} disabled={disabled} accessibilityRole="switch" accessibilityLabel={label} accessibilityState={{ checked: on, disabled }} hitSlop={Math.max(0, (44 - s.h) / 2)} style={{ opacity: disabled ? 0.4 : 1 }}>
      <Animated.View style={{ width: s.w, height: s.h, borderRadius: s.h / 2, backgroundColor: v.interpolate({ inputRange: [0, 1], outputRange: [s.off, s.on] }) }}>
        <Animated.View
          style={{
            position: 'absolute',
            top: s.inset,
            left: s.inset,
            width: s.knob,
            height: s.knob,
            borderRadius: s.knob / 2,
            backgroundColor: '#FFFFFF',
            shadowColor: '#000000',
            shadowOpacity: 0.2,
            shadowRadius: 3,
            shadowOffset: { width: 0, height: 1 },
            elevation: 2,
            transform: [{ translateX: v.interpolate({ inputRange: [0, 1], outputRange: [0, s.move] }) }],
          }}
        />
      </Animated.View>
    </Pressable>
  );
}

/** 바탕 전환 시간 (원본 .25s) — 다른 부품이 맞출 때 */
export const TOGGLE_BG_MS = dur.fast + 50;
