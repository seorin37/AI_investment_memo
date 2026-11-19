import React from 'react';
import Svg, { Circle, G, Path, Rect } from 'react-native-svg';
import type { HomeWidget } from '@/ui/screens/home/Home.types';

/* 원본 home.html 위젯 아이콘 (ALL[id][4]: 24 viewBox · 18 · 선 2 · 둥근 끝) 과 바탕·글자 색 */
export const WIDGET_META: Record<HomeWidget, { title: string; sub: string; bg: string; ink: string }> = {
  market: { title: '시장 한눈에 보기', sub: '코스피 · 코스닥 · 원/달러', bg: '#E4ECFF', ink: '#3D73F0' },
  updates: { title: '종목별 업데이트', sub: '내 종목의 새 소식 수', bg: '#EEE8FF', ink: '#7046F5' },
  news: { title: '뉴스', sub: '오늘의 시장 뉴스', bg: '#FFE8E8', ink: '#E5484D' },
  check: { title: '체크리스트', sub: '자유롭게 적는 할 일 목록', bg: '#EEE8FF', ink: '#7046F5' },
};

export function WidgetGlyph({ id, size = 18 }: { id: HomeWidget; size?: number }) {
  const c = WIDGET_META[id].ink;
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      {id === 'market' ? (
        <>
          <Path d="M4 18l5-6 4 3 7-8" />
          <Path d="M15 7h5v5" />
        </>
      ) : id === 'updates' ? (
        <Path d="M20 12a8 8 0 0 1-14 5.3M4 12a8 8 0 0 1 14-5.3M18 3v4h-4M6 21v-4h4" />
      ) : id === 'news' ? (
        <>
          <Rect x={5} y={4} width={14} height={16} rx={2} />
          <Path d="M8 8h8M8 12h8M8 16h5" />
        </>
      ) : (
        <>
          <Rect x={4} y={4} width={16} height={16} rx={4} />
          <Path d="M8.5 12l2.5 2.5 4.5-5" />
        </>
      )}
    </Svg>
  );
}

/** 편집 막대 손잡이 (14×16 · 점 r1.5 #9A9EA7) */
export function GripDots() {
  return (
    <Svg width={14} height={16} viewBox="0 0 14 16" fill="#9A9EA7">
      {[3, 8, 13].map((y) => (
        <G key={y}>
          <Circle cx={4} cy={y} r={1.5} />
          <Circle cx={10} cy={y} r={1.5} />
        </G>
      ))}
    </Svg>
  );
}

/** 홈 편집 버튼 (조절 막대 16) */
export function SlidersGlyph() {
  return (
    <Svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="#16171A" strokeWidth={2} strokeLinecap="round">
      <Path d="M4 8h10M18 8h2M4 16h2M10 16h10" />
      <Circle cx={16} cy={8} r={2} />
      <Circle cx={8} cy={16} r={2} />
    </Svg>
  );
}

/** + (편집 머리 [추가] 14 · #6A42AB · 선 2.2) */
export function PlusGlyph({ color = '#6A42AB' }: { color?: string }) {
  return (
    <Svg width={14} height={14} viewBox="0 0 14 14" fill="none">
      <Path d="M7 2v10M2 7h10" stroke={color} strokeWidth={2.2} strokeLinecap="round" />
    </Svg>
  );
}

/** 업데이트 확인하기 › (14 · 흰 선 2.4) */
export function CtaChevron() {
  return (
    <Svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth={2.4}>
      <Path d="M9 6l6 6-6 6" />
    </Svg>
  );
}

/** 체크 (체크리스트 동그라미 안 14 · 흰 선 2.4) */
export function CheckGlyph() {
  return (
    <Svg width={14} height={14} viewBox="0 0 14 14" fill="none">
      <Path d="M3 7.2l2.6 2.6L11 4.6" stroke="#FFFFFF" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

/** 불러오기 실패 플러그 (120×40) — 오른쪽 플러그는 shift 만큼 밀림 (다시 꽂힘) */
export function PlugGlyph({ shift = 0 }: { shift?: number }) {
  return (
    <Svg width={120} height={40} viewBox="0 0 120 40">
      <Path d="M0 20h40" stroke="#C9CDD4" strokeWidth={3} />
      <Rect x={38} y={12} width={16} height={16} rx={4} fill="#C9CDD4" />
      <Path d="M54 16h6M54 24h6" stroke="#C9CDD4" strokeWidth={3} strokeLinecap="round" />
      <G transform={`translate(${shift} 0)`}>
        <Rect x={66} y={12} width={16} height={16} rx={4} fill="#8569E3" />
        <Path d="M82 20h38" stroke="#8569E3" strokeWidth={3} />
      </G>
    </Svg>
  );
}

/** 앱 안 브라우저: 닫기 X (20 · 선 2.2) · 브라우저로 열기 ↗ (20 · 선 2) */
export function BrowserClose() {
  return (
    <Svg width={20} height={20} viewBox="0 0 24 24" stroke="#16171A" strokeWidth={2.2} strokeLinecap="round">
      <Path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  );
}
export function BrowserExternal() {
  return (
    <Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="#16171A" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
    </Svg>
  );
}
/** 검색칸 돋보기 (18 · #575B63) */
export function SearchGlyph() {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="#575B63" strokeWidth={2} strokeLinecap="round">
      <Circle cx={11} cy={11} r={7} />
      <Path d="M20 20l-4-4" />
    </Svg>
  );
}
