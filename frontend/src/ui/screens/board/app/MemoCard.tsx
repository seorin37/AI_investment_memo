import React, { useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { AppPlug } from '@/ui/icons/BoardGlyphs';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { SelCircle, type AppMemoCardProps } from '@/ui/shared/MemoCard';
import { AppTape } from '@/ui/shared/MemoPaper';
import { mmdd, oneLine } from '@/ui/shared/memoFormat';
import { useDark, usePaper } from '@/ui/shared/Dark';
import { appColor, curve, ft } from '@/ui/theme';
import { useFontScale } from '@/ui/shared/app/fontScale';

/** 접힌 모서리 크기 */
const CUT = 24;
/* 줄 높이 (st.dt · st.tt · st.bd 와 같은 값) · 제목 위아래 여백 */
const DT_LH = ft(11.5).lineHeight as number;
const TT_LH = ft(15.5, 1.36).lineHeight as number;
const BD_LH = ft(13.5, 1.5).lineHeight as number;
const TT_GAP = 12;
/** 카드 라운드 */
const R = 16;

/**
 * 앱 보드 2열 메모 카드 (shared/MemoCard 는 웹도 써서 앱 것을 따로) (원본 memo.html .grid .item)
 * 종이: r16 · 귀퉁이 24 접힘(덧그림) / 안쪽 14·13 / 날짜 줄 최소 22 (날짜 11.5px 500 #4A4A55 · 플러그 22 원 rgba(255,255,255,.8))
 * 제목 15px 800 줄 1.36 · 위아래 6 · 두 줄 / 본문 12.5px 줄 1.5 #2E2E38 · 세 줄
 * 누르면 .12초 뒤 .965 로 줄어듦 (.45s cubic-bezier(.3,1.3,.5,1)) · .48초 꾹 누르면 고르기
 */
export function AppMemoCard({ memo: m, width, height, selecting, selected, aiSpent, onPress, onLongPress, onPressOut }: AppMemoCardProps) {
  const paper = usePaper();
  const dark = useDark();
  const k = useMotionK();
  const p = paper[m.color];
  /* 기기 글자를 키우면(상한 1.3) 카드 높이는 그대로 두고 본문 줄 수를 줄여 줄 중간에서 잘리지 않게. 1.0배는 지금처럼 3줄 */
  const fs = useFontScale();
  const [titleLines, setTitleLines] = useState(2);
  const bodyLines = fs <= 1 ? 3 : Math.max(0, Math.min(3, Math.floor((height - st.g.paddingTop - Math.max(st.dtr.minHeight, DT_LH * fs) - TT_GAP - titleLines * TT_LH * fs) / (BD_LH * fs))));
  const [s] = useState(() => new Animated.Value(1));
  const scaleTo = (v: number, delay = 0) => Animated.timing(s, { toValue: v, duration: 450 * k, delay: delay * k, easing: curve.land, useNativeDriver: NATIVE }).start();
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
          {/* 카드는 라운드 네모 그대로 · 접힌 모서리는 그 위에 덧그림 (투명한 곳이 없어 끌기·그림자·선택에서도 모양이 같음) */}
          <View pointerEvents="none" style={[StyleSheet.absoluteFill, { borderRadius: R, backgroundColor: p.bg }]} />
          <Svg width={width} height={height} style={StyleSheet.absoluteFill} pointerEvents="none">
            {/* 접힌 선 바깥: 카드 색보다 살짝 밝게 (다크는 화면이 반전되므로 어둡게 넣음) */}
            <Path d={`M${width} ${height - CUT}V${height - R}A${R} ${R} 0 0 1 ${width - R} ${height}H${width - CUT}Z`} fill={dark ? '#000000' : '#FFFFFF'} fillOpacity={dark ? 0.15 : 0.5} />
          </Svg>
          {/* 원본: inset 0 0 0 2.5px var(--a) */}
          {selected ? <View pointerEvents="none" style={[StyleSheet.absoluteFill, { borderRadius: R, borderWidth: 2.5, borderColor: appColor.accent }]} /> : null}
          {/* 접힌 삼각형: 고른 테두리 위 (원본 .corner) */}
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
            <Text style={st.tt} numberOfLines={2} onTextLayout={(e) => setTitleLines(Math.max(1, Math.min(2, e.nativeEvent.lines.length)))}>
              {m.title}
            </Text>
            <Text style={st.bd} numberOfLines={bodyLines}>
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
  tt: { ...ft(15.5, 1.36), fontWeight: '800', color: appColor.ink, marginVertical: 6 },
  bd: { ...ft(13.5, 1.5), color: '#2E2E38' },
  nbAt: { position: 'absolute', top: -7, right: -7 },
  gchk: { position: 'absolute', top: -10, left: -8 },
  badge: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: '#FFFFFF', backgroundColor: appColor.red, alignItems: 'center', justifyContent: 'center' },
  badgeT: { ...ft(13, 1), fontWeight: '700', color: '#FFFFFF' },
});
