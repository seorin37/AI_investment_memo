/**
 * 가입 — "어떤 종목의 메모를 남기고 싶으세요?" · 많이 찾는 종목 12개(3칸 고정 · 긴 이름은 …) · 아래 트레이(N개 선택 · 보유·관심 정하기 ›) · [다음].
 * 체험판 login.html 첫 종목. 상단(건너뛰기)은 화면 안에 둠 (가입 흐름이라 앱 상단 바가 없음).
 * 움직임: 종목 칸이 차례로 튀어 오름(30ms) · 고르면 칸이 .94배로 눌렸다 spring · 체크 잉크(#014)
 *        · 선택 수가 바뀌면 숫자가 톡 · [보유·관심 정하기 ›]가 옆에서 나타남 · [다음]이 켜지며 spring
 */
import { useEffect } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Appear, PopWhen } from '@/components/motion/Appear';
import { InkCheck } from '@/components/motion/InkCheck';
import { EASE, ND, SPRING, tween, useValue } from '@/components/motion/motion';
import { usePressScale } from '@/components/motion/StateMotion';
import type { PickStock, StockPickProps } from '@/features/onboarding/StockPick.types';

const C = {
  bg: '#FFFFFF',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  cell: '#F6F7F9',
  cellOn: '#EEE9FB',
  accent: '#8569E3',
  accentDeep: '#6A42AB',
  white: '#FFFFFF',
  line: '#EEF0F3',
  dark: '#16171A',
} as const;
const PAD = 16;
const COL_GAP = 8;
const R = { cell: 16, btn: 14 };

export function StockPick({ stocks, selected, onToggle, onOpenHolding, onNext, onSkip }: StockPickProps) {
  const insets = useSafeAreaInsets();
  const n = selected.length;
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <View style={st.top}>
        <Pressable style={st.skip} onPress={onSkip} accessibilityRole="button"><Text style={st.skipText}>건너뛰기</Text></Pressable>
      </View>
      <ScrollView contentContainerStyle={st.body}>
        <Text style={st.title}>어떤 종목의 메모를{'\n'}남기고 싶으세요?</Text>
        <Text style={st.desc}>여러 개 골라도 돼요. 나중에 내 종목에서 언제든 바꿀 수 있어요.</Text>
        <Text style={st.group}>많이 찾는 종목</Text>
        <View style={st.grid}>
          {stocks.map((s, i) => <Cell key={s.stock_code} s={s} i={i} on={selected.includes(s.stock_code)} onPress={() => onToggle(s.stock_code)} />)}
        </View>
        <Text style={st.more}>찾는 종목이 없나요? 시작한 뒤 <Text style={st.moreB}>내 종목 › 종목 추가</Text>에서 코스피 전체를 찾을 수 있어요</Text>
      </ScrollView>
      <View style={[st.tray, { paddingBottom: insets.bottom + 12 }]}>
        <View style={st.trayRow}>
          <PopWhen show replay={n}><Text style={st.trayCount}>{n}개 선택</Text></PopWhen>
          {n > 0 && <Appear kind="pin" dx={12}><Pressable style={st.trayLink} onPress={onOpenHolding}><Text style={st.trayLinkText}>보유·관심 정하기 ›</Text></Pressable></Appear>}
        </View>
        <NextBtn on={n > 0} onPress={onNext} />
      </View>
    </View>
  );
}

