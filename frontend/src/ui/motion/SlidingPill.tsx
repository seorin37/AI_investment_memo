import React, { useEffect, useState } from 'react';
import { Animated, type StyleProp, type ViewStyle } from 'react-native';
import { curve, dur } from '@/ui/theme';
import { useMotionK } from './useMotion';

/**
 * 칩·탭 뒤에서 미끄러지는 알약 (원본 .m-pill: transform .5s spring · 앱 #039)
 * 부모가 각 칸의 { x, width } 를 재서 넘겨줌. 처음 자리 잡을 때는 움직이지 않음.
 */
export function SlidingPill({ target, style }: { target: { x: number; width: number } | null; style?: StyleProp<ViewStyle> }) {
  const k = useMotionK();
  const [x] = useState(() => new Animated.Value(0));
  const [w] = useState(() => new Animated.Value(0));
  const [placed, setPlaced] = useState(false);
  if (target && !placed) {
    x.setValue(target.x);
    w.setValue(target.width);
    setPlaced(true);
  }
  useEffect(() => {
    if (!target) return;
    const o = { duration: dur.sheet * k, easing: curve.spring, useNativeDriver: false };
    const a = Animated.parallel([Animated.timing(x, { toValue: target.x, ...o }), Animated.timing(w, { toValue: target.width, ...o })]);
    a.start();
    return () => a.stop();
  }, [target, x, w, k]);
  if (!target) return null;
  return <Animated.View pointerEvents="none" style={[{ position: 'absolute', left: 0, transform: [{ translateX: x }], width: w }, style]} />;
}
