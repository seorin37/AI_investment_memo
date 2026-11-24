import React, { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Polygon } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import type { Memo } from '@/types/models';
import { AppPin, AppPlug, CheckMark, Dots } from '@/ui/icons/BoardGlyphs';
import { useMotionK } from '@/ui/motion/useMotion';
import { appColor, curve, fpx, ft, webColor } from '@/ui/theme';
import { Pick } from './MemoCard';
import { mmdd, oneLine } from './memoFormat';
import { usePaper } from '@/ui/shared/Dark';

/** 목록 고르기 원 (원본 .lchk: 폭 0 → 24 · 오른쪽 여백 -12 → 0, .3s ease) */
export function ListCheck({ visible, on }: { visible: boolean; on: boolean }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(visible ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: visible ? 1 : 0, duration: 300 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [visible, v, k]);
  return (
    <Animated.View style={{ width: v.interpolate({ inputRange: [0, 1], outputRange: [0, 24] }), marginRight: v.interpolate({ inputRange: [0, 1], outputRange: [-12, 0] }), opacity: v, height: 24 }}>
      <View style={[st.lchk, on ? st.lchkOn : st.lchkOff]}>{on ? <CheckMark size={14} /> : null}</View>
    </Animated.View>
  );
}

/** 목록 작은 메모지 (원본 .mini: 30×32 · 라운드 5 · 오른쪽 아래 10 삼각형 (접힌 부분 색 | 흰 .75)) */
function Mini({ color }: { color: Memo['color'] }) {
  const paper = usePaper();
  const p = paper[color];
  return (
    <View style={[st.mini, { backgroundColor: p.bg }]}>
      <Svg width={10} height={10} style={st.miniFold}>
        <Polygon points="0,0 10,0 0,10" fill="rgba(255,255,255,0.75)" />
        <Polygon points="10,0 10,10 0,10" fill={p.accent} />
      </Svg>
    </View>
  );
}

export interface AppMemoRowProps {
  memo: Memo;
  width: number;
  selecting: boolean;
  selected: boolean;
  onPress: () => void;
  onLongPress: () => void;
  /** 꾹 누른 뒤 뗌 (끌기 · 고르기 구분) */
  onPressOut?: () => void;
}

/**
 * 앱 목록 줄 (원본 memo.html .list .item: 높이 64 · 바탕 흰 (새 소식 있으면 #FFF5F4) · 아래 선 1 #E6E8EC
 * 안쪽 왼 20 · 오른 16 · 사이 12 / 왼쪽 빨간 막대 4 (새 소식) / 작은 메모지 30×32
 * 제목 15.5px 800 한 줄 (고정이면 앞에 핀 14 #575B63) / 둘째 줄 12.5px #575B63: AI 플러그 16 원 · 'MM.DD' 600 · 본문
 * 오른쪽 배지 24 (12.5px 700). 누르면 바탕 #F1F1F4, 고르면 #F4F0FF)
 */
