import React, { useMemo, useState } from 'react';
import { Easing, PanResponder, View, type GestureResponderEvent } from 'react-native';
import Svg, { Circle, G, Line, Path, Polygon, Rect, Text as SvgText } from 'react-native-svg';
import type { Candle } from '@/types/models';
import { seg, useProgress } from '@/ui/motion/useProgress';
import type { CompanyQuarter } from '../CompanyInfo.types';
import { yoyAt, type FinKey } from '../companyFormat';

/* 원본 company.html 차트들 — react-native-svg. 애니메이션은 진행 값(0→1)을 받아 다시 그림 (SVG 를 Animated 로 감싸지 않음) */

const springE = Easing.bezier(0.34, 1.45, 0.64, 1);
const easeE = Easing.bezier(0.2, 0.8, 0.2, 1);
const clamp01 = (n: number) => Math.max(0, Math.min(1, n));


/* ---------- 주가 차트 (원본 drawCandles · hover · #096 누른 채 훑기) ---------- */
export const CANDLE_H = 232;
const H = 168;
const VT = 180;
const VH = 48;

/**
 * 캔들 + 거래량 (높이 232: 캔들 168 · 거래량 180~228). 가로줄 4개 #F1F2F4.
 * 누른 채 0.22초 또는 옆으로 끌면 그날 시세 (점선 십자 · 점) — 그동안 부모 스크롤을 잠금. 세로로 먼저 움직이면 스크롤.
 */