function Cell({ s, i, on, onPress }: { s: PickStock; i: number; on: boolean; onPress: () => void }) {
  const p = usePressScale(0.94);
  return (
    <Appear kind="pop" index={0} delay={i * 30} style={st.cellBox}>
      <Pressable onPress={onPress} onPressIn={p.onPressIn} onPressOut={p.onPressOut} accessibilityRole="checkbox" accessibilityState={{ checked: on }} accessibilityLabel={s.name}>
        <Animated.View style={[st.cell, on && st.cellOn, { transform: [{ scale: p.scale }] }]}>
          <View style={st.ck}><InkCheck checked={on} color={C.accent} lineColor={C.line} bg={C.white} size={20} radius={10} /></View>
          <View style={[st.logo, { backgroundColor: s.logo_bg }]}><Text style={[st.logoText, { color: s.logo_fg ?? C.white }]}>{s.logo_text}</Text></View>
          <Text style={st.name} numberOfLines={1}>{s.name}</Text>
          <Text style={st.code}>{s.stock_code}</Text>
        </Animated.View>
      </Pressable>
    </Appear>
  );
}

/** [다음]: 고른 게 생기면 흐림이 걷히며 살짝 톡 */
function NextBtn({ on, onPress }: { on: boolean; onPress: () => void }) {
  const v = useValue(on ? 1 : 0);
  const p = usePressScale(0.96);
  useEffect(() => { tween(v, on ? 1 : 0, on ? 450 : 200, on ? SPRING : EASE, ND).start(); }, [on, v]);
  return (
    <Pressable onPress={onPress} onPressIn={p.onPressIn} onPressOut={p.onPressOut} disabled={!on} accessibilityRole="button" accessibilityState={{ disabled: !on }}>
      <Animated.View style={[st.next, { opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0.35, 1], extrapolate: 'clamp' }),
        transform: [{ scale: p.scale }, { scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.98, 1] }) }] }]}>
        <Text style={st.nextText}>다음</Text>
      </Animated.View>
    </Pressable>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  top: { height: 52, alignItems: 'flex-end', justifyContent: 'center', paddingHorizontal: 6 },
  skip: { minHeight: 44, minWidth: 44, paddingHorizontal: 10, justifyContent: 'center' },
  skipText: { fontSize: 15, color: C.sub },
  body: { paddingHorizontal: PAD, paddingBottom: 30 },
  title: { fontSize: 24, fontWeight: '800', color: C.text, lineHeight: 33 },
  desc: { fontSize: 14, lineHeight: 21, color: C.sub, marginTop: 8 },
  group: { fontSize: 14, fontWeight: '800', color: C.text, marginTop: 22, marginBottom: 10 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: COL_GAP },
  cellBox: { width: '31.6%', flexGrow: 1, maxWidth: '33%' },
  cell: { backgroundColor: C.cell, borderRadius: R.cell, paddingVertical: 14, paddingHorizontal: 8, alignItems: 'center', minHeight: 44, borderWidth: 1.5, borderColor: C.cell },
  cellOn: { backgroundColor: C.cellOn, borderColor: C.accent },
  ck: { position: 'absolute', top: 8, right: 8 },
  logo: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  logoText: { fontSize: 16, fontWeight: '800' },
  name: { fontSize: 13.5, fontWeight: '700', color: C.text, marginTop: 8, maxWidth: '100%' },
  code: { fontSize: 11, color: C.muted, marginTop: 2 },
  more: { fontSize: 12.5, lineHeight: 19, color: C.muted, textAlign: 'center', marginTop: 18 },
  moreB: { fontWeight: '700', color: C.sub },
  tray: { borderTopWidth: 1, borderTopColor: C.line, paddingHorizontal: PAD, paddingTop: 10, backgroundColor: C.bg },
  trayRow: { flexDirection: 'row', alignItems: 'center', minHeight: 44 },
  trayCount: { flex: 1, fontSize: 15, fontWeight: '800', color: C.text },
  trayLink: { minHeight: 44, justifyContent: 'center' },
  trayLinkText: { fontSize: 14, fontWeight: '700', color: C.accentDeep },
  next: { height: 54, borderRadius: R.btn, backgroundColor: C.dark, alignItems: 'center', justifyContent: 'center', marginTop: 4 },
  nextDis: { opacity: 0.35 },
  nextText: { fontSize: 16, fontWeight: '800', color: C.white },
});
