import React, { useEffect, useMemo, useState } from 'react';
import { Animated, PanResponder, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { AppPin, SelIcon } from '@/ui/icons/BoardGlyphs';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { appColor, curve, ft } from '@/ui/theme';
import type { SwipeRowProps } from './SwipeRow.types';

const OPEN_X_MEMO = -144;
const PIN_AT_MEMO = 70;

/**
 * 앱 목록 줄 밀기 (원본 memo.html bindItem · Lucian #071)
 * 가로로 8 넘게 + 세로보다 크게 움직이면 밀기. 오른쪽: 96 넘으면 ×.3 · 70 넘겨 놓으면 고정 (주황 #F29A1F 바탕, 핀 22가 1.25배)
 * 왼쪽: [AI 연결 #8569E3 · 휴지통 #E5484D] 72씩 · -144 에서 멈춤 (넘으면 ×.25). 놓을 때 -60 보다 멀고 느리거나 빠르게 왼쪽이면 열림.
 * 안쪽 줄의 누르기(Pressable)는 그대로 — 이 부품을 Pressable 로 감싸지 않음 (규칙 5).
 */
export function SwipeRow({ enabled, open, onOpenChange, onPin, pinLabel, onAi, aiLabel, onDelete, children, kind = 'memo' }: SwipeRowProps) {
  const k = useMotionK();
  const J = kind === 'journal';
  const OPEN_X = J ? -88 : OPEN_X_MEMO;
  const PIN_AT = J ? 60 : PIN_AT_MEMO;
  const [x] = useState(() => new Animated.Value(0));
  /* 바깥에서 열고 닫을 때 (다른 줄을 밀거나 뒤로 가기) 제자리로 (원본 .face transform .45s cubic-bezier(.3,1.3,.5,1)) */
  useEffect(() => {
    const a = Animated.timing(x, { toValue: open ? OPEN_X : 0, duration: 450 * k, easing: curve.land, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [open, x, k, OPEN_X]);
  const pan = useMemo(() => {
    /* 끄는 동안의 값 (처리기끼리 나눠 씀) */
    const s = { base: 0, cur: 0 };
    const rubber = (v0: number) => {
      let v = v0;
      if (s.base < 0 && v > 0) v *= 0.2;
      if (J) {
        if (v > 70) v = 70 + (v - 70) * 0.35;
        if (v < OPEN_X) v = OPEN_X + (v - OPEN_X) * 0.3;
        return v;
      }
      if (v > 96) v = 96 + (v - 96) * 0.3;
      if (v < OPEN_X) v = OPEN_X + (v - OPEN_X) * 0.25;
      return v;
    };
    return PanResponder.create({
      onMoveShouldSetPanResponderCapture: (_, g) => enabled && Math.abs(g.dx) > 8 && Math.abs(g.dx) > Math.abs(g.dy),
      onPanResponderGrant: () => {
        x.stopAnimation();
        s.base = open ? OPEN_X : 0;
        s.cur = s.base;
      },
      onPanResponderMove: (_, g) => {
        s.cur = rubber(s.base + g.dx);
        x.setValue(s.cur);
      },
      onPanResponderRelease: (_, g) => {
        const cur = s.cur;
        if (s.base === 0 && cur > PIN_AT) {
          Animated.timing(x, { toValue: 0, duration: 450 * k, easing: curve.land, useNativeDriver: NATIVE }).start();
          onOpenChange(false);
          onPin();
          return;
        }
        const willOpen = J ? cur < -44 : cur < 0 && ((cur < -60 && g.vx < 0.3) || g.vx < -0.5);
        Animated.timing(x, { toValue: willOpen ? OPEN_X : 0, duration: 450 * k, easing: curve.land, useNativeDriver: NATIVE }).start();
        onOpenChange(willOpen);
      },
      onPanResponderTerminate: () => {
        Animated.timing(x, { toValue: open ? OPEN_X : 0, duration: 300 * k, easing: curve.ease, useNativeDriver: NATIVE }).start();
      },
      onPanResponderTerminationRequest: () => false,
    });
  }, [enabled, open, onOpenChange, onPin, x, k, J, OPEN_X, PIN_AT]);
  const pinScale = x.interpolate({ inputRange: J ? [64, 64.01] : [PIN_AT, PIN_AT + 0.01], outputRange: [1, 1.25], extrapolate: 'clamp' });
  return (
    <View style={st.wrap} {...pan.panHandlers}>
      {/* 오른쪽으로 밀면 드러나는 고정 (원본 .actl: 왼쪽 24 · 사이 8 · 13px 700) */}
      <Animated.View style={[st.actl, J && st.actlJ, { opacity: x.interpolate({ inputRange: [0, 1], outputRange: [0, 1], extrapolate: 'clamp' }) }]}>
        <Animated.View style={{ transform: [{ scale: pinScale }] }}>
          {J ? <JPin /> : <AppPin size={22} color="#FFFFFF" />}
        </Animated.View>
        <Text style={J ? st.actT : st.actlT}>{pinLabel}</Text>
      </Animated.View>
      {/* 왼쪽으로 밀면 드러나는 동작 (원본 .acts · .act 72 · 12px 700 · 사이 4) */}
      <Animated.View style={[st.acts, { opacity: x.interpolate({ inputRange: [-1, 0], outputRange: [1, 0], extrapolate: 'clamp' }) }]}>
        {onAi ? (
        <Pressable onPress={onAi} style={[st.act, { backgroundColor: appColor.accent }]} accessibilityRole="button" accessibilityLabel={aiLabel}>
          <SelIcon k="ai" color="#FFFFFF" size={20} />
          <Text style={st.actT}>{aiLabel}</Text>
        </Pressable>
        ) : null}
        <Pressable onPress={onDelete} style={[st.act, J && st.actJ, { backgroundColor: appColor.red }]} accessibilityRole="button" accessibilityLabel="휴지통">
          {J ? <JTrash /> : <SelIcon k="del" color="#FFFFFF" size={20} stroke={2} />}
          <Text style={st.actT}>휴지통</Text>
        </Pressable>
      </Animated.View>
      <Animated.View style={{ transform: [{ translateX: x }] }}>{children}</Animated.View>
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { overflow: 'hidden' },
  actl: { ...StyleSheet.absoluteFill, bottom: 1, flexDirection: 'row', alignItems: 'center', gap: 8, paddingLeft: 24, backgroundColor: '#F29A1F' },
  actlT: { ...ft(14), fontWeight: '700', color: '#FFFFFF' },
  acts: { position: 'absolute', top: 0, right: 0, bottom: 1, flexDirection: 'row' },
  act: { width: 72, alignItems: 'center', justifyContent: 'center', gap: 4 },
  actT: { ...ft(13), fontWeight: '700', color: '#FFFFFF' },
  /* 투자 기록 (원본 .jr .al: 주황 #F2A33A · 세로 · 왼쪽 22 · 사이 3 / .ar: 88 · 사이 3) */
  actlJ: { flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'center', gap: 3, paddingLeft: 22, bottom: 0, backgroundColor: appColor.org },
  actJ: { width: 88, gap: 3 },
});

/* 원본 journal.html PIN · TRASH (20 · 흰 2) */
function JPin() {
  return (
    <Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M9 4h6l-1 6 4 3v2H6v-2l4-3zM12 15v6" />
    </Svg>
  );
}
function JTrash() {
  return (
    <Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
    </Svg>
  );
}
