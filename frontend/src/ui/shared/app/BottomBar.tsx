import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, type ViewProps } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { create } from 'zustand';

type Bar = { id: object; top: number };
/** 지금 화면의 아래 버튼 줄 윗선 (화면 바닥에서, 안전 영역 포함) — 앱 토스트가 이 위 8 에 뜸. 버튼 줄이 없으면 null */
export const useBottomBar = create<{ bar: Bar | null }>(() => ({ bar: null }));

/** 높이를 아는 아래 막대(고르기 막대 등): 보이는 동안 윗선을 알림 (0 = 없음) */
export function useBottomBarTop(top: number) {
  const [id] = useState(() => ({}));
  useEffect(() => {
    if (top) useBottomBar.setState({ bar: { id, top } });
    return () => {
      if (useBottomBar.getState().bar?.id === id) useBottomBar.setState({ bar: null });
    };
  }, [id, top]);
}

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
