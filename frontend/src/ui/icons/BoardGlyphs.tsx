/**
 * 메모 보드 작은 그림 — 원본 경로 그대로 (앱 memo.html PLUG · pinSvg · CKI · 고르기 막대 · 부채꼴 / 웹 board.tsx plugPaths · memox.tsx Dots · Pick)
 * 같은 모양이라도 쓰는 곳마다 선 굵기가 달라 생성 아이콘 대신 여기서 그림.
 */
import React from 'react';
import Svg, { Circle, Path, Rect } from 'react-native-svg';

const PLUG_BODY = 'M6.5 7H17.5V11C17.5 12.46 16.92 13.86 15.89 14.89C14.86 15.92 13.46 16.5 12 16.5C10.54 16.5 9.14 15.92 8.11 14.89C7.08 13.86 6.5 12.46 6.5 11V7Z';

/** 앱 플러그 (원본 PLUG(s): 24 viewBox · 선 2.4 · #16161C) */
export function AppPlug({ size = 12, color = '#16161C', stroke = 2.4 }: { size?: number; color?: string; stroke?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M9 3V7M15 3V7" stroke={color} strokeWidth={stroke} strokeLinecap="round" />
      <Path d={PLUG_BODY} fill={color} />
      <Path d="M12 16.5V21" stroke={color} strokeWidth={stroke} strokeLinecap="round" />
    </Svg>
  );
}

/** 웹 카드 플러그 (원본 plugPaths: 14 viewBox · 켜짐 채움 / 꺼짐 #16161C .45 선) */
export function WebPlug({ on }: { on: boolean }) {
  const body = 'M3.7915 4.08301H10.2082V6.41634C10.2082 7.26724 9.87015 8.0833 9.26847 8.68498C8.66679 9.28665 7.85074 9.62467 6.99984 9.62467C6.14893 9.62467 5.33288 9.28665 4.7312 8.68498C4.12952 8.0833 3.7915 7.26724 3.7915 6.41634V4.08301Z';
  return (
    <Svg width={14} height={14} viewBox="0 0 14 14" fill="none">
      {on ? (
        <>
          <Path d="M5.25 1.75V4.08333M8.75 1.75V4.08333" stroke="#000000" strokeWidth={1.2} strokeLinecap="round" />
          <Path d={body} fill="#16161C" />
          <Path d="M7 9.625V12.25" stroke="#000000" strokeWidth={1.2} strokeLinecap="round" />
        </>
      ) : (
        <>
          <Path d="M5.25 1.75V4.08333M8.75 1.75V4.08333" stroke="#16161C" strokeOpacity={0.45} strokeWidth={1.2} strokeLinecap="round" />
          <Path d={body} stroke="#16161C" strokeOpacity={0.45} strokeWidth={1.2} strokeLinejoin="round" />
          <Path d="M7 9.625V12.25" stroke="#16161C" strokeOpacity={0.45} strokeWidth={1.2} strokeLinecap="round" />
        </>
      )}
    </Svg>
  );
}

/** 앱 고정 핀 (원본 pinSvg: 선 2.2 / 고르기 막대 1.8) */
export function AppPin({ size = 14, color = 'currentColor', stroke = 2.2 }: { size?: number; color?: string; stroke?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M9 3h6l-1 6 4 4H6l4-4zM12 13v8" stroke={color} strokeWidth={stroke} strokeLinejoin="round" />
    </Svg>
  );
}

