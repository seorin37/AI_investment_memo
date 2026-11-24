import React, { useEffect, useState } from 'react';
import { Animated, type StyleProp, type ViewStyle } from 'react-native';
import { curve, dur } from '@/ui/theme';
import { NATIVE, useMotionK } from './useMotion';

/** 차례로 올라오기 (원본 .m-reveal: translateY 10px → 0 + 페이드, .45s ease, i × 70ms 뒤) */
export function Reveal({ i = 0, children, style, rise = 10 }: { i?: number; children: React.ReactNode; style?: StyleProp<ViewStyle>; rise?: number }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: 1, duration: dur.slow * k, delay: i * dur.stagger * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [v, i, k]);
  return <Animated.View style={[style, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [rise, 0] }) }] }]}>{children}</Animated.View>;
}

/** 페이드 스루 들어오기 (원본 .m-in: opacity 0 · scale .96 → 1, .21s enter). key 를 바꾸면 다시 들어옴 */
export function FadeIn({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: 1, duration: dur.in * k, easing: curve.enter, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [v, k]);
  return <Animated.View style={[style, { opacity: v, transform: [{ scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.96, 1] }) }] }]}>{children}</Animated.View>;
}
