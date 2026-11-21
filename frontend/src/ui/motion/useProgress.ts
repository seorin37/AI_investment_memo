import { useEffect, useState } from 'react';
import { Animated, Easing } from 'react-native';
import { useMotionK } from './useMotion';

/**
 * run 이 true 가 되면(또는 key 가 바뀌면) ms 동안 0 → 1 (동작 줄이기 배율 적용).
 * SVG 차트처럼 Animated 로 감쌀 수 없는 그림은 이 값으로 다시 그림 (웹에서 Animated SVG 는 DOM 에 collapsable 이 새어 나감).
 */
export function useProgress(run: boolean, ms: number, key: unknown = 0) {
  const k = useMotionK();
  const [t, setT] = useState(0);
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const id = v.addListener(({ value }) => setT(value));
    return () => v.removeListener(id);
  }, [v]);
  useEffect(() => {
    if (!run) return;
    v.setValue(0);
    const a = Animated.timing(v, { toValue: 1, duration: Math.max(1, ms * k), easing: Easing.linear, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [run, ms, k, key, v]);
  return t;
}

/** 전체 진행 t(ms 기준)에서 delay 뒤 dur 동안의 진행 (0~1) */
export const seg = (tMs: number, delay: number, dur: number) => Math.max(0, Math.min(1, (tMs - delay) / dur));
