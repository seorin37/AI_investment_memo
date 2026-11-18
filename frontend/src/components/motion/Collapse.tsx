/**
 * 접었다 펴기 — 체험판 .ux · .src · .mx (grid-template-rows 0fr → 1fr, .42s ease).
 * 내용 높이를 재서 0 ↔ 높이로 움직임. AI 업데이트의 근거 · 출처 펼치기, 메모 기록 펼치기 등.
 * Chevron: 펼침 화살표가 .35s 로 180° 돎.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { Animated, View, type LayoutChangeEvent } from 'react-native';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { EASE, ND, tween, useValue } from '@/components/motion/motion';

export function Collapse({ open, children, duration = 420 }: { open: boolean; children: ReactNode; duration?: number }) {
  const [h, setH] = useState(0);
  const t = useValue(open ? 1 : 0);
  useEffect(() => { tween(t, open ? 1 : 0, duration, EASE, false).start(); }, [open, t, duration]);
  return (
    <Animated.View style={{ overflow: 'hidden', height: t.interpolate({ inputRange: [0, 1], outputRange: [0, h] }), opacity: t.interpolate({ inputRange: [0, 0.4, 1], outputRange: [0, 1, 1] }) }}>
      <View style={{ position: 'absolute', left: 0, right: 0, top: 0 }} onLayout={(e: LayoutChangeEvent) => setH(e.nativeEvent.layout.height)}>{children}</View>
    </Animated.View>
  );
}

export function Chevron({ open, color, size = 16 }: { open: boolean; color: string; size?: number }) {
  const r = useValue(open ? 1 : 0);
  useEffect(() => { tween(r, open ? 1 : 0, 350, EASE, ND).start(); }, [open, r]);
  return (
    <Animated.View style={{ transform: [{ rotate: r.interpolate({ inputRange: [0, 1], outputRange: ['90deg', '270deg'] }) }] }}>
      <MobileIcon name="chevron_right" size={size} color={color} />
    </Animated.View>
  );
}
