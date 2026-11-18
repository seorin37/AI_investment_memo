/**
 * 선형 아이콘 세트 (24×24, stroke 기반) — react-native-svg 로 웹/네이티브 동일 렌더.
 */
import React from 'react';
import Svg, { Circle, Ellipse, Path, Polygon, Rect } from 'react-native-svg';
import { colors } from '@/theme/tokens';

type Shape =
  | { p: string; fill?: boolean }
  | { c: [number, number, number]; fill?: boolean }
  | { r: [number, number, number, number, number?] }
  | { e: [number, number, number, number] }
  | { poly: string };

const ICONS = {
  home: [{ p: 'M3 10.5 12 3l9 7.5' }, { p: 'M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5' }],
  refresh: [{ p: 'M3 12a9 9 0 0 1 15.5-6.2L21 8' }, { p: 'M21 3v5h-5' }, { p: 'M21 12a9 9 0 0 1-15.5 6.2L3 16' }, { p: 'M3 21v-5h5' }],
  fileText: [{ p: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z' }, { p: 'M14 3v5h5' }, { p: 'M9 13h6' }, { p: 'M9 17h6' }, { p: 'M9 9h1' }],
  file: [{ p: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z' }, { p: 'M14 3v5h5' }],
  briefcase: [{ r: [3, 7, 18, 13, 2] }, { p: 'M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2' }, { p: 'M8.5 16v-2.5' }, { p: 'M12 16v-4' }, { p: 'M15.5 16v-3' }],
  trash: [{ p: 'M3 6h18' }, { p: 'M8 6V4h8v2' }, { p: 'M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6' }, { p: 'M10 11v6' }, { p: 'M14 11v6' }],
  settings: [
    {
      p: 'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z',
    },
    { c: [12, 12, 3] },
  ],
  search: [{ c: [11, 11, 7] }, { p: 'M21 21l-4.3-4.3' }],
  plus: [{ p: 'M12 5v14' }, { p: 'M5 12h14' }],
  minus: [{ p: 'M5 12h14' }],
  chevronDown: [{ p: 'M6 9l6 6 6-6' }],
  chevronUp: [{ p: 'M18 15l-6-6-6 6' }],
  chevronLeft: [{ p: 'M15 18l-6-6 6-6' }],
  chevronRight: [{ p: 'M9 18l6-6-6-6' }],
  arrowRight: [{ p: 'M5 12h14' }, { p: 'M12 5l7 7-7 7' }],
  arrowLeft: [{ p: 'M19 12H5' }, { p: 'M12 19l-7-7 7-7' }],
  x: [{ p: 'M18 6 6 18' }, { p: 'M6 6l12 12' }],
  check: [{ p: 'M20 6 9 17l-5-5' }],
  pin: [
    { p: 'M12 17v5' },
    { p: 'M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z' },
  ],
  link: [
    { p: 'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71' },
    { p: 'M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71' },
  ],
  external: [{ p: 'M7 17 17 7' }, { p: 'M7 7h10v10' }],
  pencil: [{ p: 'M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z' }, { p: 'M15 5l4 4' }],
  edit: [{ p: 'M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7' }, { p: 'M18.4 2.6a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4Z' }],
  bell: [{ p: 'M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9' }, { p: 'M10.3 21a1.94 1.94 0 0 0 3.4 0' }],
  bellRing: [{ p: 'M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9' }, { p: 'M10.3 21a1.94 1.94 0 0 0 3.4 0' }, { p: 'M4 2C2.8 3.7 2 5.7 2 8' }, { p: 'M22 8c0-2.3-.8-4.3-2-6' }],
  sparkles: [
    {
      p: 'M9.94 15.5A2 2 0 0 0 8.5 14.06l-6.13-1.58a.5.5 0 0 1 0-.96L8.5 9.94A2 2 0 0 0 9.94 8.5l1.58-6.13a.5.5 0 0 1 .96 0L14.06 8.5A2 2 0 0 0 15.5 9.94l6.13 1.58a.5.5 0 0 1 0 .96L15.5 14.06a2 2 0 0 0-1.44 1.44l-1.58 6.13a.5.5 0 0 1-.96 0z',
    },
    { p: 'M20 3v4' },
    { p: 'M22 5h-4' },
  ],
  panelLeft: [{ r: [3, 3, 18, 18, 2] }, { p: 'M9 3v18' }],
  logout: [{ p: 'M10 17l5-5-5-5' }, { p: 'M15 12H3' }, { p: 'M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4' }],
  user: [{ c: [12, 8, 4] }, { p: 'M4 21a8 8 0 0 1 16 0' }],
  monitor: [{ r: [2, 3, 20, 14, 2] }, { p: 'M8 21h8' }, { p: 'M12 17v4' }],
  barChart: [{ p: 'M6 20v-6' }, { p: 'M12 20V8' }, { p: 'M18 20V4' }],
  plug: [{ p: 'M12 22v-5' }, { p: 'M9 8V2' }, { p: 'M15 8V2' }, { p: 'M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z' }],
  database: [{ e: [12, 5, 9, 3] }, { p: 'M3 5v14a9 3 0 0 0 18 0V5' }, { p: 'M3 12a9 3 0 0 0 18 0' }],
  info: [{ c: [12, 12, 10] }, { p: 'M12 16v-4' }, { p: 'M12 8h.01' }],
  help: [{ c: [12, 12, 10] }, { p: 'M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3' }, { p: 'M12 17h.01' }],
  helpSquare: [{ p: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z' }, { p: 'M9.8 8.2a2.3 2.3 0 0 1 4.4 1c0 1.5-2.2 2.2-2.2 2.2' }, { p: 'M12 14h.01' }],
  grip: [
    { c: [9, 5, 1], fill: true }, { c: [9, 12, 1], fill: true }, { c: [9, 19, 1], fill: true },
    { c: [15, 5, 1], fill: true }, { c: [15, 12, 1], fill: true }, { c: [15, 19, 1], fill: true },
  ],
  resize: [{ p: 'M15 3h6v6' }, { p: 'M9 21H3v-6' }, { p: 'M21 3l-7 7' }, { p: 'M3 21l7-7' }],
  calendar: [{ r: [3, 4, 18, 18, 2] }, { p: 'M16 2v4' }, { p: 'M8 2v4' }, { p: 'M3 10h18' }],
  newspaper: [
    { p: 'M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2' },
    { p: 'M18 14h-8' },
    { p: 'M15 18h-5' },
    { p: 'M10 6h8v4h-8V6Z' },
  ],
  trendingUp: [{ p: 'M22 7 13.5 15.5 8.5 10.5 2 17' }, { p: 'M16 7h6v6' }],
  candle: [{ p: 'M9 5v4' }, { r: [7, 9, 4, 6, 1] }, { p: 'M9 15v2' }, { r: [15, 7, 4, 10, 1] }, { p: 'M17 4v3' }, { p: 'M17 17v3' }],
  paperclip: [{ p: 'M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48' }],
  table: [{ r: [3, 3, 18, 18, 2] }, { p: 'M3 9h18' }, { p: 'M3 15h18' }, { p: 'M12 3v18' }],
  listChecks: [{ p: 'M3 17l2 2 4-4' }, { p: 'M3 7l2 2 4-4' }, { p: 'M13 6h8' }, { p: 'M13 12h8' }, { p: 'M13 18h8' }],
  markup: [{ c: [12, 12, 9] }, { p: 'M8.6 16 12 7.5l3.4 8.5' }, { p: 'M9.8 13h4.4' }],
  undo: [{ p: 'M9 14 4 9l5-5' }, { p: 'M4 9h10.5a5.5 5.5 0 0 1 0 11H11' }],
  star: [{ poly: '12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26' }],
  grid: [{ r: [3, 3, 7, 7, 1] }, { r: [14, 3, 7, 7, 1] }, { r: [14, 14, 7, 7, 1] }, { r: [3, 14, 7, 7, 1] }],
  sliders: [{ p: 'M21 4h-7' }, { p: 'M10 4H3' }, { p: 'M21 12h-9' }, { p: 'M8 12H3' }, { p: 'M21 20h-5' }, { p: 'M12 20H3' }, { p: 'M14 2v4' }, { p: 'M8 10v4' }, { p: 'M16 18v4' }],
  menu: [{ p: 'M4 6h16' }, { p: 'M4 12h16' }, { p: 'M4 18h16' }],
  more: [{ c: [5, 12, 1], fill: true }, { c: [12, 12, 1], fill: true }, { c: [19, 12, 1], fill: true }],
  filePlus: [{ p: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z' }, { p: 'M14 3v5h5' }, { p: 'M12 12v6' }, { p: 'M9 15h6' }],
  history: [{ p: 'M3 12a9 9 0 1 0 3-6.7L3 8' }, { p: 'M3 3v5h5' }, { p: 'M12 7v5l4 2' }],
  scale: [{ p: 'M16 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z' }, { p: 'M2 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z' }, { p: 'M7 21h10' }, { p: 'M12 3v18' }, { p: 'M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2' }],
  flag: [{ p: 'M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z' }, { p: 'M4 22v-7' }],
  copy: [{ r: [8, 8, 14, 14, 2] }, { p: 'M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2' }],
  download: [{ p: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' }, { p: 'M7 10l5 5 5-5' }, { p: 'M12 15V3' }],
  camera: [{ p: 'M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z' }, { c: [12, 13, 3] }],
  bold: [{ p: 'M6 12h9a4 4 0 0 1 0 8H6V4h8a4 4 0 0 1 0 8' }],
} satisfies Record<string, Shape[]>;

export type IconName = keyof typeof ICONS;

interface Props {
  name: IconName;
  size?: number;
  color?: string;
  strokeWidth?: number;
  fill?: string;
}

export function Icon({ name, size = 20, color = colors.text, strokeWidth = 1.8, fill = 'none' }: Props) {
  const shapes = ICONS[name] as Shape[];
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
      {shapes.map((s, i) => {
        const common = { stroke: color, strokeWidth, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
        if ('p' in s) return <Path key={i} d={s.p} {...common} fill={s.fill ? color : fill} />;
        if ('c' in s) return <Circle key={i} cx={s.c[0]} cy={s.c[1]} r={s.c[2]} {...common} fill={s.fill ? color : fill} />;
        if ('r' in s) return <Rect key={i} x={s.r[0]} y={s.r[1]} width={s.r[2]} height={s.r[3]} rx={s.r[4] ?? 0} {...common} fill={fill} />;
        if ('e' in s) return <Ellipse key={i} cx={s.e[0]} cy={s.e[1]} rx={s.e[2]} ry={s.e[3]} {...common} fill={fill} />;
        return <Polygon key={i} points={s.poly} {...common} fill={fill} />;
      })}
    </Svg>
  );
}

// ─── 브랜드 로고 (로그인 버튼) ─────────────────────────────────
export function KakaoLogo({ size = 22 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path
        d="M12 3C6.48 3 2 6.58 2 11c0 2.86 1.88 5.37 4.7 6.78l-.96 3.53c-.08.3.26.54.52.37l4.2-2.78c.5.06 1.02.1 1.54.1 5.52 0 10-3.58 10-8S17.52 3 12 3z"
        fill="#191919"
      />
    </Svg>
  );
}

export function NaverLogo({ size = 18 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path d="M16.27 12.84 7.38 0H0v24h7.73V11.16L16.62 24H24V0h-7.73z" fill="#FFFFFF" />
    </Svg>
  );
}

export function GoogleLogo({ size = 20 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 48 48">
      <Path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <Path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <Path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <Path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </Svg>
  );
}

/** 국기 원형 아이콘 (시장 지수 카드) */
export function FlagDot({ flag, size = 12 }: { flag: 'kr' | 'us'; size?: number }) {
  if (flag === 'kr')
    return (
      <Svg width={size} height={size} viewBox="0 0 12 12">
        <Circle cx={6} cy={6} r={5.5} fill="#FFFFFF" stroke="#D9DEE7" strokeWidth={0.6} />
        <Path d="M3.6 6a2.4 2.4 0 0 1 4.8 0z" fill="#CD2E3A" />
        <Path d="M3.6 6a2.4 2.4 0 0 0 4.8 0z" fill="#0047A0" />
      </Svg>
    );
  return (
    <Svg width={size} height={size} viewBox="0 0 12 12">
      <Circle cx={6} cy={6} r={5.5} fill="#FFFFFF" stroke="#D9DEE7" strokeWidth={0.6} />
      <Path d="M1.2 4h9.6M1 6h10M1.2 8h9.6" stroke="#B22234" strokeWidth={1} />
      <Path d="M1.5 2.6A5.5 5.5 0 0 1 6 0.5V6H0.6A5.5 5.5 0 0 1 1.5 2.6z" fill="#3C3B6E" />
    </Svg>
  );
}
