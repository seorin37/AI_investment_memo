/* eslint-disable react-hooks/refs, react-hooks/purity -- RN Animated 관용 패턴. React Compiler 켜면 이 파일부터 정리 필요 */
/**
 * 축하 (Lucian #093 success-burst) — 체험판 memo.html 값 그대로.
 *  - DotBurst: 체크할 때 상자 둘레로 작은 점 8개가 20~28px 튀며 사라짐 (.52s cubic-bezier(.2,.7,.3,1))
 *  - Confetti: 마지막 항목을 체크하면 색종이 90개가 위로 터져 흩날림
 *    (각도 위쪽 ±0.95rad · 속도 380~800 · 중력 900 · 공기저항 .985/프레임 · 1.6~2.5초 · 끝 .4초 동안 사라짐 · 팔랑임)
 * 색종이 길은 처음에 한 번 계산해 두고, 움직임은 Animated 로 (앱은 네이티브에서 돌아감).
 * fire 값(숫자)이 바뀔 때마다 한 번 터짐.
 */
import { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';
import { BURST, LINEAR, ND, ms, tween, useValue } from '@/components/motion/motion';

const DOTC = ['#22C3A6', '#10B981', '#FFB547', '#FF6B8B', '#7B61FF', '#3D8BFF'] as const;
const N = 90;
const SAMPLES = 30;
/* 26조각 터짐 곡선 (원본 cubic-bezier(.2,.7,.4,1)) */
const POP = Easing.bezier(0.2, 0.7, 0.4, 1);

/** 체크 상자를 감싸는 View 안에 넣음 (가운데 기준) */
export function DotBurst({ fire, size = 24 }: { fire: number; size?: number }) {
  const t = useValue(0);
  /* fire 가 바뀔 때마다 새 방향 */
  const dirs = useMemo(() => Array.from({ length: fire ? 8 : 0 }, (_, i) => { const a = (i / 8) * Math.PI * 2 + 0.3, r = 20 + Math.random() * 8; return [Math.cos(a) * r, Math.sin(a) * r]; }), [fire]);
  useEffect(() => {
    if (!fire) return;
    t.setValue(0);
    tween(t, 1, 520, BURST, ND).start();
  }, [fire, t]);
  if (!fire) return null;
  return (
    <View pointerEvents="none" style={[st.dotBox, { width: size, height: size }]}>
      {dirs.map(([dx, dy], i) => (
        <Animated.View key={i} style={[st.dot, { backgroundColor: DOTC[i % DOTC.length], left: size / 2 - 3, top: size / 2 - 3,
          opacity: t.interpolate({ inputRange: [0, 0.99, 1], outputRange: [1, 1, 0] }),
          transform: [
            { translateX: t.interpolate({ inputRange: [0, 1], outputRange: [0, dx] }) },
            { translateY: t.interpolate({ inputRange: [0, 1], outputRange: [0, dy] }) },
            { scale: t.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }) },
          ] }]} />
      ))}
    </View>
  );
}

type Piece = { life: number; w: number; h: number; col: string; xs: number[]; ys: number[]; rs: string[]; fs: number[]; os: number[] };

function simulate(x: number, y: number): Piece[] {
  return Array.from({ length: N }, (_, i) => {
    const a = -Math.PI / 2 + (Math.random() - 0.5) * 1.9, v = 380 + Math.random() * 420;
    let px = x + (Math.random() - 0.5) * 40, py = y, vx = Math.cos(a) * v, vy = Math.sin(a) * v, r = Math.random() * 6;
    const vr = (Math.random() - 0.5) * 12, wob = Math.random() * 6, life = 1.6 + Math.random() * 0.9;
    const xs: number[] = [], ys: number[] = [], rs: string[] = [], fs: number[] = [], os: number[] = [];
    const dt = 1 / 60, stepsPer = Math.ceil(life / dt / SAMPLES);
    let t = 0;
    for (let s = 0; s <= SAMPLES; s++) {
      xs.push(px); ys.push(py); rs.push(`${(r * 180) / Math.PI}deg`); fs.push(Math.cos(t * 9 + wob)); os.push(Math.max(0, Math.min(1, (life - t) / 0.4)));
      for (let k = 0; k < stepsPer; k++) { vy += 900 * dt; vx *= 0.985; vy *= 0.985; px += vx * dt; py += vy * dt; r += vr * dt; t += dt; }
    }
    return { life, w: 6 + Math.random() * 5, h: 4 + Math.random() * 4, col: DOTC[i % DOTC.length], xs, ys, rs, fs, os };
  });
}

