import React, { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import type { MemoColor } from '@/types/models';
import { Toggle45Mark } from '@/ui/icons/MemoGlyphs';
import { useMotionK } from '@/ui/motion/useMotion';
import { curve, fpx } from '@/ui/theme';
import { usePaper } from '@/ui/shared/Dark';

/* 원본 board.tsx 팝업 공통 부품 (Toggle45 · AiFooter · Actions · Tabs2 · Close · Swatches) */

type Hover = { pressed: boolean; hovered?: boolean };
export const INK = '#15171A';

/** 원본 PANEL: 680 · 라운드 30 · 흰 · 안쪽 선 1 #E8ECF3 + 그림자 0 24 60 -16 rgba(110,99,150,.16) */
export const panel = StyleSheet.create({
  box: { width: 680, maxWidth: '100%', borderRadius: 30, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E8ECF3', overflow: 'hidden', shadowColor: '#6E6396', shadowOpacity: 0.16, shadowRadius: 44, shadowOffset: { width: 0, height: 24 }, elevation: 12 },
});

/** 원본 웹 메모 색 순서: 노랑 · 파랑 · 분홍 · 초록 · 보라 */
export const WEB_COLORS: MemoColor[] = ['yellow', 'blue', 'pink', 'green', 'purple'];
export const AI_OFF = '켜 두면 하루 한 번 공시·뉴스를 대신 확인해 여기에 붙여 드려요.';

/** AI 연결 스위치 (원본 Toggle45: 45×25 · 켬 #14171C · 끔 #E5E7EB + 안쪽 선 1.25 #14171C · 손잡이 20 (2.5 → 22.5, .3s spring) 안에 체크/×) */
export function Toggle45({ on, set }: { on: boolean; set: (v: boolean) => void }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(on ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: on ? 1 : 0, duration: 300 * k, easing: curve.spring, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [on, v, k]);
  return (
    <Pressable onPress={() => set(!on)} accessibilityRole="switch" accessibilityState={{ checked: on }} accessibilityLabel="AI 연결" style={[st.t45, on ? st.t45On : st.t45Off]}>
      <Animated.View style={[st.knob, !on && st.knobOff, { left: v.interpolate({ inputRange: [0, 1], outputRange: [2.5, 22.5] }) }]}>
        <Toggle45Mark on={on} />
      </Animated.View>
    </Pressable>
  );
}

/** 원본 AiFooter: 108 (좌우 24 · 위아래 12) · 회색 상자 84 라운드 12 · 'AI 연결' 17/26 500 · 설명 14/21 500 */
export function AiFooter({ on, set, sub }: { on: boolean; set: (v: boolean) => void; sub: string }) {
  return (
    <View style={st.foot}>
      <View style={st.footBox}>
        <View style={st.footRow}>
          <View style={st.flex}>
            <Text style={st.footT}>AI 연결</Text>
            <Text style={[st.footS, { color: on ? '#57535F' : '#4E5968' }]} numberOfLines={1}>
              {sub}
            </Text>
          </View>
          <Toggle45 on={on} set={set} />
        </View>
      </View>
    </View>
  );
}

/** 원본 Actions: 안내 13/20 #747D8D · [취소] 44 #F2F3F4 · [확인] 44 #14171C (아래 24 · 오른쪽 24 · 왼쪽 40) */
export function Actions({ note, ok, onCancel, onOk, pl = 40 }: { note: string; ok: string; onCancel: () => void; onOk: () => void; pl?: number }) {
  return (
    <View style={[st.acts, { paddingLeft: pl }]}>
      <Text style={st.note}>{note}</Text>
      <Pressable onPress={onCancel} accessibilityRole="button" style={({ hovered }: Hover) => [st.btn, st.btnGray, hovered && { backgroundColor: '#E9EAEC' }]}>
        <Text style={st.btnT}>취소</Text>
      </Pressable>
      <Pressable onPress={onOk} accessibilityRole="button" style={[st.btn, st.btnInk]}>
        <Text style={[st.btnT, { color: '#FFFFFF' }]}>{ok}</Text>
      </Pressable>
    </View>
  );
}

/** 원본 Tabs2: 60 (좌우 24 · 아래 12) · 바 48 라운드 14 #F2F3F4 · 알약 흰 라운드 12 (.5s spring) · 15/23 500 */
export function Tabs2({ a, b, v, set }: { a: string; b: string; v: 0 | 1; set: (i: 0 | 1) => void }) {
  const k = useMotionK();
  const [x] = useState(() => new Animated.Value(v));
  const [w, setW] = useState(0);
  useEffect(() => {
    const an = Animated.timing(x, { toValue: v, duration: 500 * k, easing: curve.spring, useNativeDriver: false });
    an.start();
    return () => an.stop();
  }, [v, x, k]);
  const half = (w - 12) / 2;
  return (
    <View style={st.tabs}>
      <View style={st.tabBar} onLayout={(e) => setW(e.nativeEvent.layout.width)}>
        {w ? <Animated.View style={[st.pill, { width: half, transform: [{ translateX: x.interpolate({ inputRange: [0, 1], outputRange: [0, half + 4] }) }] }]} /> : null}
        {[a, b].map((t, i) => (
          <Pressable key={t} onPress={() => set(i as 0 | 1)} accessibilityRole="tab" accessibilityState={{ selected: v === i }} style={st.tab}>
            <Text style={st.tabT}>{t}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

/** 원본 Close: 32 라운드 12 · '×' 26/35 500 · hover #F2F3F4 */
export function CloseBtn({ onPress }: { onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel="닫기" style={({ hovered }: Hover) => [st.close, hovered && { backgroundColor: '#F2F3F4' }]}>
      <Text style={st.closeT}>×</Text>
    </Pressable>
  );
}

/** 원본 Swatches: 44 · '메모 색상' 76 · 동그라미 34 (사이 8 · 고르면 안쪽 1.5 #15171A + ✓) · '보기·수정 칸에 같은 색상' */
export function Swatches({ v, set }: { v: MemoColor; set: (c: MemoColor) => void }) {
  const paper = usePaper();
  return (
    <View style={st.sw}>
      <Text style={st.swL}>메모 색상</Text>
      <View style={st.swDots}>
        {WEB_COLORS.map((c) => (
          <Pressable key={c} onPress={() => set(c)} accessibilityRole="button" accessibilityLabel={paper[c].label} accessibilityState={{ selected: v === c }} style={[st.dot, { backgroundColor: paper[c].bg }, v === c && st.dotOn]}>
            {v === c ? <Text style={st.dotT}>✓</Text> : null}
          </Pressable>
        ))}
      </View>
      <Text style={st.swH}>보기·수정 칸에 같은 색상</Text>
    </View>
  );
}

const st = StyleSheet.create({
  flex: { flex: 1, minWidth: 0 },
  t45: { width: 45, height: 25, borderRadius: 12.5 },
  t45On: { backgroundColor: '#14171C' },
  t45Off: { backgroundColor: '#E5E7EB', borderWidth: 1.25, borderColor: '#14171C' },
  knob: { position: 'absolute', top: 2.5, width: 20, height: 20, borderRadius: 10, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  knobOff: { top: 1.25, marginLeft: -1.25, shadowColor: '#000000', shadowOpacity: 0.28, shadowRadius: 3, shadowOffset: { width: 0, height: 1.88 }, elevation: 2 },
  foot: { paddingHorizontal: 24, paddingVertical: 12 },
  footBox: { minHeight: 84, borderRadius: 12, backgroundColor: '#F2F3F4', paddingHorizontal: 16, paddingVertical: 8, justifyContent: 'center' },
  footRow: { minHeight: 40, flexDirection: 'row', alignItems: 'center', gap: 12 },
  footT: { ...fpx(17, 26), fontWeight: '500', color: INK },
  footS: { ...fpx(14, 21), fontWeight: '500' },
  acts: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingBottom: 24, paddingRight: 24, paddingTop: 4 },
  note: { flex: 1, minWidth: 0, ...fpx(13, 20), fontWeight: '500', color: '#747D8D' },
  btn: { minHeight: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center', paddingVertical: 10 },
  btnGray: { backgroundColor: '#F2F3F4', paddingHorizontal: 18 },
  btnInk: { backgroundColor: '#14171C', paddingHorizontal: 24 },
  btnT: { ...fpx(15, 23), fontWeight: '500', color: INK },
  tabs: { paddingHorizontal: 24, paddingBottom: 12 },
  tabBar: { height: 48, flexDirection: 'row', gap: 4, borderRadius: 14, backgroundColor: '#F2F3F4', padding: 4 },
  pill: { position: 'absolute', left: 4, top: 4, height: 40, borderRadius: 12, backgroundColor: '#FFFFFF' },
  tab: { flex: 1, minWidth: 0, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  tabT: { ...fpx(15, 23), fontWeight: '500', color: INK, letterSpacing: -0.15 },
  close: { width: 32, height: 32, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  closeT: { ...fpx(26, 35), fontWeight: '500', color: INK },
  sw: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 12 },
  swL: { width: 76, ...fpx(13, 20), fontWeight: '500', color: '#4E5968' },
  swDots: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  dot: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center' },
  dotOn: { borderWidth: 1.5, borderColor: INK },
  dotT: { ...fpx(15, 23), fontWeight: '500', color: INK },
  swH: { ...fpx(13, 20), fontWeight: '500', color: '#747D8D' },
});
