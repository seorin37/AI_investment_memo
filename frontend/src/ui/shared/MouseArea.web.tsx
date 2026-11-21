import React from 'react';
import type { MouseAreaProps } from './MouseArea.types';

/** 웹: 마우스 위치 (상자 왼쪽 위 기준 · 화면 배율을 나눈 원본 px) — 차트 안내선 · 막대 hover 용 */
export function MouseArea({ width, height, scale = 1, onMove, onLeave, style, cursor = 'crosshair' }: MouseAreaProps) {
  return React.createElement('div', {
    onMouseMove: (e: React.MouseEvent<HTMLDivElement>) => {
      const r = e.currentTarget.getBoundingClientRect();
      onMove((e.clientX - r.left) / scale, (e.clientY - r.top) / scale);
    },
    onMouseLeave: onLeave,
    style: { position: 'absolute', width, height, cursor, ...(style ?? {}) },
  });
}
