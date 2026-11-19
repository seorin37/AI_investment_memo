import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet, type StyleProp, type ViewStyle } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { appColor, curve, dur, ft, shadow, webColor } from '@/ui/theme';

const ACircle = Animated.createAnimatedComponent(Circle);

export interface SnackbarProps {
  visible: boolean;
  message: string;
  /** 되돌리기 (5초 링이 돎) */
  onUndo?: () => void;
  /** 다른 동작 버튼 */
  action?: { label: string; onPress: () => void };
  /** 웹: 앞 초록 체크 */
  check?: boolean;
  /** 위치 (부모가 정함) */
  style?: StyleProp<ViewStyle>;
}

/** 되돌리기 남은 시간 링 (원본 앱 22·r9·2.4 #CDBBFF / 웹 16·r6·2 #15171A, 5초) */
function UndoRing({ variant, run }: { variant: 'app' | 'web'; run: boolean }) {
  const k = useMotionK();
  const app = variant === 'app';
  const r = app ? 9 : 6;
  const len = 2 * Math.PI * r;
  const [off] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!run) return;
    off.setValue(0);
    /* 남은 시간을 알려 주는 링이라 동작 줄이기여도 5초 그대로 (k 를 곱하지 않음) */
    const a = Animated.timing(off, { toValue: len, duration: 5000, easing: Easing.linear, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [run, off, len, k]);
  const s = app ? 22 : 16;
  return (
    <Svg width={s} height={s} viewBox={`0 0 ${s} ${s}`}>
      <Circle cx={s / 2} cy={s / 2} r={r} fill="none" stroke={app ? 'rgba(255,255,255,0.2)' : '#E5E7EB'} strokeWidth={app ? 2.4 : 2} />
      <ACircle cx={s / 2} cy={s / 2} r={r} fill="none" stroke={app ? '#CDBBFF' : webColor.ink} strokeWidth={app ? 2.4 : 2} strokeLinecap={app ? 'round' : 'butt'} strokeDasharray={`${len}`} strokeDashoffset={off} transform={`rotate(-90 ${s / 2} ${s / 2})`} />
    </Svg>
  );
}

function useShow(visible: boolean) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(visible ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: visible ? 1 : 0, duration: (visible ? dur.slow : dur.fast) * k, easing: visible ? curve.spring : curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [visible, v, k]);
  /* 원본: translateY 26 · scale .95 · 투명 → 제자리 (.45s spring · 투명도 .2s) */
  return { opacity: v.interpolate({ inputRange: [0, 0.45, 1], outputRange: [0, 1, 1] }), transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [26, 0] }) }, { scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.95, 1] }) }] };
}

/**
 * 앱 스낵바 (원본 home.html .snack: 좌우 14 · 높이 52 · 라운드 14 · #1F2024 · 글자 14px 흰색 · 안쪽 왼 16 오른 6
 * 되돌리기: #CDBBFF 14px 800 · 높이 42 · 링 22). 위치는 부모(style)가 정함 — 원본은 탭바 위(아래 80), 탭바 없으면 아래 24.
 */
export function AppSnackbar({ visible, message, onUndo, action, style }: SnackbarProps) {
  const anim = useShow(visible);
  const btn = onUndo ? { label: '되돌리기', onPress: onUndo } : action;
  return (
    <Animated.View pointerEvents={visible ? 'auto' : 'none'} style={[st.app, anim, style]} accessibilityLiveRegion="polite">
      <Text style={st.appMsg} numberOfLines={2}>
        {message}
      </Text>
      {btn ? (
        <Pressable onPress={btn.onPress} style={st.appBtn} accessibilityRole="button">
          {onUndo ? <UndoRing variant="app" run={visible} /> : null}
          <Text style={st.appBtnT}>{btn.label}</Text>
        </Pressable>
      ) : null}
    </Animated.View>
  );
}

/**
 * 웹 토스트 (원본 kit.tsx SnackHost: 검정 #15171A 알약 · 최소 높이 46 · 왼 20 · 글자 17px bold 흰색 · 자간 -0.2
 * 버튼: 흰 알약 32 · 좌우 12 · 14px bold. 가운데 아래 30). 위치는 부모(style)가 정함.
 */
export function WebSnackbar({ visible, message, onUndo, action, check, style }: SnackbarProps) {
  const anim = useShow(visible);
  const btn = onUndo ? { label: '되돌리기', onPress: onUndo } : action;
  return (
    <Animated.View pointerEvents={visible ? 'auto' : 'none'} style={[st.web, btn ? st.webWithBtn : null, anim, style]} accessibilityLiveRegion="polite">
      {check ? (
        <Svg width={20} height={20} viewBox="0 0 20 20" fill="none">
          <Circle cx={10} cy={10} r={10} fill="#22C55E" />
          <Path d="M6 10.2L8.6 12.8L14 7.4" stroke="#FFFFFF" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        </Svg>
      ) : null}
      <Text style={st.webMsg} numberOfLines={1}>
        {message}
      </Text>
      {btn ? (
        <Pressable onPress={btn.onPress} style={st.webBtn} accessibilityRole="button">
          {onUndo ? <UndoRing variant="web" run={visible} /> : null}
          <Text style={st.webBtnT}>{btn.label}</Text>
        </Pressable>
      ) : null}
    </Animated.View>
  );
}

const st = StyleSheet.create({
  app: { minHeight: 52, borderRadius: 14, backgroundColor: appColor.snack, flexDirection: 'row', alignItems: 'center', gap: 10, paddingLeft: 16, paddingRight: 6, paddingVertical: 5 },
  appMsg: { flex: 1, ...ft(14), color: '#FFFFFF' },
  appBtn: { minHeight: 42, flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 10 },
  appBtnT: { ...ft(14), fontWeight: '800', color: '#CDBBFF' },
  web: { alignSelf: 'center', minHeight: 46, borderRadius: 999, backgroundColor: webColor.ink, flexDirection: 'row', alignItems: 'center', gap: 10, paddingLeft: 20, paddingRight: 20, paddingVertical: 8, ...shadow.toast },
  webWithBtn: { paddingRight: 8 },
  /* 원본 leading-none */
  webMsg: { fontSize: 17, lineHeight: 17, letterSpacing: -0.2, fontWeight: '700', color: '#FFFFFF' },
  webBtn: { minHeight: 32, borderRadius: 999, backgroundColor: '#FFFFFF', flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12 },
  webBtnT: { fontSize: 14, lineHeight: 14, letterSpacing: -0.2, fontWeight: '700', color: webColor.ink },
});
