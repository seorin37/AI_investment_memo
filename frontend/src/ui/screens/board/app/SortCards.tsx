import React, { useEffect, useRef, useState } from 'react';
import { Animated, StyleSheet, View, type GestureResponderEvent, type ScrollView } from 'react-native';
import { useMotionK } from '@/ui/motion/useMotion';
import { curve } from '@/ui/theme';
import { moveCard } from '../boardCards';

const EDGE = 72;
const SLOP = 4;

export interface SortLayout {
  cols: number;
  w: number;
  h: number;
  /** 칸 사이 */
  gx: number;
  gy: number;
  /** 들었을 때 그림자 모서리 */
  radius: number;
}

interface SortCardsProps {
  keys: string[];
  /** 앞에서부터 고정 카드 수 (끌 수 없고, 그 안으로도 못 놓음) */
  pinCount: number;
  layout: SortLayout;
  /** 끌 수 있는 상태인지 (전체 보기 · 고르기 아님) */
  enabled: boolean;
  /** 바깥 스크롤 (끄는 동안 멈추고, 위아래 끝에서 저절로 스크롤) */
  scroll: { current: React.ComponentRef<typeof ScrollView> | null };
  viewport: { current: React.ComponentRef<typeof View> | null };
  scrollY: { current: number };
  onLock: (locked: boolean) => void;
  /** 꾹 눌렀다 그냥 뗌 → 고르기 */
  onHold: (key: string) => void;
  onDrop: (order: string[]) => void;
  renderCard: (key: string, press: { onLongPress: () => void; onPressOut: () => void }) => React.ReactNode;
}

/**
 * 앱 보드 카드 끌어 옮기기 (2열 · 목록 공통, RN 응답자 — 끄는 중에 다시 그려도 이어지게 PanResponder 대신 직접)
 * 꾹 누르면(.48초) 살짝 들림 → 그대로 떼면 고르기, 움직이면 끌기. 끄는 동안 카드 1.05배 + 그림자, 다른 카드는 부드럽게 비켜 줌.
 */
