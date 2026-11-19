import React, { useId } from 'react';
import { View } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Path, Stop } from 'react-native-svg';

export interface SparklineProps {
  /** 종가 (오래된 → 최근) */
  data: number[];
  color: string;
  /**
   * appCard: 원본 memo.html 종목 카드 (120×44 · 좌 2 · 우 6 · 위아래 6 · 면 .22 · 선 1.6 · 끝점 r3.2 흰 바탕 + 선 1.6 · 아래 점선 #C9CDD4 2 3)
   * webMini: 원본 board.tsx MiniChart (116×64 · 선 106×52.9 위 11.1 · 면 .22 · 선 2 · 아래 점선 #8E8A97 .5 · 끝점 원 2개)
   * web: 원본 kit.tsx Spark (폭 100% · 위아래 4 · 면 .2 · 선 1.7 · 끝점 r3.5 흰 테두리 2)
   */
  variant: 'appCard' | 'webMini' | 'web';
  width?: number;
  height?: number;
}

function pts(data: number[], x0: number, x1: number, y0: number, y1: number): [number, number][] {
  const mn = Math.min(...data);
  const mx = Math.max(...data);
  return data.map((v, i) => [x0 + (i / Math.max(1, data.length - 1)) * (x1 - x0), y1 - ((v - mn) / (mx - mn || 1)) * (y1 - y0)]);
}
const path = (p: [number, number][]) => p.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');

/** 작은 주가 선 (면 그라데이션 · 끝점) */
export function Sparkline({ data, color, variant, width, height }: SparklineProps) {
  const id = `sp${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  if (data.length < 2) return null;
  if (variant === 'appCard') {
    const w = width ?? 120;
    const h = height ?? 44;
    const p = pts(data, 2, w - 6, 6, h - 6);
    const d = path(p);
    const [ex, ey] = p[p.length - 1];
    return (
      <Svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
        <Defs>
          <LinearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor={color} stopOpacity={0.22} />
            <Stop offset="1" stopColor={color} stopOpacity={0} />
          </LinearGradient>
        </Defs>
        <Path d={`${d} L${ex.toFixed(1)} ${h} L2 ${h}Z`} fill={`url(#${id})`} />
        <Path d={d} fill="none" stroke={color} strokeWidth={1.6} />
        <Circle cx={ex} cy={ey} r={3.2} fill="#FFFFFF" stroke={color} strokeWidth={1.6} />
        <Path d={`M2 ${h - 4}H${w - 2}`} stroke="#C9CDD4" strokeDasharray="2 3" />
      </Svg>
    );
  }
  if (variant === 'webMini') {
    const p = pts(data, 0, 106, 0, 42.8);
    const d = path(p);
    const ey = p[p.length - 1][1];
    return (
      <View style={{ width: 116, height: 64 }}>
        <Svg width={116} height={1} viewBox="0 0 116 1" style={{ position: 'absolute', left: 0, top: 53.9 }}>
          <Path d="M0 0.5H116" stroke="#8E8A97" strokeOpacity={0.5} strokeDasharray="2 4" />
        </Svg>
        <Svg width={106} height={52.9} viewBox="0 0 106 52.9" style={{ position: 'absolute', left: 0, top: 11.1 }}>
          <Defs>
            <LinearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={color} stopOpacity={0.22} />
              <Stop offset="1" stopColor={color} stopOpacity={0} />
            </LinearGradient>
          </Defs>
          <Path d={`${d} V52.9 H0 Z`} fill={`url(#${id})`} />
          <Path d={d} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        </Svg>
        <View style={{ position: 'absolute', left: 98, top: 11.1 + ey - 8, width: 16, height: 16, borderRadius: 8, borderWidth: 1.5, borderColor: color, opacity: 0.35 }} />
        <View style={{ position: 'absolute', left: 102, top: 11.1 + ey - 4, width: 8, height: 8, borderRadius: 4, borderWidth: 2, borderColor: '#FFFFFF', backgroundColor: color }} />
      </View>
    );
  }
  const w = width ?? 160;
  const h = height ?? 44;
  const p = pts(data, 0, w, 4, h - 4);
  const d = path(p);
  const [ex, ey] = p[p.length - 1];
  return (
    <Svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <Defs>
        <LinearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={color} stopOpacity={0.2} />
          <Stop offset="1" stopColor={color} stopOpacity={0} />
        </LinearGradient>
      </Defs>
      <Path d={`${d} L${w} ${h} L0 ${h}Z`} fill={`url(#${id})`} />
      <Path d={d} fill="none" stroke={color} strokeWidth={1.7} strokeLinejoin="round" />
      <Circle cx={ex} cy={ey} r={3.5} fill={color} stroke="#FFFFFF" strokeWidth={2} />
    </Svg>
  );
}
