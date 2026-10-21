/**
 * 차트 포인터 — 웹: 마우스 hover/휠, 네이티브: 터치 드래그(Responder)
 * 반환된 ref/handlers 를 차트 컨테이너 View 에 붙이세요.
 */
import { useEffect, useRef, useState } from 'react';
import type React from 'react';
import { Platform, type GestureResponderEvent, type View } from 'react-native';

export function useChartPointer(opts: { onWheel?: (deltaY: number) => void } = {}) {
  // 콜백 ref: 차트가 폭 측정 후에 마운트되므로, 노드가 생길 때 리스너를 붙입니다
  const [node, ref] = useState<React.ComponentRef<typeof View> | null>(null);
  const [x, setX] = useState<number | null>(null);
  const wheelRef = useRef(opts.onWheel);
  useEffect(() => {
    wheelRef.current = opts.onWheel;
  });

  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const el = node as unknown as HTMLElement | null;
    if (!el || typeof el.addEventListener !== 'function') return;
    const move = (e: MouseEvent) => setX(e.clientX - el.getBoundingClientRect().left);
    const leave = () => setX(null);
    const wheel = (e: WheelEvent) => {
      if (!wheelRef.current) return;
      e.preventDefault();
      wheelRef.current(e.deltaY);
    };
    el.addEventListener('mousemove', move);
    el.addEventListener('mouseleave', leave);
    el.addEventListener('wheel', wheel, { passive: false });
    return () => {
      el.removeEventListener('mousemove', move);
      el.removeEventListener('mouseleave', leave);
      el.removeEventListener('wheel', wheel);
    };
  }, [node]);

  const native =
    Platform.OS === 'web'
      ? {}
      : {
          onStartShouldSetResponder: () => true,
          onMoveShouldSetResponder: () => true,
          onResponderGrant: (e: GestureResponderEvent) => setX(e.nativeEvent.locationX),
          onResponderMove: (e: GestureResponderEvent) => setX(e.nativeEvent.locationX),
          onResponderRelease: () => setX(null),
          onResponderTerminate: () => setX(null),
        };

  return { ref, x, setX, handlers: native };
}

/** 보기 좋은 눈금 간격 */
export function niceTicks(min: number, max: number, count = 5): number[] {
  if (min === max) return [min];
  const span = max - min;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const start = Math.floor(min / step) * step;
  const out: number[] = [start];
  while (out[out.length - 1] < max - 1e-9) out.push(Math.round((out[out.length - 1] + step) * 1e6) / 1e6);
  return out;
}