export function SortCards(p: SortCardsProps) {
  const { keys, layout: L } = p;
  const k = useMotionK();
  const [held, setHeld] = useState<string | null>(null);
  const [to, setTo] = useState<number | null>(null);
  const xy = useRef(new Map<string, Animated.ValueXY>());
  const live = useRef(p);
  /* 끄는 동안의 값 */
  const g = useRef({ key: null as string | null, moving: false, x0: 0, y0: 0, px: 0, py: 0, dx: 0, dy: 0, scroll0: 0, at: -1, top: 0, bottom: 0, speed: 0, raf: 0 });
  useEffect(() => {
    live.current = p;
  });

  const pos = (i: number) => ({ x: (i % L.cols) * (L.w + L.gx), y: Math.floor(i / L.cols) * (L.h + L.gy) });
  const shown = held !== null && to !== null ? (moveCard(keys, p.pinCount, held, to) ?? keys) : keys;

  const finish = (commit: boolean) => {
    const s = g.current;
    const { keys: now, pinCount, onLock, onDrop } = live.current;
    cancelAnimationFrame(s.raf);
    const next = commit && s.moving && s.key ? moveCard(now, pinCount, s.key, s.at) : null;
    s.key = null;
    s.moving = false;
    s.speed = 0;
    setHeld(null);
    setTo(null);
    onLock(false);
    if (next) onDrop(next);
  };
  const place = () => {
    const s = g.current;
    const { keys: now, pinCount, layout: l, scrollY } = live.current;
    if (!s.key) return;
    const x = s.x0 + s.dx;
    const y = s.y0 + s.dy + (scrollY.current - s.scroll0);
    xy.current.get(s.key)?.setValue({ x, y });
    const col = Math.max(0, Math.min(l.cols - 1, Math.round(x / (l.w + l.gx))));
    const row = Math.max(0, Math.round(y / (l.h + l.gy)));
    const at = Math.max(pinCount, Math.min(now.length - 1, row * l.cols + col));
    if (at !== s.at) {
      s.at = at;
      setTo(at);
    }
  };
  const auto = () => {
    const s = g.current;
    if (!s.moving) return;
    if (s.speed) {
      live.current.scroll.current?.scrollTo({ y: Math.max(0, live.current.scrollY.current + s.speed), animated: false });
      place();
    }
    s.raf = requestAnimationFrame(auto);
  };

  const onTouchDown = (e: GestureResponderEvent) => {
    g.current.px = e.nativeEvent.pageX;
    g.current.py = e.nativeEvent.pageY;
    return false;
  };
  const onWantMove = (e: GestureResponderEvent) => {
    const s = g.current;
    if (!s.key || s.moving) return s.moving;
    if (Math.hypot(e.nativeEvent.pageX - s.px, e.nativeEvent.pageY - s.py) < SLOP) return false;
    /* 카드의 '누름 끝'보다 먼저 표시 → 고르기로 넘어가지 않게 */
    s.moving = true;
    return true;
  };
  const onGrant = () => {
    const s = g.current;
    s.scroll0 = live.current.scrollY.current;
    live.current.viewport.current?.measureInWindow((_x, y, _w, h) => {
      s.top = y;
      s.bottom = y + h;
    });
    s.raf = requestAnimationFrame(auto);
  };
  const onMove = (e: GestureResponderEvent) => {
    const s = g.current;
    const y = e.nativeEvent.pageY;
    s.dx = e.nativeEvent.pageX - s.px;
    s.dy = y - s.py;
    s.speed = !s.bottom ? 0 : y < s.top + EDGE ? -Math.ceil((s.top + EDGE - y) / 6) : y > s.bottom - EDGE ? Math.ceil((y - (s.bottom - EDGE)) / 6) : 0;
    place();
  };
  useEffect(() => {
    const s = g.current;
    return () => cancelAnimationFrame(s.raf);
  }, []);

  const onArm = (key: string) => {
    const i = keys.indexOf(key);
    if (!p.enabled || i < p.pinCount) return p.onHold(key);
    const at = pos(i);
    Object.assign(g.current, { key, moving: false, x0: at.x, y0: at.y, dx: 0, dy: 0, at: i, speed: 0, bottom: 0 });
    setHeld(key);
    setTo(i);
    p.onLock(true);
  };
  const onOut = (key: string) => {
    const s = g.current;
    if (s.key !== key || s.moving) return;
    finish(false);
    p.onHold(key);
  };
  const onCell = (key: string, v: Animated.ValueXY | null) => {
    if (v) xy.current.set(key, v);
    else xy.current.delete(key);
  };

  const rows = Math.ceil(keys.length / L.cols);
  return (
    <View style={{ height: Math.max(0, rows * (L.h + L.gy) - L.gy), userSelect: 'none' }}
      onStartShouldSetResponderCapture={onTouchDown}
      onMoveShouldSetResponderCapture={onWantMove}
      onResponderGrant={onGrant}
      onResponderMove={onMove}
      onResponderRelease={() => finish(true)}
      onResponderTerminate={() => finish(false)}
      onResponderTerminationRequest={() => false}
    >
      {keys.map((key) => (
        <Cell key={key} id={key} at={pos(shown.indexOf(key))} held={held === key} layout={L} k={k} onCell={onCell} onArm={onArm} onOut={onOut} render={p.renderCard} />
      ))}
    </View>
  );
}

interface CellProps {
  id: string;
  at: { x: number; y: number };
  held: boolean;
  layout: SortLayout;
  k: number;
  onCell: (key: string, v: Animated.ValueXY | null) => void;
  onArm: (key: string) => void;
  onOut: (key: string) => void;
  render: SortCardsProps['renderCard'];
}

function Cell({ id, at, held, layout, k, onCell, onArm, onOut, render }: CellProps) {
  const [v] = useState(() => new Animated.ValueXY(at));
  const [lift] = useState(() => new Animated.Value(0));
  useEffect(() => {
    onCell(id, v);
    return () => onCell(id, null);
  });
  const { x, y } = at;
  useEffect(() => {
    if (held) return;
    const a = Animated.timing(v, { toValue: { x, y }, duration: 280 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [x, y, held, v, k]);
  useEffect(() => {
    const a = Animated.timing(lift, { toValue: held ? 1 : 0, duration: 180 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [held, lift, k]);
  return (
    <Animated.View
      style={[
        st.cell,
        { width: layout.w, height: layout.h, transform: [{ translateX: v.x }, { translateY: v.y }, { scale: lift.interpolate({ inputRange: [0, 1], outputRange: [1, 1.05] }) }] },
        held && { zIndex: 30, borderRadius: layout.radius, boxShadow: '0px 12px 24px rgba(17,17,17,0.24)' },
      ]}
    >
      {render(id, { onLongPress: () => onArm(id), onPressOut: () => onOut(id) })}
    </Animated.View>
  );
}

const st = StyleSheet.create({
  cell: { position: 'absolute', left: 0, top: 0 },
});
