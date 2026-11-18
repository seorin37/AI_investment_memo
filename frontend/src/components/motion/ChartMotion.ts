/**
 * 차트 움직임
 *  - useScrub (Lucian #096 line-chart-scrub): 차트를 누른 채 옆으로 움직이면 가장 가까운 날의 값을 보여 줌. 손을 떼면 사라짐.
 *    PanResponder 만 사용. 세로 스크롤과 겹치지 않게 옆으로 먼저 움직일 때만 차트가 손가락을 가져감.
 *  - useDraw: 선이 왼쪽에서 오른쪽으로 그려짐 (체험판 .chart .ln: 1.2s ease · .15s 뒤 시작)
 *    lineLength 로 점들의 길이를 구해 strokeDasharray/strokeDashoffset 에 씀.
 */
import { useMemo, useRef, useState } from 'react';
import { PanResponder, type GestureResponderEvent } from 'react-native';
import { EASE, useProgress } from '@/components/motion/motion';

export function useScrub(count: number, width: number, padLeft = 0, padRight = 0) {
  const [index, setIndex] = useState<number | null>(null);
  const geo = useRef({ count, width, padLeft, padRight });
  geo.current = { count, width, padLeft, padRight };
  const pick = (e: GestureResponderEvent) => {
    const g = geo.current;
    const inner = Math.max(1, g.width - g.padLeft - g.padRight);
    const x = e.nativeEvent.locationX - g.padLeft;
    const i = Math.round((x / inner) * (g.count - 1));
    setIndex(Math.max(0, Math.min(g.count - 1, i)));
  };
  const pan = useRef(PanResponder.create({
    onStartShouldSetPanResponder: () => false,
    onMoveShouldSetPanResponder: (_, gs) => Math.abs(gs.dx) > 6 && Math.abs(gs.dx) > Math.abs(gs.dy),
    onPanResponderGrant: pick,
    onPanResponderMove: pick,
    onPanResponderRelease: () => setIndex(null),
    onPanResponderTerminate: () => setIndex(null),
    onPanResponderTerminationRequest: () => false,
  })).current;
  /** 길게 눌러도 바로 보이게 (Pressable 대신 View 에 붙임) */
  const onLongPress = pick;
  return { index, panHandlers: pan.panHandlers, onLongPress, clear: () => setIndex(null) };
}

export function lineLength(pts: [number, number][]): number {
  let L = 0;
  for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return Math.max(1, L);
}

/** 반환값을 Path 에 펼쳐 넣음: <Path {...draw(len)} /> */
export function useDraw(replay: unknown, duration = 1200, delay = 150) {
  const p = useProgress(replay, duration, EASE, delay);
  return useMemo(() => (len: number) => ({ strokeDasharray: `${len} ${len}`, strokeDashoffset: len * (1 - p) }), [p]);
}
