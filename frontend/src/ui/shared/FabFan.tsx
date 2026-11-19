import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, RadialGradient, Stop } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { FanIcon, PlusGlyph } from '@/ui/icons/BoardGlyphs';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { appColor, curve, ft, shadow } from '@/ui/theme';

export type FanPick = 'check' | 'memo';

/* 원본 .fan-it: --x · --y · 바탕 140° 그라데이션 */
const ITEMS: { k: FanPick; label: string; x: number; y: number; from: string; to: string }[] = [
  { k: 'check', label: '체크리스트', x: -10, y: -94, from: '#FFA45C', to: '#FF7A1A' },
  { k: 'memo', label: '메모', x: -92, y: -30, from: '#9B7BFF', to: '#6A42AB' },
];

/**
 * 앱 + 버튼 부채꼴 (Lucian #011 · 원본 memo.html .fab/.fan)
 * + 58 (#8569E3 · 그림자) — 열면 + 가 135° 돌고 (.6s spring) 뒤로 보라 번짐 300 (scale .2 → 1, .6s) · 막 rgba(246,247,249,.8) (.3s)
 * 항목 52 원: 0.3 → 1 로 커지며 제자리로 (.5s spring · 45ms 차이) · 이름 12.5px 700 #575B63 (원 아래 57)
 * 고르면 1.25 배로 커졌다가 닫힘. 평소엔 버튼 둘레가 숨 쉬듯 번짐 (2.6s)
 * 위치: 오른쪽 18 · 아래 16 (+ up 이면 62 위로 — 스낵바가 떠 있을 때)
 */
