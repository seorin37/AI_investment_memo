/* eslint-disable react-hooks/refs -- RN Animated 관용 패턴. React Compiler 켜면 이 파일부터 정리 필요 */
/**
 * 끌어서 순서 바꾸기 (Lucian #317 sort-flip-list) — 체험판 stock.html 값. 내 종목의 보유·관심 안 순서.
 *  - ⋮⋮ 손잡이를 4px 넘게 움직여야 끌기 시작
 *  - 들어 올린 줄은 손가락을 따라오고 살짝 커지며 그림자
 *  - 다른 줄은 .6s cubic-bezier(.3,1.1,.4,1) 로 비켜 남 · 놓으면 그 자리로 날아가 앉음
 *  - 다 놓으면 onReorder(새 순서)
 * 줄 높이는 같아야 함(row_height). 끄는 동안 바깥 ScrollView 를 멈추려면 onDragging 으로 scrollEnabled 를 끔.
 * (11.18 결정: 메모 보드의 메모 순서 바꾸기는 넣지 않음 — 이 부품은 내 종목에서만)
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Animated, PanResponder, View, type GestureResponderHandlers } from 'react-native';
import { ND, SORT, tween } from '@/components/motion/motion';

const M = { shadow: '#000000' } as const;
/** 들어 올린 줄의 그림자 (그림자 값은 네이티브 애니메이션이 안 돼서 켜고 끄기만) */
const LIFTED = { shadowColor: M.shadow, shadowOpacity: 0.16, shadowRadius: 14, shadowOffset: { width: 0, height: 8 }, elevation: 8 };

export interface SortableListProps<T> {
  data: T[];
  keyOf: (item: T) => string;
  row_height: number;
  enabled: boolean;
  renderRow: (item: T, drag: { handle: GestureResponderHandlers; lifted: boolean }) => ReactNode;
  onReorder: (keys: string[]) => void;
  onDragging?: (dragging: boolean) => void;
}

export function SortableList<T>({ data, keyOf, row_height, enabled, renderRow, onReorder, onDragging }: SortableListProps<T>) {
  const keys = data.map(keyOf);
  const sig = keys.join('|');
  const ys = useRef<Record<string, Animated.Value>>({});
  const lift = useRef<Record<string, Animated.Value>>({});
  keys.forEach((k, i) => {
    if (!ys.current[k]) ys.current[k] = new Animated.Value(i * row_height);
    if (!lift.current[k]) lift.current[k] = new Animated.Value(0);
  });
  const order = useRef<string[]>(keys);
  const [lifted, setLifted] = useState<string | null>(null);

  useEffect(() => {
    order.current = sig ? sig.split('|') : [];
    order.current.forEach((k, i) => tween(ys.current[k], i * row_height, 600, SORT, ND).start());
  }, [sig, row_height]);

  const live = useRef({ onReorder, onDragging, row_height });
  live.current = { onReorder, onDragging, row_height };

  const handles = useMemo(() => {
    const out: Record<string, GestureResponderHandlers> = {};
    keys.forEach((k) => {
      let from = 0, slot = 0;
      out[k] = PanResponder.create({
        onStartShouldSetPanResponder: () => false,
        onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 4,
        onPanResponderTerminationRequest: () => false,
        onPanResponderGrant: () => {
          const h = live.current.row_height;
          from = order.current.indexOf(k); slot = from;
          setLifted(k); live.current.onDragging?.(true);
          tween(lift.current[k], 1, 200, SORT, ND).start();
          ys.current[k].setValue(from * h);
        },
        onPanResponderMove: (_, g) => {
          const h = live.current.row_height, n = order.current.length;
          ys.current[k].setValue(from * h + g.dy);
          const to = Math.max(0, Math.min(n - 1, Math.round((from * h + g.dy) / h)));
          if (to === slot) return;
          slot = to;
          const rest = order.current.filter((x) => x !== k);
          rest.splice(to, 0, k);
          rest.forEach((x, i) => { if (x !== k) tween(ys.current[x], i * h, 600, SORT, ND).start(); });
          order.current = rest;
        },
        onPanResponderRelease: () => finish(k),
        onPanResponderTerminate: () => finish(k),
      }).panHandlers;
    });
    return out;
    function finish(k: string) {
      const h = live.current.row_height;
      const i = order.current.indexOf(k);
      tween(ys.current[k], i * h, 600, SORT, ND).start();
      tween(lift.current[k], 0, 300, SORT, ND).start();
      setLifted(null); live.current.onDragging?.(false);
      live.current.onReorder([...order.current]);
    }
  }, [sig]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <View style={{ height: keys.length * row_height }}>
      {data.map((item) => {
        const k = keyOf(item), L = lift.current[k];
        return (
          <Animated.View key={k} style={{ position: 'absolute', left: 0, right: 0, height: row_height, zIndex: lifted === k ? 2 : 1,
            ...(lifted === k ? LIFTED : null),
            transform: [{ translateY: ys.current[k] }, { scale: L.interpolate({ inputRange: [0, 1], outputRange: [1, 1.02] }) }] }}>
            {renderRow(item, { handle: enabled ? handles[k] : {}, lifted: lifted === k })}
          </Animated.View>
        );
      })}
    </View>
  );
}
