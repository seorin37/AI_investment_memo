import React, { useEffect, useState } from 'react';
import { Animated, Pressable, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { useMotionK } from '@/ui/motion/useMotion';
import { appColor, curve, tw } from '@/ui/theme';

const APath = Animated.createAnimatedComponent(Path);

/**
 * 체크 상자
 * app: 원본 memo.html .cb (24 · 라운드 7 · 끔 흰 바탕 + 안쪽 2px #C5C8CF · 켬 #8569E3)
 * web: 원본 kit.tsx Check (20 · 라운드 6 또는 원 · 끔 흰 바탕 + 안쪽 1.5px #C9CDD4 · 켬 #111
 *      체크 선이 .25s ease 로 그려짐(.08s 뒤) · 켜지면 1.08배)
 */
export function CheckBox({ on, onChange, label, variant, round }: { on: boolean; onChange?: (v: boolean) => void; label?: string; variant: 'app' | 'web'; round?: boolean }) {
  const k = useMotionK();
  const [d] = useState(() => new Animated.Value(on ? 0 : 14));
  useEffect(() => {
    const a = Animated.timing(d, { toValue: on ? 0 : 14, duration: 250 * k, delay: 80 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [on, d, k]);
  const app = variant === 'app';
  const sz = app ? 24 : 20;
  const r = round ? sz / 2 : app ? 7 : 6;
  const box = (
    <View
      style={{
        width: sz,
        height: sz,
        borderRadius: r,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: on ? (app ? appColor.accent : tw.black) : '#FFFFFF',
        borderWidth: on ? 0 : app ? 2 : 1.5,
        borderColor: app ? '#C5C8CF' : '#C9CDD4',
        transform: [{ scale: on && !app ? 1.08 : 1 }],
      }}
    >
      <Svg width={app ? 14 : 12} height={app ? 14 : 12} viewBox="0 0 14 14">
        <APath d="M3 7.3 5.8 10 11 4.3" fill="none" stroke="#FFFFFF" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" strokeDasharray="14" strokeDashoffset={d} />
      </Svg>
    </View>
  );
  if (!onChange) return box;
  return (
    <Pressable onPress={() => onChange(!on)} accessibilityRole="checkbox" accessibilityState={{ checked: on }} accessibilityLabel={label} hitSlop={(44 - sz) / 2}>
      {box}
    </Pressable>
  );
}