export function CandleChart({ candles, width, visible, onHover, onLock }: { candles: Candle[]; width: number; visible: boolean; onHover: (i: number | null) => void; onLock: (on: boolean) => void }) {
  const n = candles.length;
  const run = visible && width > 0;
  const total = 420 + n * 14;
  const t = useProgress(run, total, candles);
  const tMs = t * total;
  const [hover, setHover] = useState<number | null>(null);
  const sw = width / Math.max(1, n);
  const bw = Math.max(2, Math.min(12, sw * 0.6));
  const g = useMemo(() => {
    const hi = Math.max(...candles.map((d) => d.high));
    const lo = Math.min(...candles.map((d) => d.low));
    const pad = (hi - lo) * 0.08;
    const y = (v: number) => 8 + (H - 8) * (1 - (v - (lo - pad)) / (hi + pad - (lo - pad)));
    const vmax = Math.max(...candles.map((d) => d.volume));
    return { y, vmax };
  }, [candles]);
  /* 손가락 처리 (원본 #096): 처리기끼리 나눠 쓰는 값은 이 안에만 (SwipeRow 와 같은 방식). 차트 왼쪽 = pageX - locationX */
  const h = useMemo(() => {
    const s = { px: 0, y0: 0, timer: undefined as ReturnType<typeof setTimeout> | undefined, on: false, moved: false };
    const show = (pageX: number) => {
      const i = Math.max(0, Math.min(n - 1, Math.floor((pageX - s.px) / sw)));
      setHover(i);
      onHover(i);
    };
    const end = () => {
      clearTimeout(s.timer);
      if (s.on) onLock(false);
      s.on = false;
      setHover(null);
      onHover(null);
    };
    const pan = PanResponder.create({
      /* 옆으로 먼저 움직이면 차트가 가져감 (세로면 스크롤) */
      onMoveShouldSetPanResponder: (_, gs) => Math.abs(gs.dx) > 6 && Math.abs(gs.dx) > Math.abs(gs.dy) * 1.2,
      onPanResponderGrant: () => {
        clearTimeout(s.timer);
        if (!s.on) {
          s.on = true;
          onLock(true);
        }
      },
      onPanResponderMove: (e) => show(e.nativeEvent.pageX),
      onPanResponderTerminationRequest: () => false,
      onPanResponderRelease: end,
      onPanResponderTerminate: end,
    });
    const touchStart = (e: GestureResponderEvent) => {
      const { pageX, pageY, locationX } = e.nativeEvent;
      s.px = pageX - locationX;
      s.y0 = pageY;
      s.moved = false;
      clearTimeout(s.timer);
      /* 누른 채 0.22초 → 그 자리 시세 */
      s.timer = setTimeout(() => {
        if (s.moved) return;
        s.on = true;
        onLock(true);
        show(pageX);
      }, 220);
    };
    const touchMove = (e: GestureResponderEvent) => {
      const { pageX, pageY } = e.nativeEvent;
      if (!s.on && Math.abs(pageY - s.y0) > 8) {
        s.moved = true;
        clearTimeout(s.timer);
      }
      if (s.on) show(pageX);
    };
    return { pan, touchStart, touchMove, end };
  }, [n, sw, onHover, onLock]);
  const d = hover != null ? candles[hover] : null;
  const hx = hover != null ? sw * hover + sw / 2 : 0;
  return (
    <View {...h.pan.panHandlers} onTouchStart={h.touchStart} onTouchMove={h.touchMove} onTouchEnd={h.end} onTouchCancel={h.end} style={{ width, height: CANDLE_H }}>
      {width ? (
        <Svg width={width} height={CANDLE_H}>
          {[0, 1, 2, 3].map((i) => (
            <Line key={i} x1={0} x2={width} y1={10 + (i * (H - 10)) / 3} y2={10 + (i * (H - 10)) / 3} stroke="#F1F2F4" />
          ))}
          {candles.map((c, i) => {
            const x = sw * i + sw / 2;
            const up = c.close >= c.open;
            const col = up ? '#E5484D' : '#2F6BDB';
            /* 원본 .cdl: 가운데 기준 세로로 자람 .42s spring · 차례 14ms / .vb: 아래 기준 .4s */
            const s = springE(seg(tMs, i * 14, 420));
            const sv = easeE(seg(tMs, i * 14, 400));
            const top = g.y(Math.max(c.open, c.close));
            const bh = Math.max(1.5, Math.abs(g.y(c.open) - g.y(c.close)));
            const mid = (g.y(c.high) + g.y(c.low)) / 2;
            const vy = VT + VH * (1 - c.volume / g.vmax);
            const vh = (VT + VH - vy) * sv;
            return (
              <G key={c.date} opacity={clamp01(seg(tMs, i * 14, 120))}>
                <Line x1={x} x2={x} y1={mid + (g.y(c.high) - mid) * s} y2={mid + (g.y(c.low) - mid) * s} stroke={col} strokeWidth={1.2} />
                <Rect x={x - bw / 2} y={mid + (top - mid) * s} width={bw} height={bh * s} fill={col} rx={1} />
                <Rect x={x - bw / 2} y={VT + VH - vh} width={bw} height={vh} fill={up ? '#F3A9AC' : '#A8C1F3'} rx={1} />
              </G>
            );
          })}
          {d ? (
            <G>
              <Line x1={hx} x2={hx} y1={0} y2={VT + VH} stroke="#16171A" strokeDasharray="3 3" />
              <Line x1={0} x2={width} y1={g.y(d.close)} y2={g.y(d.close)} stroke="#16171A" strokeDasharray="3 3" />
              <Circle cx={hx} cy={g.y(d.close)} r={4.5} fill="#FFFFFF" stroke="#16171A" strokeWidth={2} />
            </G>
          ) : null}
        </Svg>
      ) : null}
    </View>
  );
}