export function FabFan({ open, onToggle, onPick, up = false }: { open: boolean; onToggle: (open: boolean) => void; onPick: (k: FanPick) => void; up?: boolean }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(open ? 1 : 0));
  const [lift] = useState(() => new Animated.Value(up ? 1 : 0));
  const [breath] = useState(() => new Animated.Value(0));
  const [picked, setPicked] = useState<FanPick | null>(null);
  const [pickV] = useState(() => new Animated.Value(0));
  const [items] = useState(() => ITEMS.map(() => new Animated.Value(0)));
  useEffect(() => {
    const all = Animated.parallel([
      Animated.timing(v, { toValue: open ? 1 : 0, duration: (open ? 600 : 300) * k, easing: open ? curve.spring : curve.ease, useNativeDriver: NATIVE }),
      ...items.map((iv, i) =>
        Animated.timing(iv, { toValue: open ? 1 : 0, duration: (open ? 500 : 250) * k, delay: (open ? i * 45 : (1 - i) * 30) * k, easing: open ? curve.spring : curve.ease, useNativeDriver: NATIVE }),
      ),
    ]);
    all.start();
    return () => all.stop();
  }, [open, v, items, k]);
  useEffect(() => {
    const a = Animated.timing(lift, { toValue: up ? 1 : 0, duration: 450 * k, easing: curve.spring, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [up, lift, k]);
  useEffect(() => {
    if (open || k < 1) return;
    /* 원본 fabbr: 0% 그림자 0 → 70% 16px 퍼지며 사라짐, 2.6s 반복 */
    const a = Animated.loop(Animated.sequence([Animated.timing(breath, { toValue: 1, duration: 1820, easing: curve.ease, useNativeDriver: NATIVE }), Animated.timing(breath, { toValue: 1, duration: 780, useNativeDriver: NATIVE }), Animated.timing(breath, { toValue: 0, duration: 0, useNativeDriver: NATIVE })]));
    a.start();
    return () => a.stop();
  }, [open, breath, k]);
  const pick = (it: FanPick) => {
    setPicked(it);
    pickV.setValue(0);
    /* 원본 fanpick: 50% 에서 1.25 배 (.5s) */
    Animated.timing(pickV, { toValue: 1, duration: 500 * k, easing: Easing.inOut(Easing.ease), useNativeDriver: NATIVE }).start(() => {
      setPicked(null);
      onToggle(false);
      onPick(it);
    });
  };
  const ty = lift.interpolate({ inputRange: [0, 1], outputRange: [0, -62] });
  return (
    <>
      <Animated.View pointerEvents={open ? 'auto' : 'none'} style={[StyleSheet.absoluteFill, st.scrim, { opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0, 1], extrapolate: 'clamp' }) }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={() => onToggle(false)} accessibilityLabel="닫기" />
      </Animated.View>
      <Animated.View pointerEvents="box-none" style={[st.fan, { transform: [{ translateY: ty }] }]}>
        <Animated.View pointerEvents="none" style={[st.halo, { opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0, 1], extrapolate: 'clamp' }), transform: [{ scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.2, 1] }) }] }]}>
          <Svg width={300} height={300}>
            <Defs>
              <RadialGradient id="fanhalo" cx="0.5" cy="0.5" r="0.5">
                <Stop offset="0" stopColor="#8569E3" stopOpacity={0.22} />
                <Stop offset="0.7" stopColor="#8569E3" stopOpacity={0.07} />
                <Stop offset="1" stopColor="#8569E3" stopOpacity={0} />
              </RadialGradient>
            </Defs>
            <Circle cx={150} cy={150} r={150} fill="url(#fanhalo)" />
          </Svg>
        </Animated.View>
        {ITEMS.map((it, i) => {
          const iv = items[i];
          const sc = picked === it.k ? pickV.interpolate({ inputRange: [0, 0.5, 1], outputRange: [1, 1.25, 1] }) : 1;
          return (
            <Animated.View
              key={it.k}
              pointerEvents={open ? 'auto' : 'none'}
              style={[st.item, { opacity: iv.interpolate({ inputRange: [0, 0.4, 1], outputRange: [0, 1, 1] }), transform: [{ translateX: iv.interpolate({ inputRange: [0, 1], outputRange: [0, it.x] }) }, { translateY: iv.interpolate({ inputRange: [0, 1], outputRange: [0, it.y] }) }, { scale: iv.interpolate({ inputRange: [0, 1], outputRange: [0.3, 1] }) }] }]}
            >
              <Pressable onPress={() => pick(it.k)} accessibilityRole="button" accessibilityLabel={it.label}>
                <Animated.View style={[st.itemCircle, { transform: [{ scale: sc }] }]}>
                  <Svg width={52} height={52} style={StyleSheet.absoluteFill}>
                    <Defs>
                      {/* 140° ≈ 위 왼쪽 → 아래 오른쪽 */}
                      <LinearGradient id={`fan${it.k}`} x1="0.18" y1="0.12" x2="0.82" y2="0.88">
                        <Stop offset="0" stopColor={it.from} />
                        <Stop offset="1" stopColor={it.to} />
                      </LinearGradient>
                    </Defs>
                    <Circle cx={26} cy={26} r={26} fill={`url(#fan${it.k})`} />
                  </Svg>
                  <FanIcon k={it.k} />
                </Animated.View>
              </Pressable>
              <Text style={st.itemLabel} numberOfLines={1}>
                {it.label}
              </Text>
            </Animated.View>
          );
        })}
        <Animated.View pointerEvents="none" style={[st.breath, { opacity: breath.interpolate({ inputRange: [0, 1], outputRange: [0.45, 0] }), transform: [{ scale: breath.interpolate({ inputRange: [0, 1], outputRange: [1, 90 / 58] }) }] }]} />
        <Pressable onPress={() => onToggle(!open)} accessibilityRole="button" accessibilityLabel="새로 만들기" accessibilityState={{ expanded: open }} style={({ pressed }) => [st.fab, pressed && { transform: [{ scale: 0.9 }] }]}>
          <Animated.View style={{ transform: [{ rotate: v.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '135deg'] }) }] }}>
            <PlusGlyph size={26} stroke={2.4} />
          </Animated.View>
        </Pressable>
      </Animated.View>
    </>
  );
}

const st = StyleSheet.create({
  scrim: { backgroundColor: 'rgba(246,247,249,0.8)', zIndex: 3 },
  fan: { position: 'absolute', right: 18, bottom: 16, width: 58, height: 58, zIndex: 5 },
  halo: { position: 'absolute', left: 29 - 150, top: 29 - 150, width: 300, height: 300 },
  item: { position: 'absolute', left: 3, top: 3, width: 52, height: 52, alignItems: 'center' },
  /* 원본: inset 0 1px 0 rgba(255,255,255,.35) · 0 14px 24px -14px rgba(0,0,0,.5) */
  itemCircle: { width: 52, height: 52, borderRadius: 26, alignItems: 'center', justifyContent: 'center', shadowColor: '#000000', shadowOpacity: 0.5, shadowRadius: 10, shadowOffset: { width: 0, height: 14 }, elevation: 6, backgroundColor: '#8569E3' },
  itemLabel: { position: 'absolute', top: 57, width: 80, textAlign: 'center', ...ft(12.5), fontWeight: '700', color: appColor.ink2 },
  breath: { position: 'absolute', left: 0, top: 0, width: 58, height: 58, borderRadius: 29, backgroundColor: 'rgba(133,105,227,1)' },
  fab: { width: 58, height: 58, borderRadius: 29, backgroundColor: appColor.accent, alignItems: 'center', justifyContent: 'center', ...shadow.fab },
});
