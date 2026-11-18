/**
 * 줄 밀기 — 체험판 memo.html(목록 보기) · journal.html 값 그대로. RN 기본 PanResponder 만 사용.
 *  - 옆으로 8px 넘게, 세로보다 많이 움직여야 밀기 시작 (세로 스크롤과 안 겹치게)
 *  - 오른쪽으로 밀기 → 왼쪽에 주황 "고정"이 드러남. 70px 넘으면 아이콘이 1.25배로 커지고, 손을 떼면 고정(onLeft)
 *    (메모 96px · 기록 70px 넘으면 고무줄처럼 덜 따라옴)
 *  - 왼쪽으로 밀기 → 오른쪽 버튼(예: AI 연결 · 삭제)이 열림. 60px 넘게 밀거나 빠르게 밀면 열린 채 멈춤
 *    (열린 폭을 넘으면 고무줄 · 열린 줄을 오른쪽으로 밀면 0.2배만 따라옴)
 *  - 놓을 때 .3s cubic-bezier(.3,1.2,.5,1) 로 자리 잡음 · 열린 줄을 누르면 닫힘
 * 한 번에 한 줄만 열리게 open / onOpenChange 로 부모가 관리.
 */
import { useEffect, useRef, type ReactNode } from 'react';
import { Animated, Easing, PanResponder, Pressable, StyleSheet, Text, View } from 'react-native';
import { MobileIcon, type MobileIconName } from '@/components/icons/MobileIcons';
import { ND, SPRING, tween, useValue } from '@/components/motion/motion';

const M = { white: '#FFFFFF' } as const;
const SETTLE = Easing.bezier(0.3, 1.2, 0.5, 1);

export interface SwipeAction {
  key: string;
  label: string;
  icon: MobileIconName;
  color: string;
  onPress: () => void;
}

export interface SwipeRowProps {
  children: ReactNode;
  enabled: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 오른쪽으로 밀어 실행 (고정) — 없으면 오른쪽 밀기 없음 */
  left?: { label: string; icon: MobileIconName; color: string; onTrigger: () => void };
  /** 왼쪽으로 밀어 여는 버튼들 (각 72px · 기록은 88px 하나) */
  right?: SwipeAction[];
  action_width?: number;
  /** 오른쪽 밀기 고무줄 시작 거리 (메모 96 · 기록 70) */
  left_max?: number;
  /** 부모 높이를 꽉 채움 (높이가 정해진 칸 안에 둘 때) */
  fill?: boolean;
}

export function SwipeRow({ children, enabled, open, onOpenChange, left, right = [], action_width = 72, left_max = 96, fill }: SwipeRowProps) {
  const openW = right.length * action_width;
  const x = useValue(0);
  const big = useValue(0);
  const live = useRef({ open, openW, left, left_max, onOpenChange, enabled });
  live.current = { open, openW, left, left_max, onOpenChange, enabled };
  const cur = useRef(0);

  useEffect(() => {
    const to = open ? -openW : 0;
    cur.current = to;
    tween(x, to, 300, SETTLE, ND).start();
  }, [open, openW, x]);

  const pan = useRef(PanResponder.create({
    onMoveShouldSetPanResponder: (_, g) => live.current.enabled && Math.abs(g.dx) > 8 && Math.abs(g.dx) > Math.abs(g.dy),
    onPanResponderTerminationRequest: () => false,
    onPanResponderGrant: () => {},
    onPanResponderMove: (_, g) => {
      const L = live.current;
      const base = L.open ? -L.openW : 0;
      let v = base + g.dx;
      if (!L.left && v > 0) v = 0;
      if (base < 0 && v > 0) v *= 0.2;
      if (v > L.left_max) v = L.left_max + (v - L.left_max) * 0.3;
      if (L.openW === 0 && v < 0) v = 0;
      if (v < -L.openW) v = -L.openW + (v + L.openW) * 0.25;
      cur.current = v;
      x.setValue(v);
      const go = !!L.left && v > 70 ? 1 : 0;
      tween(big, go, 350, SPRING, ND).start();
    },
    onPanResponderRelease: (_, g) => {
      const L = live.current;
      const v = cur.current;
      tween(big, 0, 200, SPRING, ND).start();
      if (!L.open && L.left && v > 70) {
        tween(x, 0, 300, SETTLE, ND).start();
        setTimeout(() => L.left?.onTrigger(), 160);
        return;
      }
      const shouldOpen = L.openW > 0 && v < 0 && ((v < -60 && g.vx < 0.3) || g.vx < -0.5);
      tween(x, shouldOpen ? -L.openW : 0, 300, SETTLE, ND).start();
      cur.current = shouldOpen ? -L.openW : 0;
      if (shouldOpen !== L.open) L.onOpenChange(shouldOpen);
    },
    onPanResponderTerminate: () => {
      const L = live.current;
      tween(x, L.open ? -L.openW : 0, 300, SETTLE, ND).start();
    },
  })).current;

  const leftO = x.interpolate({ inputRange: [0, 1], outputRange: [0, 1], extrapolate: 'clamp' });
  const rightO = x.interpolate({ inputRange: [-1, 0], outputRange: [1, 0], extrapolate: 'clamp' });
  return (
    <View style={[st.wrap, fill && st.fill]}>
      {left && (
        <Animated.View style={[st.left, { backgroundColor: left.color, opacity: leftO }]}>
          <Animated.View style={{ transform: [{ scale: big.interpolate({ inputRange: [0, 1], outputRange: [1, 1.25] }) }] }}>
            <MobileIcon name={left.icon} size={20} color={M.white} />
          </Animated.View>
          <Text style={st.leftText}>{left.label}</Text>
        </Animated.View>
      )}
      {right.length > 0 && (
        <Animated.View style={[st.right, { opacity: rightO }]}>
          {right.map((a) => (
            <Pressable key={a.key} style={[st.act, { width: action_width, backgroundColor: a.color }]} onPress={() => { onOpenChange(false); a.onPress(); }} accessibilityRole="button" accessibilityLabel={a.label}>
              <MobileIcon name={a.icon} size={20} color={M.white} strokeWidth={1.8} />
              <Text style={st.actText}>{a.label}</Text>
            </Pressable>
          ))}
        </Animated.View>
      )}
      <Animated.View style={[fill && st.fill, { transform: [{ translateX: x }] }]} {...pan.panHandlers}>
        {children}
        {open && <Pressable style={StyleSheet.absoluteFill} onPress={() => onOpenChange(false)} accessibilityLabel="닫기" />}
      </Animated.View>
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { overflow: 'hidden' },
  fill: { flex: 1 },
  left: { position: 'absolute', left: 0, top: 0, bottom: 1, right: 0, flexDirection: 'row', alignItems: 'center', gap: 8, paddingLeft: 24 },
  leftText: { fontSize: 13, fontWeight: '700', color: M.white },
  right: { position: 'absolute', right: 0, top: 0, bottom: 1, flexDirection: 'row' },
  act: { alignItems: 'center', justifyContent: 'center', gap: 4 },
  actText: { fontSize: 12, fontWeight: '700', color: M.white },
});