/* ---------- 성장성 (원본 drawGrow: 막대 + 전년 동기 대비 꺾은선) ---------- */
export const GROW_H = 190;
export function GrowthChart({ all, k, color, width, visible, sel, picked, onPick, emptyText }: { all: CompanyQuarter[]; k: FinKey; color: string; width: number; visible: boolean; sel: number; picked: boolean; onPick: (i: number, how: 'tap' | 'drag') => void; emptyText: string }) {
  const shown = all.slice(-8);
  const off = all.length - shown.length;
  const v = shown.map((q) => q[k]);
  const n = v.length;
  const top = 46;
  const base = 160;
  const nn = v.filter((x): x is number => x != null);
  const mx = (nn.length ? Math.max(...nn) : 1) * 1.05;
  const sw = width / n;
  const bw = Math.min(34, sw * 0.62);
  const total = n * 45 + 250 + n * 60 + 400;
  const t = useProgress(visible && width > 0, total, `${k}`);
  const tMs = t * total;
  const pts = v.map((_, i) => {
    const Y = yoyAt(all, k, off + i);
    return Y.t === 'pct' ? ([sw * i + sw / 2, Y.v] as const) : null;
  });
  const ok = pts.filter((p): p is readonly [number, number] => !!p);
  const ys = ok.map((p) => p[1]);
  const a = Math.min(...ys);
  const b = Math.max(...ys);
  const yy = (r: number) => (b === a ? 24 : 34 - 22 * ((r - a) / (b - a)));
  /* 흑자·적자 전환처럼 % 가 안 되는 칸은 점을 빼고 선을 끊음 (앞 칸이 비면 새로 시작 M) */
  const d = pts.map((p, i) => (p ? `${i > 0 && pts[i - 1] ? 'L' : 'M'}${p[0]} ${yy(p[1])}` : '')).join(' ');
  const lineT = easeE(seg(tMs, n * 45 + 150, 900));
  /* 칸을 누르거나 옆으로 훑기 ([11.11] 막대 칸 어디를 눌러도 됨 · 누른 채 옆으로 훑으면 따라감) */
  const h = useMemo(() => {
    const s = { px: 0, x0: 0, moved: false };
    const idx = (pageX: number) => Math.max(0, Math.min(n - 1, Math.floor((pageX - s.px) / sw)));
    const pan = PanResponder.create({
      onMoveShouldSetPanResponder: (_, gs) => Math.abs(gs.dx) > 6 && Math.abs(gs.dx) > Math.abs(gs.dy) * 1.2,
      onPanResponderMove: (e) => {
        s.moved = true;
        onPick(idx(e.nativeEvent.pageX), 'drag');
      },
      onPanResponderTerminationRequest: () => false,
    });
    const touchStart = (e: GestureResponderEvent) => {
      s.px = e.nativeEvent.pageX - e.nativeEvent.locationX;
      s.x0 = e.nativeEvent.pageX;
      s.moved = false;
    };
    const touchEnd = (e: GestureResponderEvent) => {
      if (!s.moved && Math.abs(e.nativeEvent.pageX - s.x0) < 8) onPick(idx(e.nativeEvent.pageX), 'tap');
    };
    return { pan, touchStart, touchEnd };
  }, [n, sw, onPick]);
  return (
    <View {...h.pan.panHandlers} onTouchStart={h.touchStart} onTouchEnd={h.touchEnd} style={{ width, height: GROW_H }}>
      {width ? (
        <Svg width={width} height={GROW_H}>
          {!nn.length ? (
            <SvgText x={width / 2} y={(top + base) / 2} fontSize={13} fill="#9A9EA7" textAnchor="middle">
              {emptyText}
            </SvgText>
          ) : null}
          {v.map((x, i) => {
            const h = x == null ? 0 : (base - top) * (x / mx);
            const s = springE(seg(tMs, i * 45, 500));
            return <Rect key={i} x={sw * i + (sw - bw) / 2} y={base - h * s} width={bw} height={Math.max(0, h * s)} rx={3} fill={color} opacity={picked && i !== sel ? 0.35 : 1} />;
          })}
          {ok.length ? <Path d={d} stroke="#33404B" strokeWidth={1.4} fill="none" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="400" strokeDashoffset={400 * (1 - lineT)} /> : null}
          {ok.map((p, j) => {
            const s = springE(seg(tMs, n * 45 + 250 + j * 60, 350));
            return <Circle key={j} cx={p[0]} cy={yy(p[1])} r={3.6 * s} fill="#FFFFFF" stroke="#33404B" strokeWidth={1.4} />;
          })}
          {shown.map((q, i) => (
            <SvgText key={q.q} x={sw * i + sw / 2} y={base + 18} fontSize={11} fill="#9A9EA7" textAnchor="middle">
              {q.q}
            </SvgText>
          ))}
        </Svg>
      ) : null}
    </View>
  );
}

