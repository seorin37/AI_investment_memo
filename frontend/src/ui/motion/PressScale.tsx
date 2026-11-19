import React, { useState } from 'react';
import { Animated, Pressable, type PressableProps, type StyleProp, type ViewStyle } from 'react-native';
import { curve, dur } from '@/ui/theme';
import { NATIVE, useMotionK } from './useMotion';

/**
 * 누르면 살짝 작아지는 버튼 (원본 .m-press: :active scale(.97), transform .3s spring)
 * style 은 바깥(크기·배경 포함) 한 곳에 줌.
 */
export function PressScale({ style, children, scaleTo = 0.97, ...p }: Omit<PressableProps, 'style' | 'children'> & { style?: StyleProp<ViewStyle>; children?: React.ReactNode; scaleTo?: number }) {
  const k = useMotionK();
  const [s] = useState(() => new Animated.Value(1));
  const to = (v: number) => Animated.timing(s, { toValue: v, duration: dur.base * k, easing: curve.spring, useNativeDriver: NATIVE }).start();
  return (
    <Pressable
      {...p}
      onPressIn={(e) => {
        to(scaleTo);
        p.onPressIn?.(e);
      }}
      onPressOut={(e) => {
        to(1);
        p.onPressOut?.(e);
      }}
    >
      <Animated.View style={[style, { transform: [{ scale: s }] }]}>{children}</Animated.View>
    </Pressable>
  );
}
