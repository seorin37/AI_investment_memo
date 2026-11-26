import React, { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { useMotionK } from '@/ui/motion/useMotion';
import { nf } from '@/ui/shared/app/nf';
import { appColor, curve } from '@/ui/theme';

type Tab = 'board' | 'company';
const TABS: { key: Tab; label: string }[] = [
  { key: 'board', label: '메모 보드' },
  { key: 'company', label: '기업정보' },
];
const PAD = 4;

/** 종목 상세 탭 (메모 보드 · 기업정보가 같이 씀): 버튼 40 · 글자 14.5 · 고른 글자 600 (원본 memo.html .seg) */
export function StockTabs({ value, onChange }: { value: Tab; onChange: (t: Tab) => void }) {
  const k = useMotionK();
  const [w, setW] = useState(0);
  const idx = value === 'board' ? 0 : 1;
  const [x] = useState(() => new Animated.Value(idx));
  useEffect(() => {
    const a = Animated.timing(x, { toValue: idx, duration: 320 * k, easing: curve.spring, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [idx, x, k]);
  const cw = w ? (w - PAD * 2) / TABS.length : 0;
  return (
    <View style={st.box} onLayout={(e) => setW(e.nativeEvent.layout.width)}>
      {cw ? <Animated.View style={[st.pill, { width: cw, transform: [{ translateX: x.interpolate({ inputRange: [0, 1], outputRange: [0, cw] }) }] }]} /> : null}
      {TABS.map((t) => {
        const on = t.key === value;
        return (
          <Pressable key={t.key} onPress={() => !on && onChange(t.key)} accessibilityRole="tab" accessibilityState={{ selected: on }} style={st.btn}>
            <Text style={[st.t, on && st.tOn]}>{t.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  box: { flexDirection: 'row', backgroundColor: '#E3E5EA', borderRadius: 14, padding: PAD },
  pill: { position: 'absolute', top: PAD, bottom: PAD, left: PAD, borderRadius: 11, backgroundColor: '#FFFFFF', shadowColor: '#000000', shadowOpacity: 0.08, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  btn: { flex: 1, height: 40, alignItems: 'center', justifyContent: 'center' },
  t: { ...nf(14.5), color: appColor.ink2 },
  tOn: { color: appColor.ink, fontWeight: '600' },
});