/* ---------- 수익성 (원본 drawProf: 60·40·20% 눈금 · 선이 그려짐 · 범례로 켜고 끄기) ---------- */
export const PROF_H = 170;
export function ProfitChart({ series, labels, width, visible }: { series: { name: string; color: string; values: (number | null)[]; hidden: boolean }[]; labels: string[]; width: number; visible: boolean }) {
  const top = 14;
  const base = 140;
  const n = labels.length;
  const sw = width / n;
  const y = (x: number) => base - (base - top) * (x / 60);
  const total = series.length * 180 + 300 + n * 40 + 900;
  const t = useProgress(visible && width > 0, total);
  const tMs = t * total;
  return (
    <View style={{ width, height: PROF_H }}>
      {width ? (
        <Svg width={width} height={PROF_H}>
          {[60, 40, 20].map((v) => (
            <G key={v}>
              <Line x1={0} x2={width} y1={y(v)} y2={y(v)} stroke="#F1F2F4" />
              <SvgText x={0} y={y(v) - 3} fontSize={11} fill="#9A9EA7">{`${v}%`}</SvgText>
            </G>
          ))}
          {series.map((p, k) => {
            if (p.values.every((x) => x == null)) return null;
            const vals = p.values.map((x) => x ?? 0);
            const d = vals.map((x, i) => `${i ? 'L' : 'M'}${sw * i + sw / 2} ${y(x)}`).join(' ');
            const lt = easeE(seg(tMs, k * 180, 900));
            return (
              <G key={p.name} opacity={p.hidden ? 0 : 1}>
                <Path d={d} stroke={p.color} strokeWidth={1.8} fill="none" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="520" strokeDashoffset={520 * (1 - lt)} />
                {vals.map((x, i) => (
                  <Circle key={i} cx={sw * i + sw / 2} cy={y(x)} r={2.8 * springE(seg(tMs, k * 180 + 300 + i * 40, 350))} fill={p.color} />
                ))}
              </G>
            );
          })}
          {labels.map((l, i) => (
            <SvgText key={l} x={sw * i + sw / 2} y={base + 20} fontSize={11} fill="#9A9EA7" textAnchor="middle">
              {l}
            </SvgText>
          ))}
        </Svg>
      ) : null}
    </View>
  );
}

/* ---------- 건전성 레이더 (원본 drawRadar: 가운데 (가로 가운데, 118) · 반지름 82 · 고리 1 · .66 · .33 · 가운데서 퍼짐 .7s spring) ---------- */
export const RADAR_H = 230;
/** missing[i]가 true면 값이 없는 지표: 점은 가운데(점 표시 없음), 라벨은 흐리게 */
export function Radar({ labels, scores, missing, width, visible }: { labels: string[]; scores: number[]; missing?: boolean[]; width: number; visible: boolean }) {
  const t = useProgress(visible && width > 0, 900);
  const sc = springE(seg(t * 900, 200, 700));
  const cx = width / 2;
  const cy = 118;
  const R = 82;
  const n = labels.length;
  const pt = (i: number, r: number) => [cx + r * Math.sin((Math.PI * 2 * i) / n), cy - r * Math.cos((Math.PI * 2 * i) / n)] as const;
  const ps = scores.map((s, i) => pt(i, R * s * sc));
  return (
    <View style={{ width, height: RADAR_H }}>
      {width ? (
        <Svg width={width} height={RADAR_H}>
          {[1, 0.66, 0.33].map((k) => (
            <Polygon key={k} points={labels.map((_, i) => pt(i, R * k).join(',')).join(' ')} fill="none" stroke="#E6E3F3" />
          ))}
          {labels.map((l, i) => {
            const p = pt(i, R);
            const q = pt(i, R + 20);
            return (
              <G key={l}>
                <Line x1={cx} y1={cy} x2={p[0]} y2={p[1]} stroke="#EEECF6" />
                <SvgText x={q[0]} y={q[1] + 4} fontSize={11} fill={missing?.[i] ? '#B0B8C1' : '#575B63'} textAnchor="middle">
                  {l}
                </SvgText>
              </G>
            );
          })}
          <Polygon points={ps.map((p) => p.join(',')).join(' ')} fill="rgba(133,105,227,0.18)" stroke="#7046F5" strokeWidth={2} />
          {ps.map((p, i) => (missing?.[i] ? null : <Circle key={i} cx={p[0]} cy={p[1]} r={3.5} fill="#7046F5" />))}
        </Svg>
      ) : null}
    </View>
  );
}
