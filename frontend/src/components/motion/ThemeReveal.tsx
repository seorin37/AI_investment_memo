/**
 * 원으로 번지며 테마 바뀜 (Lucian #219 circular-theme-switch) — 체험판 .7s.
 * 누른 자리에서 새 테마 바탕색 원이 화면을 덮을 때까지 커지고(.7s ease), 다 덮으면 onCovered(여기서 테마를 바꿈),
 * 그 다음 원이 .25s 로 걷힘. (웹의 view-transition 처럼 이전 화면을 사진으로 찍을 수는 없어서, 새 바탕색으로 덮었다 걷는 방식)
 * 화면 맨 위(전체를 덮는 자리)에 둠.
 */
import { useEffect } from 'react';
import { Animated, StyleSheet, View, useWindowDimensions } from 'react-native';
import { EASE, ND, ms, tween, useValue } from '@/components/motion/motion';

export function ThemeReveal({ fire, onCovered }: { fire: { x: number; y: number; color: string; id: number } | null; onCovered: () => void }) {
  const { width: W, height: H } = useWindowDimensions();
  const s = useValue(0);
  const o = useValue(0);
  useEffect(() => {
    if (!fire) return;
    if (!ms(1)) { onCovered(); return; }
    s.setValue(0); o.setValue(1);
    tween(s, 1, 700, EASE, ND).start(({ finished }) => {
      if (!finished) return;
      onCovered();
      tween(o, 0, 250, EASE, ND).start();
    });
  }, [fire]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!fire) return null;
  const R = Math.hypot(Math.max(fire.x, W - fire.x), Math.max(fire.y, H - fire.y));
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <Animated.View style={{ position: 'absolute', left: fire.x - R, top: fire.y - R, width: R * 2, height: R * 2, borderRadius: R, backgroundColor: fire.color, opacity: o, transform: [{ scale: s }] }} />
    </View>
  );
}
