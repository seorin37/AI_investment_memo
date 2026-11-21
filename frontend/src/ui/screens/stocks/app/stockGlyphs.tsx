import React from 'react';
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import type { Hold } from '../MyStocks.types';

/** 원본 stock.html IC: 보유(가방 #3D73F0) · 관심(종 #B07800) — 17 · 선 2 */
export function HoldIcon({ h, size = 17 }: { h: Hold; size?: number }) {
  if (h === 'holding')
    return (
      <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#3D73F0" strokeWidth={2}>
        <Rect x={3} y={7} width={18} height={13} rx={2.5} />
        <Path d="M9 7V5h6v2M8 16v-3M12 16v-5M16 16v-2" />
      </Svg>
    );
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#B07800" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20a2 2 0 0 0 4 0" />
    </Svg>
  );
}
/** 묶음 아이콘 바탕 (원본 GBG) */
export const HOLD_BG: Record<Hold, string> = { holding: '#E6EEFF', watching: '#FFF3C4' };

/** 순서 손잡이 (14×18 · 점 r1.6 #9A9EA7) */
export function Grip() {
  return (
    <Svg width={14} height={18} viewBox="0 0 14 18" fill="#9A9EA7">
      {[4, 9, 14].map((y) => (
        <React.Fragment key={y}>
          <Circle cx={4} cy={y} r={1.6} />
          <Circle cx={10} cy={y} r={1.6} />
        </React.Fragment>
      ))}
    </Svg>
  );
}
/** 체크 (13 · 흰 선 2.3) */
export function Check13() {
  return (
    <Svg width={13} height={13} viewBox="0 0 14 14" fill="none">
      <Path d="M3 7.3l2.6 2.6L11 4.4" stroke="#FFFFFF" strokeWidth={2.3} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}
/** 빼기 휴지통 (22 · 빨강) */
export function TrashIcon() {
  return (
    <Svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="#E5484D" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
    </Svg>
  );
}
