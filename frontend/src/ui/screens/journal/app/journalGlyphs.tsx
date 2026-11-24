import React from 'react';
import Svg, { Circle, Path, Rect } from 'react-native-svg';

/* 원본 journal.html 아이콘 (24 기준 · 선 굵기 원본 그대로) */
const line = (c: string, w: number) => ({ fill: 'none', stroke: c, strokeWidth: w, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const });

export function JSearch({ color, size = 18 }: { color: string; size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line(color, 2.2)}>
      <Circle cx={11} cy={11} r={7} />
      <Path d="M20 20l-4-4" />
    </Svg>
  );
}

export function JMic({ color }: { color: string }) {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24" {...line(color, 2)}>
      <Rect x={9} y={3} width={6} height={11} rx={3} />
      <Path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" />
    </Svg>
  );
}

export function JCompose({ color }: { color: string }) {
  return (
    <Svg width={24} height={24} viewBox="0 0 24 24" {...line(color, 2)}>
      <Path d="M12 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-6" />
      <Path d="M17.5 3.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4z" />
    </Svg>
  );
}

export function JChevron({ color }: { color: string }) {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24" {...line(color, 2.4)}>
      <Path d="M6 9l6 6 6-6" />
    </Svg>
  );
}

/** 고르기 동그라미 안 체크 (원본 CHK 13) */
export function JCheck() {
  return (
    <Svg width={13} height={13} viewBox="0 0 14 14" fill="none">
      <Path d="M3 7.3l2.6 2.6L11 4.4" stroke="#FFFFFF" strokeWidth={2.3} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

export function JClose() {
  return (
    <Svg width={22} height={22} viewBox="0 0 24 24" {...line('#16171A', 2.2)}>
      <Path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  );
}

/** 아래 고르기 막대 (원본 .abar 22 · 선 2) */
export function JBarIcon({ k, color }: { k: 'pin' | 'share' | 'del'; color: string }) {
  return (
    <Svg width={22} height={22} viewBox="0 0 24 24" {...line(color, 2)}>
      {k === 'pin' ? <Path d="M9 4h6l-1 6 4 3v2H6v-2l4-3zM12 15v6" /> : k === 'share' ? <Path d="M12 3v12M7.5 7.5 12 3l4.5 4.5M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7" /> : <Path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />}
    </Svg>
  );
}

/** 빈 목록 그림 (원본 .empty .ill 44 · #7356D6 1.7) */
export function JEmptyDoc() {
  return (
    <Svg width={44} height={44} viewBox="0 0 24 24" {...line('#7356D6', 1.7)}>
      <Path d="M6 3h8l4 4v14H6z" />
      <Path d="M9 12h6M9 16h4" />
    </Svg>
  );
}

/** 검색 결과 없음 그림 (원본 34 · #7356D6 2) */
export function JNoHit() {
  return (
    <Svg width={34} height={34} viewBox="0 0 24 24" {...line('#7356D6', 2)}>
      <Circle cx={11} cy={11} r={7} />
      <Path d="M20 20l-4-4M8.5 11h5" />
    </Svg>
  );
}

export function JPlus() {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24" {...line('#FFFFFF', 2.4)}>
      <Path d="M12 5v14M5 12h14" />
    </Svg>
  );
}

/** 기록 화면 머리 · 도구 (원본 journal.html #nh · .ntb · .acc) */
export function JBack({ color }: { color: string }) {
  return (
    <Svg width={22} height={22} viewBox="0 0 24 24" {...line(color, 2.4)}>
      <Path d="M15 5l-7 7 7 7" />
    </Svg>
  );
}

export function JShare({ color }: { color: string }) {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24" {...line(color, 2)}>
      <Path d="M12 3v12M7.5 7.5 12 3l4.5 4.5M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7" />
    </Svg>
  );
}

export function JMore({ color }: { color: string }) {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24" fill={color}>
      <Circle cx={5.5} cy={12} r={2} />
      <Circle cx={12} cy={12} r={2} />
      <Circle cx={18.5} cy={12} r={2} />
    </Svg>
  );
}

export function JUndo({ color }: { color: string }) {
  return (
    <Svg width={22} height={22} viewBox="0 0 24 24" {...line(color, 2.1)}>
      <Path d="M9 14 4 9l5-5" />
      <Path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" />
    </Svg>
  );
}

export function JChecklist({ color, size = 24 }: { color: string; size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line(color, 2)}>
      <Circle cx={5} cy={7} r={1.8} />
      <Circle cx={5} cy={17} r={1.8} />
      <Path d="M10 7h10M10 17h10" />
    </Svg>
  );
}

export function JX({ size = 14, color = '#16171A' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line(color, 2.6)}>
      <Path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  );
}
