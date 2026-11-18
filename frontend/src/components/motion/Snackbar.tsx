/* eslint-disable react-hooks/refs -- RN Animated 관용 패턴. React Compiler 켜면 이 파일부터 정리 필요 */
/**
 * 되돌리기 알림 (Lucian #071 snackbar-undo) — 체험판 .snack 값.
 *  - 26px 아래 · .95배 → 제자리 (.45s spring) · 투명도 .2s
 *  - [되돌리기] 옆 원이 남은 시간만큼 줄어듦 (기본 5초) · 끝나면 onTimeout
 *  - 같은 알림이 또 오면(count 증가) 숫자가 1.25배로 톡 (bump .4s)
 * 화면 맨 아래(탭바 위)에 두고 bottom 으로 자리 지정.
 */
import { useEffect, useRef } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { EASE, LINEAR, ND, SPRING, tween, useProgress, useValue } from '@/components/motion/motion';

const M = { bg: '#1F2024', text: '#FFFFFF', undo: '#CDBBFF', ringBack: 'rgba(205,187,255,0.25)' } as const;
const RING = 2 * Math.PI * 9;

export interface SnackbarProps {
  /** null 이면 숨김 */
  message: string | null;
  /** 같은 일이 몇 번 이어졌는지 (예: 3개 지움) — 바뀌면 톡 */
  count?: number;
  actionLabel?: string;
  onAction?: () => void;
  onTimeout: () => void;
  duration?: number;
  bottom?: number;
}

export function Snackbar({ message, count, actionLabel, onAction, onTimeout, duration = 5000, bottom = 96 }: SnackbarProps) {
  const t = useValue(0);
  const bump = useValue(1);
  const last = useRef(message);
  if (message) last.current = message;
  const p = useProgress(`${message}|${count}`, message ? duration : 0, LINEAR);
  const left = message ? 1 - p : 0;
  const done = useRef(onTimeout);
  done.current = onTimeout;

  useEffect(() => {
    tween(t, message ? 1 : 0, message ? 450 : 200, message ? SPRING : EASE, ND).start();
    if (!message) return;
    const id = setTimeout(() => done.current(), duration);
    return () => clearTimeout(id);
  }, [message, count, duration, t]);
  useEffect(() => {
    if (!count) return;
    Animated.sequence([tween(bump, 1.25, 160, EASE, ND), tween(bump, 1, 240, SPRING, ND)]).start();
  }, [count, bump]);

  return (
    <Animated.View pointerEvents={message ? 'auto' : 'none'} accessibilityLiveRegion="polite"
      style={[st.snack, { bottom, opacity: t.interpolate({ inputRange: [0, 1], outputRange: [0, 1], extrapolate: 'clamp' }),
        transform: [{ translateY: t.interpolate({ inputRange: [0, 1], outputRange: [26, 0] }) }, { scale: t.interpolate({ inputRange: [0, 1], outputRange: [0.95, 1] }) }] }]}>
      <Animated.Text style={[st.msg, { transform: [{ scale: bump }] }]} numberOfLines={1}>{last.current}</Animated.Text>
      {actionLabel && onAction && (
        <Pressable onPress={onAction} style={st.undo} accessibilityRole="button">
          <Text style={st.undoText}>{actionLabel}</Text>
          <View>
            <Svg width={22} height={22} viewBox="0 0 22 22">
              <Circle cx={11} cy={11} r={9} stroke={M.ringBack} strokeWidth={2.4} fill="none" />
              <Circle cx={11} cy={11} r={9} stroke={M.undo} strokeWidth={2.4} fill="none" strokeLinecap="round"
                strokeDasharray={`${RING}`} strokeDashoffset={RING * (1 - left)} rotation={-90} origin="11, 11" />
            </Svg>
          </View>
        </Pressable>
      )}
    </Animated.View>
  );
}

const st = StyleSheet.create({
  snack: { position: 'absolute', left: 14, right: 14, height: 52, borderRadius: 14, backgroundColor: M.bg, flexDirection: 'row', alignItems: 'center', paddingLeft: 16, paddingRight: 6, gap: 10 },
  msg: { flex: 1, fontSize: 14, color: M.text },
  undo: { flexDirection: 'row', alignItems: 'center', gap: 8, height: 44, paddingHorizontal: 10 },
  undoText: { fontSize: 14, fontWeight: '800', color: M.undo },
});