/** 화면 맨 위(전체를 덮는 자리)에 두고, fire 에 {x, y, id} 를 넘기면 그 자리에서 터짐 */
export function Confetti({ fire }: { fire: { x: number; y: number; id: number } | null }) {
  const pieces = useMemo(() => (fire && ms(1) ? simulate(fire.x, fire.y) : []), [fire]);
  const vals = useRef<Animated.Value[]>([]);
  if (vals.current.length !== pieces.length) vals.current = pieces.map(() => new Animated.Value(0));
  useEffect(() => {
    if (!pieces.length) return;
    const a = Animated.parallel(pieces.map((p, i) => tween(vals.current[i], 1, p.life * 1000, LINEAR, ND)));
    a.start();
    return () => a.stop();
  }, [pieces]);
  if (!pieces.length) return null;
  const inR = Array.from({ length: SAMPLES + 1 }, (_, i) => i / SAMPLES);
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      {pieces.map((p, i) => {
        const v = vals.current[i];
        return (
          <Animated.View key={i} style={[st.piece, { width: p.w, height: p.h, marginLeft: -p.w / 2, marginTop: -p.h / 2, backgroundColor: p.col,
            opacity: v.interpolate({ inputRange: inR, outputRange: p.os }),
            transform: [
              { translateX: v.interpolate({ inputRange: inR, outputRange: p.xs }) },
              { translateY: v.interpolate({ inputRange: inR, outputRange: p.ys }) },
              { rotate: v.interpolate({ inputRange: inR, outputRange: p.rs }) },
              { scaleY: v.interpolate({ inputRange: inR, outputRange: p.fs }) },
            ] }]} />
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  dotBox: { position: 'absolute', left: 0, top: 0 },
  dot: { position: 'absolute', width: 6, height: 6, borderRadius: 3 },
  piece: { position: 'absolute', left: 0, top: 0 },
  popBox: { position: 'absolute', left: '50%', top: '50%', width: 0, height: 0, zIndex: 20 },
  pop: { position: 'absolute', left: 0, top: 0, borderRadius: 2 },
});

/**
 * 그 자리에서 사방으로 26조각 (원본 home.html .conf 7×10 · 1.1s / studio.html .cf 7×11 · 1s · cubic-bezier(.2,.7,.4,1))
 * 각도 아무렇게나 · 거리 60~150 · 위로 40 더 · 회전 ±(360|270)도 · 끝으로 갈수록 투명. 체크 상자처럼 기준이 되는 View 안에 넣음 (가운데 기준).
 */
export function PopBurst({ fire, colors, w = 7, h = 10, dur = 1100, spin = 720 }: { fire: number; colors: readonly string[]; w?: number; h?: number; dur?: number; spin?: number }) {
  const t = useValue(0);
  const parts = useMemo(
    () =>
      Array.from({ length: fire ? 26 : 0 }, (_, i) => {
        const a = Math.random() * Math.PI * 2;
        const d = 60 + Math.random() * 90;
        return { x: Math.cos(a) * d, y: Math.sin(a) * d - 40, r: `${Math.random() * spin - spin / 2}deg`, c: colors[i % colors.length] };
      }),
    [fire, colors, spin],
  );
  useEffect(() => {
    if (!fire) return;
    t.setValue(0);
    tween(t, 1, dur, POP, ND).start();
  }, [fire, t, dur]);
  if (!fire) return null;
  return (
    <View pointerEvents="none" style={st.popBox}>
      {parts.map((p, i) => (
        <Animated.View
          key={i}
          style={[
            st.pop,
            {
              width: w,
              height: h,
              marginLeft: -w / 2,
              marginTop: -h / 2,
              backgroundColor: p.c,
              opacity: t.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }),
              transform: [{ translateX: t.interpolate({ inputRange: [0, 1], outputRange: [0, p.x] }) }, { translateY: t.interpolate({ inputRange: [0, 1], outputRange: [0, p.y] }) }, { rotate: t.interpolate({ inputRange: [0, 1], outputRange: ['0deg', p.r] }) }],
            },
          ]}
        />
      ))}
    </View>
  );
}
