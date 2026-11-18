/**
 * 부채꼴 + 버튼 (Lucian #011 fab-radial-menu) — 체험판 memo.html 값 그대로.
 *  - 평소: 버튼 둘레가 2.6초마다 숨 쉬듯 번짐 (fabbr)
 *  - 누르면: + 가 135° 돌아 × · 뒤에 보랏빛 번짐(.2배 → 1배) · 항목이 45ms 차이로 튀어나옴(.5s spring)
 *  - 항목을 고르면 1.25배로 커졌다가 접히고 그 다음 onPick
 *  - 화면은 옅게 가려지고(.3s), 빈 곳이나 버튼을 다시 누르면 닫힘
 * 화면 맨 위(ScrollView 밖)에 두면 됨. 색은 화면이 넘김.
 */
import { useEffect, useRef } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';
import { MobileIcon, type MobileIconName } from '@/components/icons/MobileIcons';
import { EASE, ND, SPRING, tween, useReduceMotion, useValue } from '@/components/motion/motion';

const M = { white: '#FFFFFF', label: '#575B63', shadow: '#000000' } as const;
const FAB = 58, ITEM = 52;

export interface FanItem<K extends string> {
  key: K;
  label: string;
  icon: MobileIconName;
  color: string;
  /** + 버튼 가운데에서 항목 가운데까지 (오른쪽 +, 아래 +) */
  dx: number;
  dy: number;
}

export interface FabFanProps<K extends string> {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: FanItem<K>[];
  onPick: (key: K) => void;
  color: string;
  haloColor: string;
  scrimColor: string;
  shadowColor: string;
  right?: number;
  bottom?: number;
}

export function FabFan<K extends string>(props: FabFanProps<K>) {
  const { open, onOpenChange, items, onPick, color, haloColor, scrimColor, shadowColor, right = 18, bottom = 16 } = props;
  const o = useValue(0);       // 열림 정도 (항목별 지연은 아래)
  const rot = useValue(0);     // + 회전 .6s spring
  const halo = useValue(0);
  const breathe = useValue(0);
  /** 항목 수는 화면에서 고정(메모 · 체크리스트)이라 처음 만든 값을 계속 씀 */
  const its = useRef(items.map(() => new Animated.Value(0))).current;
  const picked = useRef(items.map(() => new Animated.Value(1))).current;
  const still = useReduceMotion();

  useEffect(() => {
    const to = open ? 1 : 0;
    Animated.parallel([
      tween(o, to, 300, EASE, ND),
      tween(rot, to, 600, SPRING, ND),
      tween(halo, to, 450, SPRING, ND),
      Animated.stagger(45, (open ? its : [...its].reverse()).map((v) => tween(v, to, open ? 500 : 300, open ? SPRING : EASE, ND))),
    ]).start();
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (open || still) { breathe.setValue(0); return; }
    const loop = Animated.loop(Animated.sequence([tween(breathe, 1, 1820, EASE, ND), Animated.delay(780)]));
    breathe.setValue(0);
    loop.start();
    return () => loop.stop();
  }, [open, still, breathe]);

  const pick = (i: number) => {
    Animated.sequence([tween(picked[i], 1.25, 250, EASE, ND), tween(picked[i], 1, 250, EASE, ND)]).start();
    setTimeout(() => { onOpenChange(false); onPick(items[i].key); }, 260);
  };

  const cx = right + FAB / 2, cy = bottom + FAB / 2;
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="box-none">
      <Animated.View pointerEvents={open ? 'auto' : 'none'} style={[StyleSheet.absoluteFill, { backgroundColor: scrimColor, opacity: o }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={() => onOpenChange(false)} accessibilityLabel="메뉴 닫기" />
      </Animated.View>

      <Animated.View pointerEvents="none" style={[st.halo, { right: cx - 150, bottom: cy - 150, opacity: halo.interpolate({ inputRange: [0, 1], outputRange: [0, 1], extrapolate: 'clamp' }), transform: [{ scale: halo.interpolate({ inputRange: [0, 1], outputRange: [0.2, 1] }) }] }]}>
        {[300, 210, 130].map((d, i) => <View key={d} style={[st.ring, { width: d, height: d, borderRadius: d / 2, backgroundColor: haloColor, opacity: [0.07, 0.1, 0.14][i] }]} />)}
      </Animated.View>

      {items.map((it, i) => {
        const v = its[i];
        return (
          <Animated.View key={it.key} pointerEvents={open ? 'box-none' : 'none'}
            style={[st.item, { right: cx - ITEM / 2 - 12, bottom: cy - ITEM / 2 - 20, opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0, 1], extrapolate: 'clamp' }),
              transform: [
                { translateX: v.interpolate({ inputRange: [0, 1], outputRange: [0, it.dx] }) },
                { translateY: v.interpolate({ inputRange: [0, 1], outputRange: [0, it.dy] }) },
                { scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.3, 1] }) },
              ] }]}>
            <Pressable onPress={() => pick(i)} style={st.itemHit} accessibilityRole="button" accessibilityLabel={it.label}>
              <Animated.View style={[st.circle, { backgroundColor: it.color, transform: [{ scale: picked[i] }] }]}>
                <MobileIcon name={it.icon} size={22} color={M.white} />
              </Animated.View>
              <Text style={st.label}>{it.label}</Text>
            </Pressable>
          </Animated.View>
        );
      })}

      <Animated.View pointerEvents="none" style={[st.breath, { right, bottom, backgroundColor: haloColor,
        opacity: breathe.interpolate({ inputRange: [0, 1], outputRange: [0.45, 0] }),
        transform: [{ scale: breathe.interpolate({ inputRange: [0, 1], outputRange: [1, (FAB + 32) / FAB] }) }] }]} />
      <Pressable onPress={() => onOpenChange(!open)} style={[st.fab, { right, bottom, backgroundColor: color, shadowColor }]}
        accessibilityRole="button" accessibilityLabel={open ? '메뉴 닫기' : '새로 만들기'} accessibilityState={{ expanded: open }}>
        <Animated.View style={{ transform: [{ rotate: rot.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '135deg'] }) }] }}>
          <MobileIcon name="plus" size={26} color={M.white} strokeWidth={2.4} />
        </Animated.View>
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  halo: { position: 'absolute', width: 300, height: 300, alignItems: 'center', justifyContent: 'center' },
  ring: { position: 'absolute' },
  item: { position: 'absolute', width: ITEM + 24, alignItems: 'center' },
  itemHit: { alignItems: 'center', minHeight: 44 },
  circle: { width: ITEM, height: ITEM, borderRadius: ITEM / 2, alignItems: 'center', justifyContent: 'center', shadowColor: M.shadow, shadowOpacity: 0.25, shadowRadius: 12, shadowOffset: { width: 0, height: 8 }, elevation: 5 },
  label: { fontSize: 12.5, fontWeight: '700', color: M.label, marginTop: 5 },
  breath: { position: 'absolute', width: FAB, height: FAB, borderRadius: FAB / 2 },
  fab: { position: 'absolute', width: FAB, height: FAB, borderRadius: FAB / 2, alignItems: 'center', justifyContent: 'center', shadowOpacity: 0.45, shadowRadius: 11, shadowOffset: { width: 0, height: 10 }, elevation: 6 },
});
