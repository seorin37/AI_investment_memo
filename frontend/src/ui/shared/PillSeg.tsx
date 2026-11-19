import React, { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { useMotionK } from '@/ui/motion/useMotion';
import { appColor, curve, ft } from '@/ui/theme';

/**
 * 알약이 미끄러지는 구간 버튼 (원본 company.html .seg2 · .pseg · .tabs3 · #039: 흰 알약 그림자 0 1 3 .08, left·width .32s spring)
 * 크기·색은 원본 칸마다 달라서 숫자를 받음.
 */
export function PillSeg<K extends string>({
  options,
  value,
  onChange,
  bg,
  pad,
  radius,
  pillRadius,
  height,
  fontSize,
  style,
}: {
  options: { key: K; label: string }[];
  value: K;
  onChange: (k: K) => void;
  bg: string;
  pad: number;
  radius: number;
  pillRadius: number;
  height: number;
  fontSize: number;
  style?: StyleProp<ViewStyle>;
}) {
  const k = useMotionK();
  const [w, setW] = useState(0);
  const idx = Math.max(0, options.findIndex((o) => o.key === value));
  const [x] = useState(() => new Animated.Value(idx));
  useEffect(() => {
    const a = Animated.timing(x, { toValue: idx, duration: 320 * k, easing: curve.spring, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [idx, x, k]);
  const cw = w ? (w - pad * 2) / options.length : 0;
  return (
    <View style={[{ flexDirection: 'row', backgroundColor: bg, borderRadius: radius, padding: pad }, style]} onLayout={(e) => setW(e.nativeEvent.layout.width)}>
      {cw ? <Animated.View style={[st.pill, { top: pad, bottom: pad, left: pad, width: cw, borderRadius: pillRadius, transform: [{ translateX: x.interpolate({ inputRange: [0, Math.max(1, options.length - 1)], outputRange: [0, cw * Math.max(1, options.length - 1)] }) }] }]} /> : null}
      {options.map((o) => {
        const on = o.key === value;
        return (
          <Pressable key={o.key} onPress={() => !on && onChange(o.key)} accessibilityRole="tab" accessibilityState={{ selected: on }} style={[st.btn, { height }]}>
            <Text style={[ft(fontSize), { color: on ? appColor.ink : appColor.ink2, fontWeight: on ? '700' : '400' }]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  pill: { position: 'absolute', backgroundColor: '#FFFFFF', shadowColor: '#000000', shadowOpacity: 0.08, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  btn: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