/** 체크 표시 (원본 .gchk/.lchk 14 · CKI 11 · Pick 12) */
export function CheckMark({ size = 14, color = '#FFFFFF', stroke = 2.2, kind = 'sel' }: { size?: number; color?: string; stroke?: number; kind?: 'sel' | 'cki' | 'pick' }) {
  if (kind === 'cki')
    return (
      <Svg width={size} height={size} viewBox="0 0 12 12" fill="none">
        <Path d="M2.5 6L4.8 8.3L9.5 3.5" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" />
      </Svg>
    );
  if (kind === 'pick')
    return (
      <Svg width={size} height={size} viewBox="0 0 12 12" fill="none">
        <Path d="M2.5 6L4.8 8.3L9.5 3.5" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" />
      </Svg>
    );
  return (
    <Svg width={size} height={size} viewBox="0 0 14 14" fill="none">
      <Path d="M3 7.2l2.6 2.6L11 4.6" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

/** 체크리스트 표 (원본 .cki 안: 선 2.4 #C2410C) */
export function CkiMark({ size = 14 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M5 12.5l4 4L19 7" stroke="#C2410C" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

/** 웹 점 세 개 (원본 memox.tsx Dots 18) */
export function Dots({ size = 18, color }: { size?: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 18 18" fill={color}>
      <Circle cx={4} cy={9} r={1.5} fill={color} />
      <Circle cx={9} cy={9} r={1.5} fill={color} />
      <Circle cx={14} cy={9} r={1.5} fill={color} />
    </Svg>
  );
}

/** 웹 끌기 안내 점 6개 (원본 BoardHead 14) */
export function Grip6({ color }: { color: string }) {
  return (
    <Svg width={14} height={14} viewBox="0 0 16 16">
      {[
        [5.5, 4],
        [10.5, 4],
        [5.5, 8],
        [10.5, 8],
        [5.5, 12],
        [10.5, 12],
      ].map(([x, y]) => (
        <Circle key={`${x}-${y}`} cx={x} cy={y} r={1.2} fill={color} />
      ))}
    </Svg>
  );
}

/** 앱 고르기 막대·밀기 아이콘 (원본 memo.html .sb · .act) */
export function SelIcon({ k, color, size = 22, stroke = 1.8 }: { k: 'pin' | 'color' | 'ai' | 'copy' | 'del'; color: string; size?: number; stroke?: number }) {
  if (k === 'pin') return <AppPin size={size} color={color} stroke={stroke} />;
  if (k === 'ai')
    return (
      <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <Path d="M9 3V7M15 3V7" stroke={color} strokeWidth={2} strokeLinecap="round" />
        <Path d={PLUG_BODY} fill={color} />
        <Path d="M12 16.5V21" stroke={color} strokeWidth={2} strokeLinecap="round" />
      </Svg>
    );
  if (k === 'color')
    return (
      <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <Circle cx={12} cy={12} r={9} stroke={color} strokeWidth={stroke} />
        <Circle cx={8.5} cy={10} r={1.3} fill={color} />
        <Circle cx={12} cy={7.5} r={1.3} fill={color} />
        <Circle cx={15.5} cy={10} r={1.3} fill={color} />
      </Svg>
    );
  if (k === 'copy')
    return (
      <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <Rect x={8} y={8} width={12} height={12} rx={2} stroke={color} strokeWidth={stroke} />
        <Path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" stroke={color} strokeWidth={stroke} />
      </Svg>
    );
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" stroke={color} strokeWidth={stroke} strokeLinecap="round" />
    </Svg>
  );
}

/** 앱 부채꼴 항목 아이콘 (원본 .fan-it: 체크리스트 · 메모, 22) */
export function FanIcon({ k }: { k: 'check' | 'memo' }) {
  if (k === 'check')
    return (
      <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
        <Rect x={4} y={4} width={16} height={16} rx={4} stroke="#FFFFFF" strokeWidth={2.2} />
        <Path d="M8 12.3l2.6 2.6L16 9.5" stroke="#FFFFFF" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
      </Svg>
    );
  return (
    <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
      <Path d="M5 4.5h14v10l-5 5H5z" stroke="#FFFFFF" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <Path d="M14 19.5v-5h5M8.5 9h7M8.5 12.5h4" stroke="#FFFFFF" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

/** 앱 + (원본 .fab: 26 · 선 2.4 흰색) · 웹 + (원본 NewMemoFab: 24 · 선 2.2) */
export function PlusGlyph({ size, stroke }: { size: number; stroke: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 5v14M5 12h14" stroke="#FFFFFF" strokeWidth={stroke} strokeLinecap="round" />
    </Svg>
  );
}

/** 웹 메뉴 아이콘 (원본 x.tsx MI: 18) */
export function MenuIcon({ k, color }: { k: 'pin' | 'trash' | 'copy' | 'find' | 'select' | 'move' | 'info'; color: string }) {
  const p = { stroke: color, strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, fill: 'none' };
  return (
    <Svg width={18} height={18} viewBox="0 0 20 20" fill="none">
      {k === 'pin' ? (
        <>
          <Path d="M12.5 2.5l5 5-3 1-3.5 3.5-.5 4-8-8 4-.5L10 4l1-3z" transform="translate(-0.5 0.5)" {...p} />
          <Path d="M3 17l4-4" {...p} />
        </>
      ) : k === 'trash' ? (
        <Path d="M3.5 5.5h13M8 5.5V3.5h4v2M5 5.5l.8 11h8.4l.8-11" {...p} />
      ) : k === 'copy' ? (
        <>
          <Rect x={6.5} y={6.5} width={10} height={10} rx={2} {...p} />
          <Path d="M13.5 6.5V4.5a1 1 0 0 0-1-1h-8a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h2" {...p} />
        </>
      ) : k === 'move' ? (
        <Path d="M4 7h12M12 3.5L15.5 7 12 10.5M16 13H4M8 16.5L4.5 13 8 9.5" {...p} />
      ) : k === 'info' ? (
        <>
          <Rect x={3} y={3.5} width={14} height={13} rx={2.5} {...p} />
          <Path d="M6.5 13V10M10 13V7.5M13.5 13v-4" {...p} />
        </>
      ) : k === 'find' ? (
        <>
          <Circle cx={9} cy={9} r={5.5} {...p} />
          <Path d="M13 13l4 4" {...p} />
        </>
      ) : (
        <>
          <Circle cx={10} cy={10} r={7} {...p} />
          <Path d="M7 10.2l2 2 4-4.4" {...p} />
        </>
      )}
    </Svg>
  );
}
