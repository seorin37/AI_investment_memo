import React, { useEffect, useState } from 'react';
import { Animated, Easing } from 'react-native';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';

/** 돌아가는 표시 (24 · 선 2 #E4DDFB · 위 #8569E3 · .8초). 부모를 기준으로 바깥 2 만큼 채움 */
export function Spin() {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.loop(Animated.timing(v, { toValue: 1, duration: 800 * k, easing: Easing.linear, useNativeDriver: NATIVE }));
    a.start();
    return () => a.stop();
  }, [v, k]);
  return <Animated.View style={{ position: 'absolute', top: -2, left: -2, right: -2, bottom: -2, borderRadius: 12, borderWidth: 2, borderColor: '#E4DDFB', borderTopColor: '#8569E3', transform: [{ rotate: v.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }] }} />;
}
