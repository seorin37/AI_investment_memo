/* eslint-disable react-hooks/set-state-in-effect -- RN Animated 관용 패턴. React Compiler 켜면 이 파일부터 정리 필요 */
/**
 * 나타나기 — 체험판의 짧은 등장 움직임을 한 부품으로.
 *   up    아래에서 12px 떠오름 · .45s ease · 60ms 차이 (rvin: AI 업데이트 · 보고서 줄)
 *   rise  아래에서 10px · .45s (bein: 빈 보드 안내)
 *   pop   16px 아래 · .96배 → 제자리 · .55s spring · 60ms 차이 (tipop: AI 연결 후보 카드)
 *   pin   옆에서 dx 만큼 · .5s spring · 45ms 차이 (메모 상세 줄들)
 *   drop  위에서 8px · .45s spring (ckin: 새 체크 항목)
 *   tab   .96배 → 제자리 · .21s (ft: 탭 내용 바뀔 때)
 *   fade  투명 → 보임 · .25s
 *   scale 0 → 1 · .55s spring (pop2: 완료 체크 원)
 *   step  옆에서 dx 만큼 · .55s ease (#042 단계 넘기기, dx = ±폭 40%)
 * replay 값이 바뀌면 다시 재생.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Animated, type StyleProp, type ViewStyle } from 'react-native';
import { EASE, SPRING, STANDARD, ND, tween, useValue } from '@/components/motion/motion';

export type AppearKind = 'up' | 'rise' | 'pop' | 'pin' | 'drop' | 'tab' | 'fade' | 'scale' | 'step';

const P: Record<AppearKind, { x?: number; y?: number; s?: number; dur: number; ease: (t: number) => number; gap: number }> = {
  up: { y: 12, dur: 450, ease: EASE, gap: 60 },
  rise: { y: 10, dur: 450, ease: EASE, gap: 0 },
  pop: { y: 16, s: 0.96, dur: 550, ease: SPRING, gap: 60 },
  pin: { x: 14, dur: 500, ease: SPRING, gap: 45 },
  drop: { y: -8, dur: 450, ease: SPRING, gap: 0 },
  tab: { s: 0.96, dur: 210, ease: STANDARD, gap: 0 },
  fade: { dur: 250, ease: EASE, gap: 0 },
  scale: { s: 0, dur: 550, ease: SPRING, gap: 0 },
  step: { x: 40, dur: 550, ease: EASE, gap: 0 },
};

export interface AppearProps {
  kind?: AppearKind;
  /** 몇 번째인지 (차례대로 나올 때) */
  index?: number;
  /** pin 의 옆 거리 (기본 14, 왼쪽에서 오면 음수) */
  dx?: number;
  delay?: number;
  replay?: unknown;
  style?: StyleProp<ViewStyle>;
  children?: ReactNode;
}

export function Appear({ kind = 'up', index = 0, dx, delay = 0, replay, style, children }: AppearProps) {
  const p = P[kind];
  const t = useValue(0);
  useEffect(() => {
    t.setValue(0);
    const a = tween(t, 1, p.dur, p.ease, ND, delay + index * p.gap);
    a.start();
    return () => a.stop();
  }, [t, replay, p, delay, index]);

  const transform: ({ translateX: Animated.AnimatedInterpolation<number> } | { translateY: Animated.AnimatedInterpolation<number> } | { scale: Animated.AnimatedInterpolation<number> })[] = [];
  const x = dx ?? p.x;
  if (x) transform.push({ translateX: t.interpolate({ inputRange: [0, 1], outputRange: [x, 0] }) });
  if (p.y) transform.push({ translateY: t.interpolate({ inputRange: [0, 1], outputRange: [p.y, 0] }) });
  if (p.s !== undefined) transform.push({ scale: t.interpolate({ inputRange: [0, 1], outputRange: [p.s, 1] }) });
  const opacity = kind === 'scale' ? 1 : t.interpolate({ inputRange: [0, 1], outputRange: [0, 1], extrapolate: 'clamp' });

  return <Animated.View style={[style, { opacity, transform }]}>{children}</Animated.View>;
}

/**
 * 켜질 때만 톡 (체험판 plugpop: 0 → 1.35 → 1, .6s) — AI 연결 플러그 · 새 소식 배지.
 * 처음 그릴 때는 움직이지 않고, 나중에 show 가 켜지거나 replay 가 바뀌면 튐. 꺼질 때는 .2s 로 작아지며 사라짐.
 */
export function PopWhen({ show, replay, style, children }: { show: boolean; replay?: unknown; style?: StyleProp<ViewStyle>; children?: ReactNode }) {
  const [mounted, setMounted] = useState(show);
  const s = useValue(show ? 1 : 0);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    if (show) {
      setMounted(true);
      s.setValue(0);
      Animated.sequence([tween(s, 1.35, 360, EASE, ND), tween(s, 1, 240, EASE, ND)]).start();
    } else {
      tween(s, 0, 200, EASE, ND).start(({ finished }) => { if (finished) setMounted(false); });
    }
  }, [show, replay, s]);
  if (!mounted) return null;
  return <Animated.View style={[style, { transform: [{ scale: s }] }]}>{children}</Animated.View>;
}
