import React, { useState } from 'react';
import { View, type LayoutChangeEvent } from 'react-native';

/* 원본 stock.tsx FixedFrame (11.13): 860 고정 틀 · 양옆 24 · 자리에 맞춰 줄이거나 최대 1.15배 */
export const FRAME = 860;
const GUT = 24;
const KMAX = 1.15;

/**
 * 웹 고정 틀 — 노션처럼 860px 로 그리고 가운데 폭에 맞춰 비율 그대로 줄임 (1440 · 사이드바·스튜디오 펼침에서 약 .82)
 * children 은 860 기준 원본 px 그대로. 배율은 onScale 로 알려 줌 (끌기 좌표 계산용).
 */
export function FixedFrame({ children, onScale }: { children: React.ReactNode; onScale?: (k: number) => void }) {
  const [w, setW] = useState(0);
  const [h, setH] = useState(0);
  const k = w ? Math.max(0.5, Math.min(KMAX, (w - GUT * 2) / FRAME)) : 1;
  const onOuter = (e: LayoutChangeEvent) => {
    const nw = e.nativeEvent.layout.width;
    setW(nw);
    onScale?.(Math.max(0.5, Math.min(KMAX, (nw - GUT * 2) / FRAME)));
  };
  return (
    <View onLayout={onOuter} style={{ width: '100%' }}>
      <View style={{ width: FRAME * k, height: h * k, alignSelf: 'center', opacity: w ? 1 : 0 }}>
        <View onLayout={(e) => setH(e.nativeEvent.layout.height)} style={{ position: 'absolute', left: 0, top: 0, width: FRAME, transformOrigin: 'left top', transform: [{ scale: k }] }}>
          {children}
        </View>
      </View>
    </View>
  );
}
