import React, { useEffect, useState } from 'react';
import { Animated, BackHandler, Easing, Keyboard, Pressable, ScrollView, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';
import { BottomBar } from '@/ui/shared/app/BottomBar';
import { MiniSpace } from '@/ui/screens/studio/app/MiniBar';
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

/* .it 최소 52 · 좌우 16 · 15px · 아래 선 #F1F2F4 (마지막 줄 없음) · .tw 위아래 12 · 높이 62 · .v 13 ink3 + › */
export function Item({ title, sub, value, red, last, two, onPress, right, label }: { title: string; sub?: string; value?: string; red?: boolean; last?: boolean; two?: boolean; onPress?: () => void; right?: React.ReactNode; label?: string }) {
  const body = (
    <>
      <View style={pt.itMain}>
        <Text style={[pt.itT, two && pt.itT2, red && { color: MC.red }]}>{title}</Text>
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

/**
 * MY 하위 화면 틀 (원본 .pg: 바탕 #F3F4F6 · .bh 머리 · .sc 스크롤 아래 28 · .wb 아래 고정 버튼이면 150)
 * 안드로이드 뒤로: onHardwareBack 이 true 를 돌려주면 그 안에서 처리, 아니면 onBack
 */
export function Page({ title, onBack, lead, children, bottom, onHardwareBack }: { title: string; onBack: () => void; lead?: string; children: React.ReactNode; bottom?: React.ReactNode; onHardwareBack?: () => boolean }) {
  const insets = useSafeAreaInsets();
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (onHardwareBack?.()) return true;
      onBack();
      return true;
    });
    return () => sub.remove();
  }, [onBack, onHardwareBack]);
  /* 키보드가 올라오면 아래 버튼이 키보드 바로 위에 붙게 (안전 영역 여백 빼기) */
  const [kb, setKb] = useState(false);
  useEffect(() => {
    const a = Keyboard.addListener('keyboardDidShow', () => setKb(true));
    const b = Keyboard.addListener('keyboardDidHide', () => setKb(false));
    return () => { a.remove(); b.remove(); };
  }, []);
  const padB = kb ? 0 : insets.bottom;
  return (
    <View style={[pt.page, { paddingTop: insets.top }]}>
      <Head title={title} onBack={onBack} />
      <ScrollView contentContainerStyle={{ paddingBottom: (bottom ? 150 : 28) + insets.bottom }} showsVerticalScrollIndicator={false}>
        {lead ? <Lead>{lead}</Lead> : null}
        <View style={pt.w}>{children}</View>
        <MiniSpace />
      </ScrollView>
      {bottom ? (
        <BottomBar clear={30} style={[pt.bot, { paddingBottom: 12 + padB }]}>
          {/* 원본 .bot: linear-gradient(transparent → .85 40% → bg 70%) */}
          <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" preserveAspectRatio="none">
            <Defs>
              <LinearGradient id="myBot" x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0" stopColor={MC.bg} stopOpacity={0} />
                <Stop offset="0.4" stopColor={MC.bg} stopOpacity={0.85} />
                <Stop offset="0.7" stopColor={MC.bg} stopOpacity={1} />
              </LinearGradient>
            </Defs>
            <Rect x="0" y="0" width="100%" height="100%" fill="url(#myBot)" />
          </Svg>
          {bottom}
        </BottomBar>
      ) : null}
    </View>
  );
}

/* .bar 6 · #ECEDF1 · 0 → N% .9s (90% 이상 #E89A0C · 100% 빨강) */
export function UsageBar({ pct, delay = 200 }: { pct: number; delay?: number }) {
  const k = useMotionK();
  const [w, setW] = useState(0);
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!w) return;
    const a = Animated.timing(v, { toValue: (w * Math.min(pct, 100)) / 100, duration: 900 * k, delay: delay * k, easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [w, pct, k, v, delay]);
  return (
    <View style={pt.bar} onLayout={(e) => setW(e.nativeEvent.layout.width)}>
      <Animated.View style={[pt.barI, { width: v, backgroundColor: usageColor(pct) }]} />
    </View>
  );
}
export const usageColor = (pct: number) => (pct >= 100 ? MC.red : pct >= 90 ? '#E89A0C' : MC.a);

/* .lead (하위 화면): 12.5 ink3 · 좌우 18 · 아래 12 · 줄 1.55 */
export function Lead({ children }: { children: string }) {
  return <Text keepAll style={pt.lead}>{children}</Text>;
}
/* .foot2: 11.5 ink3 · 위 12 · 좌우 4 · 줄 1.6 */
export function Foot({ children }: { children: string }) {
  return <Text keepAll style={pt.foot}>{children}</Text>;
}
/* IC.ok: ✓ 16 · #6A42AB · 선 2.6 */
export function OkIcon({ size = 16, color = MC.a2 }: { size?: number; color?: string }) {
  return <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round"><Path d="M5 12.5l4.5 4.5L19 7" /></Svg>;
}

export const pt = StyleSheet.create({
  page: { flex: 1, backgroundColor: MC.bg },
  w: { paddingHorizontal: 16 },
  bot: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingTop: 30, paddingHorizontal: 16 },
  bar: { height: 6, borderRadius: 3, backgroundColor: '#ECEDF1', marginTop: 12, marginBottom: 8, overflow: 'hidden' },
  barI: { height: 6, borderRadius: 3 },
  lead: { fontSize: 12.5, lineHeight: 19.4, color: MC.ink3, marginHorizontal: 18, marginBottom: 12 },
  foot: { fontSize: 11.5, lineHeight: 18.4, color: MC.ink3, marginTop: 12, marginHorizontal: 4 },
  bh: { height: 58, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10 },
  ib: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  bhT: { fontSize: 19, lineHeight: 27, fontWeight: '700', color: MC.ink },
  lb: { marginTop: 16, marginHorizontal: 4, marginBottom: 7 },
  lbT: { fontSize: 12.5, lineHeight: 18, color: MC.ink3 },
  grp: { backgroundColor: '#FFFFFF', borderRadius: 18, overflow: 'hidden' },
  it: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 52, paddingHorizontal: 16 },
  /* 62 = 12 + 18 + 2 + 17 + 12 + 선 1 (마지막 줄도 62) */
  tw: { paddingVertical: 12, minHeight: 62 },
  itLine: { borderBottomWidth: 1, borderBottomColor: '#F1F2F4' },
  itMain: { flex: 1, minWidth: 0 },
  itT: { fontSize: 15, lineHeight: 22, color: MC.ink },
  itT2: { lineHeight: 18, fontWeight: '500' },
  itS: { fontSize: 12, lineHeight: 17, color: MC.ink3, marginTop: 2 },
  v: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 4 },
  vT: { fontSize: 13, lineHeight: 19, color: MC.ink3 },
  sh: { paddingHorizontal: 20, paddingBottom: 12 },
  shH: { fontSize: 18, lineHeight: 26, fontWeight: '700', color: MC.ink, marginBottom: 6 },
  shP: { fontSize: 13.5, lineHeight: 21.6, color: MC.ink2, marginBottom: 16 },
  sbtn: { flexDirection: 'row', gap: 8 },
  sb: { flex: 1, borderRadius: 14, paddingVertical: 15, minHeight: 52, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F1F2F4' },
  sbT: { fontSize: 15, lineHeight: 22, fontWeight: '800', color: MC.ink },
});
