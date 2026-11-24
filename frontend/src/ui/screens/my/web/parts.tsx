import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { useMotionK } from '@/ui/motion/useMotion';

/** 웹 설정 공통 부품 (원본 overlays.tsx: T15 · D14 · H16 · Hr · Row · Switch · SBtn · Card · Stat · Chev · CloseX) */
export type Hover = { hovered?: boolean; pressed?: boolean };

/* SBtn: 높이 36 · 라운드 8 · 선 #E5E3E8 · 15/23 · hover #F8F7F5 */
export function SBtn({ w, label, red, onPress }: { w: number; label: string; red?: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ hovered }: Hover) => [ws.sbtn, { width: w }, hovered && { backgroundColor: '#F8F7F5' }]}>
      <Text style={[ws.sbtnT, red && { color: '#E45D6A' }]}>{label}</Text>
    </Pressable>
  );
}

/* Switch: 40×24 · 안쪽 2 · 켬 #15171A / 끔 #D1D1D1 · 손잡이 20 · 16 이동 .25s */
export function Switch({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  const k = useMotionK();
  const [x] = useState(() => new Animated.Value(on ? 16 : 0));
  useEffect(() => {
    const a = Animated.timing(x, { toValue: on ? 16 : 0, duration: 250 * k, easing: Easing.out(Easing.ease), useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [on, k, x]);
  return (
    <Pressable onPress={() => onChange(!on)} accessibilityRole="switch" accessibilityState={{ checked: on }} accessibilityLabel={label} style={[ws.sw, { backgroundColor: on ? '#15171A' : '#D1D1D1' }]}>
      <Animated.View style={[ws.swK, { transform: [{ translateX: x }] }]} />
    </Pressable>
  );
}

export function Chev({ dir = 'down' }: { dir?: 'down' | 'up' | 'right' }) {
  const d = dir === 'down' ? 'M3.11133 5.44531L7.00022 9.3342L10.8891 5.44531' : dir === 'up' ? 'M10.8887 8.55469L6.99978 4.6658L3.11089 8.55469' : 'M5.44531 10.8887L9.3342 6.99978L5.44531 3.11089';
  return <Svg width={14} height={14} viewBox="0 0 14 14" fill="none"><Path d={d} stroke="#8E8A97" strokeWidth={1.24444} strokeLinecap="round" strokeLinejoin="round" /></Svg>;
}

export function CloseX({ onPress, label = '닫기' }: { onPress: () => void; label?: string }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={({ hovered }: Hover) => [ws.x, hovered && { backgroundColor: '#F8F7F5' }]}>
      <Svg width={36} height={36} viewBox="0 0 36 36" fill="none"><Path d="M13 13L23 23" stroke="#333333" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" /><Path d="M23 13L13 23" stroke="#333333" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" /></Svg>
    </Pressable>
  );
}

/* Row: 제목 17/26 medium · 설명 15/23 #8E8A97 · 오른쪽 부품 (718 · 사이 24) */
export function Row({ t, d, w, children }: { t: string; d?: string; w: number; children?: React.ReactNode }) {
  return (
    <View style={ws.row}>
      <View style={{ width: w, gap: 4 }}>
        <Text style={ws.t15}>{t}</Text>
        {d ? <Text style={ws.d14}>{d}</Text> : null}
      </View>
      {children}
    </View>
  );
}

export const ws = StyleSheet.create({
  t15: { fontSize: 17, lineHeight: 26, fontWeight: '500', color: '#15171A' },
  d14: { fontSize: 15, lineHeight: 23, color: '#8E8A97' },
  h16: { fontSize: 20, lineHeight: 29, fontWeight: '700', color: '#15171A' },
  hr: { height: 1, alignSelf: 'stretch', backgroundColor: '#E5E3E8' },
  card: { width: 718, borderRadius: 12, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF', padding: 20, gap: 20 },
  row: { width: 718, flexDirection: 'row', alignItems: 'center', gap: 24 },
  sbtn: { height: 36, borderRadius: 8, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12 },
  sbtnT: { fontSize: 15, lineHeight: 23, color: '#15171A' },
  sw: { width: 40, height: 24, borderRadius: 12, padding: 2 },
  swK: { width: 20, height: 20, borderRadius: 10, backgroundColor: '#FFFFFF' },
  x: { width: 36, height: 36, borderRadius: 8 },
  note: { fontSize: 14, lineHeight: 21, color: '#8E8A97' },
});
