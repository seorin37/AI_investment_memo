/**
 * 미끄러지는 선택 알약 (Lucian #039 sliding tabs pill · #047 segmented control)
 * 고른 칸 뒤의 알약이 다음 칸으로 미끄러져 크기까지 맞춰짐 — .5s spring (체험판 .vt .knob · .ptab).
 * 쓰는 곳: [메모 보드|기업정보] · 메모 상세 탭 · 차트 기간 · 2열/목록 · 필터 칩.
 * 색·크기는 화면이 넘김 (이 파일에는 색 없음).
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Animated, Pressable, StyleSheet, Text, View, type LayoutChangeEvent, type StyleProp, type TextStyle, type ViewStyle } from 'react-native';
import { SPRING, tween, useValue } from '@/components/motion/motion';

export interface PillItem<K extends string> {
  key: K;
  label?: string;
  /** 글자 대신 아이콘 등 (on 여부를 받아 그림) */
  render?: (on: boolean) => ReactNode;
  accessibilityLabel?: string;
}

export interface SlidingPillProps<K extends string> {
  items: PillItem<K>[];
  value: K;
  onChange: (key: K) => void;
  /** 칸을 똑같은 폭으로 (탭) / 글자 폭대로 (칩) */
  equal?: boolean;
  style?: StyleProp<ViewStyle>;
  itemStyle?: StyleProp<ViewStyle>;
  itemOnStyle?: StyleProp<ViewStyle>;
  pillStyle?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
  textOnStyle?: StyleProp<TextStyle>;
  gap?: number;
  hitSlop?: number;
  /** 처음 그릴 때 알약이 이 칸에서 출발해 value 로 미끄러짐 (화면이 바뀌어도 이어져 보이게) */
  from?: K;
}

type Box = { x: number; y: number; w: number; h: number };

export function SlidingPill<K extends string>(props: SlidingPillProps<K>) {
  const { items, value, onChange, equal, style, itemStyle, itemOnStyle, pillStyle, textStyle, textOnStyle, gap = 0, hitSlop = 0, from } = props;
  const boxes = useRef<Partial<Record<K, Box>>>({});
  const [ready, setReady] = useState(false);
  const x = useValue(0), y = useValue(0), w = useValue(0), h = useValue(0);
  const first = useRef(true);

  const move = (k: K) => {
    const b = boxes.current[k];
    if (!b) return;
    if (first.current) {
      const f = from && from !== k ? boxes.current[from] : undefined;
      if (from && from !== k && !f) return; // 출발 칸을 아직 못 잼
      const s0 = f ?? b;
      x.setValue(s0.x); y.setValue(s0.y); w.setValue(s0.w); h.setValue(s0.h);
      first.current = false; setReady(true);
      if (!f) return;
    }
    Animated.parallel([tween(x, b.x, 500, SPRING, false), tween(y, b.y, 500, SPRING, false), tween(w, b.w, 500, SPRING, false), tween(h, b.h, 500, SPRING, false)]).start();
  };
  useEffect(() => { move(value); }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  const onItemLayout = (k: K) => (e: LayoutChangeEvent) => {
    const { x: bx, y: by, width, height } = e.nativeEvent.layout;
    const prev = boxes.current[k];
    boxes.current[k] = { x: bx, y: by, w: width, h: height };
    if (first.current) { move(value); return; }
    if (k === value && prev && (prev.w !== width || prev.x !== bx)) { x.setValue(bx); y.setValue(by); w.setValue(width); h.setValue(height); }
  };

  return (
    <View style={[st.row, { gap }, style]}>
      <Animated.View pointerEvents="none" style={[st.pill, pillStyle, { left: x, top: y, width: w, height: h, opacity: ready ? 1 : 0 }]} />
      {items.map((it) => {
        const on = it.key === value;
        return (
          <Pressable key={it.key} onLayout={onItemLayout(it.key)} onPress={() => onChange(it.key)} hitSlop={hitSlop}
            style={[st.item, equal && st.equal, itemStyle, on && itemOnStyle]}
            accessibilityRole="tab" accessibilityState={{ selected: on }} accessibilityLabel={it.accessibilityLabel ?? it.label}>
            {it.render ? it.render(on) : <Text style={[textStyle, on && textOnStyle]} numberOfLines={1}>{it.label}</Text>}
          </Pressable>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center' },
  pill: { position: 'absolute' },
  item: { alignItems: 'center', justifyContent: 'center', flexDirection: 'row' },
  equal: { flex: 1 },
});
