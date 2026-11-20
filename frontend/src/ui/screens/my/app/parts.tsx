import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { Sheet } from '@/ui/shared/Sheet';
import { appColor } from '@/ui/theme';

/** 원본 app/my.html :root */
export const MC = { a: appColor.accent, a2: '#6A42AB', aSoft: '#EEE9FB', ink: '#16171A', ink2: '#575B63', ink3: '#9A9EA7', line: '#E6E8EC', sf: '#F2F2F5', red: '#E5484D', bg: '#F3F4F6' };

/* .bh 58 · .ib 42 · 제목 19 bold */
export function Head({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <View style={pt.bh}>
      <Pressable onPress={onBack} style={({ pressed }) => [pt.ib, pressed && { backgroundColor: '#E9EAEE' }]} accessibilityRole="button" accessibilityLabel="뒤로">
        <Svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="#16171A" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"><Path d="M15 5l-7 7 7 7" /></Svg>
      </Pressable>
      <Text style={pt.bhT}>{title}</Text>
    </View>
  );
}

export function Chev() {
  return <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="#B3B7BE" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"><Path d="M9 5l7 7-7 7" /></Svg>;
}

/* .rv > * : 아래에서 올라옴 .42s · i×45ms */
export function Rv({ i, children, style }: { i: number; children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: 1, duration: 420 * k, delay: i * 45 * k, easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [i, k, v]);
  return <Animated.View style={[style, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }) }] }]}>{children}</Animated.View>;
}

/* .lb 12.5 ink3 · 위 16 · 아래 7 · 좌우 4 */
export function Lb({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[pt.lb, style]}><Text keepAll style={pt.lbT}>{children}</Text></View>;
}

/* .grp 흰 바탕 · 라운드 18 */
export function Grp({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[pt.grp, style]}>{children}</View>;
}

/* .it 최소 52 · 좌우 16 · 15px · 아래 선 #F1F2F4 (마지막 줄 없음) · .tw 위아래 12 · .v 13 ink3 + › */
export function Item({ title, sub, value, red, last, two, onPress, right, label }: { title: string; sub?: string; value?: string; red?: boolean; last?: boolean; two?: boolean; onPress?: () => void; right?: React.ReactNode; label?: string }) {
  const body = (
    <>
      <View style={pt.itMain}>
        <Text style={[pt.itT, two && { fontWeight: '500' }, red && { color: MC.red }]}>{title}</Text>
        {sub ? <Text keepAll style={pt.itS}>{sub}</Text> : null}
      </View>
      {right ?? (
        <View style={pt.v}>
          {value ? <Text style={pt.vT}>{value}</Text> : null}
          <Chev />
        </View>
      )}
    </>
  );
  const style = [pt.it, two && pt.tw, !last && pt.itLine];
  if (!onPress) return <View style={style}>{body}</View>;
  return <Pressable onPress={onPress} style={({ pressed }) => [...style, pressed && { backgroundColor: '#F7F7F9' }]} accessibilityRole="button" accessibilityLabel={label ?? title}>{body}</Pressable>;
}

/* 원본 .sheet 확인: h3 18 · p 13.5 줄 1.6 ink2 · 버튼 둘(라운드 14 · 위아래 15 · 15px 800 · #F1F2F4 / 검정 또는 빨강) */
export function ConfirmSheet({ open, title, body, ok, red, onCancel, onOk }: { open: boolean; title: string; body: string; ok: string; red?: boolean; onCancel: () => void; onOk: () => void }) {
  return (
    <Sheet open={open} onClose={onCancel} label={title}>
      <View style={pt.sh}>
        <Text style={pt.shH}>{title}</Text>
        <Text keepAll style={pt.shP}>{body}</Text>
        <View style={pt.sbtn}>
          <Pressable onPress={onCancel} style={({ pressed }) => [pt.sb, pressed && { opacity: 0.85 }]} accessibilityRole="button"><Text style={pt.sbT}>취소</Text></Pressable>
          <Pressable onPress={onOk} style={({ pressed }) => [pt.sb, { backgroundColor: red ? MC.red : MC.ink }, pressed && { opacity: 0.85 }]} accessibilityRole="button"><Text style={[pt.sbT, { color: '#FFFFFF' }]}>{ok}</Text></Pressable>
        </View>
      </View>
    </Sheet>
  );
}

export const pt = StyleSheet.create({
  bh: { height: 58, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10 },
  ib: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  bhT: { fontSize: 19, lineHeight: 27, fontWeight: '700', color: MC.ink },
  lb: { marginTop: 16, marginHorizontal: 4, marginBottom: 7 },
  lbT: { fontSize: 12.5, lineHeight: 18, color: MC.ink3 },
  grp: { backgroundColor: '#FFFFFF', borderRadius: 18, overflow: 'hidden' },
  it: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 52, paddingHorizontal: 16 },
  tw: { paddingVertical: 12 },
  itLine: { borderBottomWidth: 1, borderBottomColor: '#F1F2F4' },
  itMain: { flex: 1, minWidth: 0 },
  itT: { fontSize: 15, lineHeight: 22, color: MC.ink },
  itS: { fontSize: 12, lineHeight: 17.4, color: MC.ink3, marginTop: 2 },
  v: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 4 },
  vT: { fontSize: 13, lineHeight: 19, color: MC.ink3 },
  sh: { paddingHorizontal: 20, paddingBottom: 12 },
  shH: { fontSize: 18, lineHeight: 26, fontWeight: '700', color: MC.ink, marginBottom: 6 },
  shP: { fontSize: 13.5, lineHeight: 21.6, color: MC.ink2, marginBottom: 16 },
  sbtn: { flexDirection: 'row', gap: 8 },
  sb: { flex: 1, borderRadius: 14, paddingVertical: 15, minHeight: 52, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F1F2F4' },
  sbT: { fontSize: 15, lineHeight: 22, fontWeight: '800', color: MC.ink },
});
