import React from 'react';
import type { SwipeRowProps } from './SwipeRow.types';

/** 웹: 줄 밀기 없음 (원본 웹 목록은 ⋯ 메뉴 · 우클릭) — 같은 props, 내용만 */
export function SwipeRow({ children }: SwipeRowProps) {
  return <>{children}</>;
}
