import React, { type ComponentType } from 'react';
import type { StyleProp, ViewStyle } from 'react-native';
import Svg, { Circle, ClipPath, Defs, Ellipse, G, Line, LinearGradient, Mask, Path, Polygon, Polyline, RadialGradient, Rect, Stop } from 'react-native-svg';
import type { IconAttrs, IconDef, IconNode } from './iconTypes';

const DEFAULT_INK = '#16171A';
/* 웹에서 <svg> 는 RN View 가 아니라 flex-shrink 1 을 받아, 옆 칸(flex 1)에 밀려 폭이 0 이 될 수 있음 */
const NO_SHRINK = { flexShrink: 0 } as const;
const PAINT_KEYS = new Set(['stroke', 'fill', 'stopColor', 'color']);

type AnySvg = ComponentType<Record<string, unknown>>;
const TAGS: Record<string, AnySvg> = {
  path: Path as unknown as AnySvg,
  circle: Circle as unknown as AnySvg,
  rect: Rect as unknown as AnySvg,
  line: Line as unknown as AnySvg,
  polyline: Polyline as unknown as AnySvg,
  polygon: Polygon as unknown as AnySvg,
  ellipse: Ellipse as unknown as AnySvg,
  g: G as unknown as AnySvg,
  defs: Defs as unknown as AnySvg,
  linearGradient: LinearGradient as unknown as AnySvg,
  radialGradient: RadialGradient as unknown as AnySvg,
  stop: Stop as unknown as AnySvg,
  clipPath: ClipPath as unknown as AnySvg,
  mask: Mask as unknown as AnySvg,
};

function paint(v: string | number, main: string, color: string | undefined): string | number {
  if (typeof v !== 'string') return v;
  if (v === 'currentColor') return color ?? (main === 'currentColor' ? DEFAULT_INK : main);
  if (color && v.toLowerCase() === main.toLowerCase()) return color;
  return v;
}

function draw(nodes: readonly IconNode[], main: string, color: string | undefined, key: string): React.ReactNode[] {
  return nodes.map((n, i) => {
    const [tag, attrs, kids] = n;
    const C = TAGS[tag];
    if (!C) return null;
    const props: IconAttrs = {};
    for (const [k, v] of Object.entries(attrs)) props[k] = PAINT_KEYS.has(k) ? paint(v, main, color) : v;
    return (
      <C key={`${key}${i}`} {...props}>
        {kids ? draw(kids, main, color, `${key}${i}.`) : null}
      </C>
    );
  });
}

export interface SvgIconProps {
  /** 가로 크기. 세로는 원본 비율대로 (없으면 원본 width) */
  size?: number;
  /** 세로를 따로 정할 때 */
  height?: number;
  /** 원본 주색(과 currentColor)을 바꿀 색 */
  color?: string;
  style?: StyleProp<ViewStyle>;
}

/** 원본 SVG 하나를 그대로 그림 (원본 크기·선 굵기·색 유지) */
export function SvgIcon({ def, size, height, color, style }: SvgIconProps & { def: IconDef }) {
  const w = size ?? def.w;
  const h = height ?? (size ? (size * def.h) / def.w : def.h);
  return (
    <Svg width={w} height={h} viewBox={def.vb} fill="none" style={[NO_SHRINK, style]}>
      {draw(def.nodes, def.main, color, '')}
    </Svg>
  );
}
