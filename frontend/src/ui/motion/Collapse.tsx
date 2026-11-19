import React, { useEffect, useState } from 'react';
import { Animated, View, type LayoutChangeEvent } from 'react-native';
import { curve, dur } from '@/ui/theme';
import { useMotionK } from './useMotion';

/** 펼침·접힘 (원본 x.css 펼침 공통: 높이 0 ↔ 내용 높이, .3s ease) */
export function Collapse({ open, children, duration = dur.base }: { open: boolean; children: React.ReactNode; duration?: number }) {
  const k = useMotionK();
  const [h, setH] = useState(0);
  const [v] = useState(() => new Animated.Value(open ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: open ? 1 : 0, duration: duration * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [open, v, k, duration]);
  const onLayout = (e: LayoutChangeEvent) => setH(e.nativeEvent.layout.height);
  return (
    <Animated.View style={{ overflow: 'hidden', height: v.interpolate({ inputRange: [0, 1], outputRange: [0, h] }) }}>
      <View style={{ position: 'absolute', left: 0, right: 0, top: 0 }} onLayout={onLayout}>
        {children}
      </View>
    </Animated.View>
  );
}
