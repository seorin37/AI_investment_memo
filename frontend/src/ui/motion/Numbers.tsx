import React, { useEffect, useState } from 'react';
import { Animated, View, type StyleProp, type TextStyle } from 'react-native';
import { AnimatedText, Text } from '@/components/ui/AppText';
import { curve, dur } from '@/ui/theme';
import { NATIVE, useMotionK } from './useMotion';

/**
 * 숫자 굴림 (원본 .m-odo: 자리마다 0~9 기둥이 .6s sheet 곡선으로 올라감, 한 칸 높이 1.3em)
 * style 의 fontSize 로 칸 높이를 정함.
 */
export function Odometer({ value, style }: { value: number; style: StyleProp<TextStyle> & { fontSize: number } }) {
  const s = String(value);
  const fs = (style as { fontSize: number }).fontSize;
  const cell = Math.round(fs * 1.3 * 100) / 100;
  return (
    <View style={{ flexDirection: 'row', height: cell, overflow: 'hidden' }} accessibilityLabel={s}>
      {s.split('').map((d, i) => (
        <Digit key={`${s.length}-${i}`} d={d} cell={cell} style={style} />
      ))}
    </View>
  );
}

function Digit({ d, cell, style }: { d: string; cell: number; style: StyleProp<TextStyle> }) {
  const k = useMotionK();
  const n = /\d/.test(d) ? Number(d) : -1;
  const [y] = useState(() => new Animated.Value(n < 0 ? 0 : -n * cell));
  useEffect(() => {
    if (n < 0) return;
    const a = Animated.timing(y, { toValue: -n * cell, duration: dur.odo * k, easing: curve.sheet, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [n, cell, y, k]);
  if (n < 0) return <Text style={[style, { lineHeight: cell }]}>{d}</Text>;
  return (
    <Animated.View style={{ transform: [{ translateY: y }] }}>
      {Array.from({ length: 10 }, (_, i) => (
        <Text key={i} style={[style, { height: cell, lineHeight: cell }]}>
          {i}
        </Text>
      ))}
    </Animated.View>
  );
}

/** 0부터 세어 올라가는 숫자 (원본 kit.tsx CountUp: 650ms, 1-(1-t)^3) */
export function CountUp({ to, decimals = 0, comma = true, style, duration = 650 }: { to: number; decimals?: number; comma?: boolean; style?: StyleProp<TextStyle>; duration?: number }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const id = v.addListener(({ value }) => setShown(value));
    const a = Animated.timing(v, { toValue: to, duration: duration * k, easing: (t) => 1 - Math.pow(1 - t, 3), useNativeDriver: false });
    a.start();
    return () => {
      a.stop();
      v.removeListener(id);
    };
  }, [to, v, k, duration]);
  const txt = decimals ? shown.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : comma ? Math.round(shown).toLocaleString('ko-KR') : String(Math.round(shown));
  return <AnimatedText style={style}>{txt}</AnimatedText>;
}
