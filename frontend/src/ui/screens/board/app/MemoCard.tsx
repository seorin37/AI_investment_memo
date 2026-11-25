import React, { useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import Svg, { ClipPath, Defs, Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { AppPlug } from '@/ui/icons/BoardGlyphs';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { SelCircle, type AppMemoCardProps } from '@/ui/shared/MemoCard';
import { AppTape } from '@/ui/shared/MemoPaper';
import { mmdd, oneLine } from '@/ui/shared/memoFormat';
import { usePaper } from '@/ui/shared/Dark';
import { appColor, curve, ft } from '@/ui/theme';

/** 접힌 모서리 크기 */
const CUT = 24;

/**
 * 앱 보드 2열 메모 카드 (shared/MemoCard 는 웹도 써서 앱 것을 따로) (원본 memo.html .grid .item)
 * 종이: r16 · 귀퉁이 24 접힘 / 안쪽 14·13 / 날짜 줄 최소 22 (날짜 11.5px 500 #4A4A55 · 플러그 22 원 rgba(255,255,255,.8))
 * 제목 15px 800 줄 1.36 · 위아래 6 · 두 줄 / 본문 12.5px 줄 1.5 #2E2E38 · 세 줄
 * 누르면 .12초 뒤 .965 로 줄어듦 (.45s cubic-bezier(.3,1.3,.5,1)) · .48초 꾹 누르면 고르기
 */
export function AppMemoCard({ memo: m, width, height, selecting, selected, aiSpent, onPress, onLongPress, onPressOut }: AppMemoCardProps) {
  const paper = usePaper();
  const k = useMotionK();
  const p = paper[m.color];
  const [s] = useState(() => new Animated.Value(1));
  const scaleTo = (v: number, delay = 0) => Animated.timing(s, { toValue: v, duration: 450 * k, delay: delay * k, easing: curve.land, useNativeDriver: NATIVE }).start();
  const d = `M16 0H${width - 16}A16 16 0 0 1 ${width} 16V${height - CUT}L${width - CUT} ${height}H16A16 16 0 0 1 0 ${height - 16}V16A16 16 0 0 1 16 0Z`;
  return (
    <View style={{ width, height }}>
      <Pressable
        onPress={onPress}
        onLongPress={onLongPress}
        delayLongPress={480}
        onPressIn={() => scaleTo(0.965, 120)}
        onPressOut={() => {
          scaleTo(1);
          onPressOut?.();
        }}
        accessibilityRole="button"
        accessibilityLabel={m.title}
        accessibilityState={{ selected }}
      >
        <Animated.View style={{ width, height, transform: [{ scale: s }] }}>
          <Svg width={width} height={height} style={StyleSheet.absoluteFill} pointerEvents="none">
            {/* 잘린 모서리 자리: 보드 바탕 (끌 때 그림자·뒤 카드가 비치지 않게 카드 라운드까지) */}
            <Path d={`M${width} ${height - CUT}V${height - 16}A16 16 0 0 1 ${width - 16} ${height}H${width - CUT}Z`} fill={appColor.bg} />
            <Path d={d} fill={p.bg} />
          </Svg>
          {selected ? (
            /* 원본: inset 0 0 0 2.5px var(--a) — 종이 모양 안쪽 테두리 */
            <Svg width={width} height={height} style={StyleSheet.absoluteFill} pointerEvents="none">
              <Defs>
                <ClipPath id={`sel${m.id}`}>
                  <Path d={d} />
                </ClipPath>
              </Defs>
              <Path d={d} fill="none" stroke={appColor.accent} strokeWidth={5} clipPath={`url(#sel${m.id})`} />
            </Svg>
          ) : null}
          {/* 접힌 삼각형: 고른 테두리 위 — 상태가 바뀌어도 모양과 색이 그대로 (원본 .corner) */}
          <Svg width={width} height={height} style={StyleSheet.absoluteFill} pointerEvents="none">
            <Path d={`M${width - CUT} ${height - CUT + 7}A7 7 0 0 1 ${width - CUT + 7} ${height - CUT}H${width}L${width - CUT} ${height}Z`} fill={p.accent} />
          </Svg>
          <View style={st.g}>
            <View style={st.dtr}>
              <Text style={st.dt}>{mmdd(m.created_at)} 작성</Text>
              {m.ai_linked ? (
                <View style={[st.plug, aiSpent && st.plugSpent]}>
                  <View style={{ opacity: aiSpent ? 0.4 : 1 }}>
                    <AppPlug size={12} color={aiSpent ? '#9A9EA7' : '#16161C'} />
                  </View>
                </View>
              ) : null}
            </View>
            <Text style={st.tt} numberOfLines={2}>
              {m.title}
            </Text>
            <Text style={st.bd} numberOfLines={3}>
              {oneLine(m.body)}
            </Text>
          </View>
        </Animated.View>
      </Pressable>
      {m.pinned ? <AppTape color={p.accent} /> : null}
      {m.unread_updates > 0 ? (
        <View style={st.nbAt} pointerEvents="none">
          <View style={st.badge}><Text style={st.badgeT}>{m.unread_updates}</Text></View>
        </View>
      ) : null}
      <SelCircle visible={selecting} on={selected} style={st.gchk} />
    </View>
  );
}

const st = StyleSheet.create({
  g: { paddingTop: 14, paddingHorizontal: 13 },
  dtr: { flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 22 },
  dt: { ...ft(11.5), fontWeight: '500', color: '#4A4A55', flexShrink: 1 },
  plug: { marginLeft: 'auto', width: 22, height: 22, borderRadius: 11, backgroundColor: 'rgba(255,255,255,0.8)', alignItems: 'center', justifyContent: 'center' },
  plugSpent: { backgroundColor: '#E9EAEE' },
  tt: { ...ft(15, 1.36), fontWeight: '800', color: appColor.ink, marginVertical: 6 },
  bd: { ...ft(12.5, 1.5), color: '#2E2E38' },
  nbAt: { position: 'absolute', top: -7, right: -7 },
  gchk: { position: 'absolute', top: -10, left: -8 },
  badge: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: '#FFFFFF', backgroundColor: appColor.red, alignItems: 'center', justifyContent: 'center' },
  badgeT: { ...ft(12, 1), fontWeight: '700', color: '#FFFFFF' },
});