export function AppMemoRow({ memo: m, width, selecting, selected, onPress, onLongPress, onPressOut }: AppMemoRowProps) {
  const badge = m.unread_updates > 0;
  return (
    <Pressable
      onPress={onPress}
      onLongPress={onLongPress}
      onPressOut={onPressOut}
      delayLongPress={480}
      accessibilityRole="button"
      accessibilityLabel={m.title}
      accessibilityState={{ selected }}
      style={({ pressed }) => [st.row, { width, backgroundColor: selected ? '#F4F0FF' : pressed ? '#F1F1F4' : badge ? '#FFF5F4' : '#FFFFFF' }]}
    >
      {badge ? <View style={st.bar} /> : null}
      <ListCheck visible={selecting} on={selected} />
      <Mini color={m.color} />
      <View style={st.lt}>
        <View style={st.a}>
          {m.pinned ? <AppPin size={14} color={appColor.ink2} /> : null}
          <Text style={st.aT} numberOfLines={1}>
            {m.title}
          </Text>
        </View>
        <View style={st.bRow}>
          {m.ai_linked ? (
            <View style={st.lplug}>
              <AppPlug size={10} />
            </View>
          ) : null}
          <Text style={st.b} numberOfLines={1}>
            <Text style={st.em}>{mmdd(m.created_at)}</Text>
            {/* 원본 em 오른쪽 여백 6 → 띄어쓰기 두 칸 */}
            {'  '}
            {oneLine(m.body)}
          </Text>
        </View>
      </View>
      {badge ? (
        <View style={st.lb}>
          <Text style={st.lbT}>{m.unread_updates}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

export interface WebMemoRowProps {
  memo: Memo;
  first: boolean;
  selecting: boolean;
  selected: boolean;
  onOpen: () => void;
  onPick: () => void;
  onMenu: (at: { x: number; y: number }) => void;
}

type HoverState = { pressed: boolean; hovered?: boolean };

/**
 * 웹 목록 줄 (원본 memox.tsx MemoList: 높이 76 · 좌우 20 · 사이 16 · 위 선 #F0F1F3 · hover #F9F9F9
 * 메모지 40 (라운드 10 10 0 10) · 제목 17/26 bold + '고정' 태그 · 둘째 줄 14/21 #747D8D 'MM.DD 작성 · 본문'
 * 'AI 연결' 칩 (28 · #F2F3F4 · 13 bold) · 배지 24 · ⋯ 32)
 */
export function WebMemoRow({ memo: m, first, selecting, selected, onOpen, onPick, onMenu }: WebMemoRowProps) {
  const paper = usePaper();
  return (
    <Pressable onPress={selecting ? onPick : onOpen} accessibilityLabel={m.title} style={({ hovered }: HoverState) => [st.wrow, !first && st.wline, hovered && { backgroundColor: webColor.hover }]}>
      {selecting ? <Pick on={selected} /> : null}
      <View style={[st.wsw, { backgroundColor: paper[m.color].bg }]} />
      <View style={st.wmid}>
        <View style={st.wtop}>
          <Text style={st.wt} numberOfLines={1}>
            {m.title}
          </Text>
          {m.pinned ? (
            <View style={st.wpin}>
              <Text style={st.wpinT}>고정</Text>
            </View>
          ) : null}
        </View>
        <Text style={st.wsub} numberOfLines={1}>
          {mmdd(m.created_at)} 작성 · {oneLine(m.body)}
        </Text>
      </View>
      {m.ai_linked ? (
        <View style={st.wai}>
          <Text style={st.waiT}>AI 연결</Text>
        </View>
      ) : null}
      {m.unread_updates > 0 ? (
        <View style={st.wbadge}>
          <Text style={st.wbadgeT}>{m.unread_updates}</Text>
        </View>
      ) : null}
      {!selecting ? (
        <Pressable onPress={(e) => onMenu({ x: e.nativeEvent.pageX - 220, y: e.nativeEvent.pageY + 6 })} accessibilityRole="button" accessibilityLabel="메모 메뉴" style={({ hovered }: HoverState) => [st.wdots, hovered && { backgroundColor: webColor.chip }]}>
          <Dots color={webColor.sub2} />
        </Pressable>
      ) : null}
    </Pressable>
  );
}

const st = StyleSheet.create({
  row: { height: 64, flexDirection: 'row', alignItems: 'center', gap: 12, paddingLeft: 20, paddingRight: 16, borderBottomWidth: 1, borderBottomColor: appColor.line },
  bar: { position: 'absolute', left: 0, top: 0, bottom: 0, width: 4, backgroundColor: appColor.red },
  lchk: { width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  lchkOff: { backgroundColor: '#FFFFFF', borderWidth: 2, borderColor: '#C9CDD4' },
  lchkOn: { backgroundColor: appColor.accent },
  mini: { width: 30, height: 32, borderRadius: 5, overflow: 'hidden' },
  miniFold: { position: 'absolute', right: 0, bottom: 0 },
  lt: { flex: 1, minWidth: 0 },
  a: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  aT: { ...ft(15.5), fontWeight: '800', color: appColor.ink, flexShrink: 1 },
  bRow: { flexDirection: 'row', alignItems: 'center', marginTop: 2 },
  b: { ...ft(12.5), color: appColor.ink2, flexShrink: 1 },
  em: { fontWeight: '600', color: appColor.ink },
  /* AI 플러그 16 원 (#EEE9FB) · 오른쪽 4 */
  lplug: { width: 16, height: 16, borderRadius: 8, backgroundColor: appColor.accentSoft, alignItems: 'center', justifyContent: 'center', marginRight: 4 },
  lb: { width: 24, height: 24, borderRadius: 12, backgroundColor: appColor.red, alignItems: 'center', justifyContent: 'center' },
  lbT: { ...ft(12.5, 1), fontWeight: '700', color: '#FFFFFF' },
  wrow: { height: 76, flexDirection: 'row', alignItems: 'center', gap: 16, paddingHorizontal: 20 },
  wline: { borderTopWidth: 1, borderTopColor: '#F0F1F3' },
  wsw: { width: 40, height: 40, borderTopLeftRadius: 10, borderTopRightRadius: 10, borderBottomLeftRadius: 10 },
  wmid: { flex: 1, minWidth: 0 },
  wtop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  wt: { ...fpx(17, 26), fontWeight: '700', color: webColor.ink, flexShrink: 1 },
  wpin: { borderRadius: 6, backgroundColor: webColor.chip, paddingHorizontal: 6 },
  wpinT: { ...fpx(13, 20), fontWeight: '500', color: webColor.ink2 },
  wsub: { ...fpx(14, 21), color: '#747D8D' },
  wai: { minHeight: 28, borderRadius: 999, backgroundColor: webColor.chip, paddingHorizontal: 10, justifyContent: 'center' },
  waiT: { ...fpx(13, 20), fontWeight: '700', color: webColor.ink },
  wbadge: { minWidth: 24, height: 24, borderRadius: 12, backgroundColor: appColor.red, paddingHorizontal: 6, alignItems: 'center', justifyContent: 'center' },
  wbadgeT: { ...fpx(13, 20), fontWeight: '500', color: '#FFFFFF' },
  wdots: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
});
