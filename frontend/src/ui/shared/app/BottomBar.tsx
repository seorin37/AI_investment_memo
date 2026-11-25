import React, { useCallback, useRef, useState } from 'react';
import { View, type ViewProps } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { create } from 'zustand';

type Bar = { id: object; top: number };
/** 지금 화면의 아래 버튼 줄 윗선 (화면 바닥에서, 안전 영역 포함) — 앱 토스트가 이 위 8 에 뜸. 버튼 줄이 없으면 null */
export const useBottomBar = create<{ bar: Bar | null }>(() => ({ bar: null }));

/** 상세 화면 아래 버튼 줄. clear: 버튼 위 투명한 그라데이션 높이 (토스트 위치에서 뺌) */
export function BottomBar({ clear = 0, ...p }: ViewProps & { clear?: number }) {
  const [id] = useState(() => ({}));
  const top = useRef(0);
  const focused = useRef(false);
  useFocusEffect(
    useCallback(() => {
      focused.current = true;
      if (top.current) useBottomBar.setState({ bar: { id, top: top.current } });
      return () => {
        focused.current = false;
        if (useBottomBar.getState().bar?.id === id) useBottomBar.setState({ bar: null });
      };
    }, [id]),
  );
  return (
    <View
      {...p}
      onLayout={(e) => {
        top.current = e.nativeEvent.layout.height - clear;
        if (focused.current) useBottomBar.setState({ bar: { id, top: top.current } });
      }}
    />
  );
}
