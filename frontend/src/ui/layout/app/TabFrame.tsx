import React, { createContext, useContext, useEffect, useState } from 'react';
import { Animated, View, type ScrollViewInstance, type ScrollViewProps, type StyleProp, type ViewStyle } from 'react-native';
import { NATIVE } from '@/ui/motion/useMotion';

/** 탭 화면 상단 바 높이 · 첫 본문까지 간격 (탭 위에 덮는 편집·선택 머리도 같은 값을 씀) */
export const TAB_BAR_H = 64;
export const TAB_BAR_GAP = 12;

/** 본문이 올라간 만큼 — TopBar 가 부제목을 같이 올림 */
const ScrollY = createContext<Animated.Value | null>(null);
export const useTabScrollY = () => useContext(ScrollY);

/**
 * 탭 화면 바깥 틀 (탭 5개 공용): 상단 바(64)는 고정, 부제목은 TabScroll 과 함께 올라감.
 * 부제목 자리(제목 아래 6)는 바 높이 안이라 본문과 따로 그리고, 스크롤 값으로 같은 만큼 옮김.
 */
export function TabFrame({ style, children }: { style?: StyleProp<ViewStyle>; children: React.ReactNode }) {
  const [y] = useState(() => new Animated.Value(0));
  return (
    <ScrollY.Provider value={y}>
      <View style={style}>{children}</View>
    </ScrollY.Provider>
  );
}

/** 탭 화면 본문: 바 아래 간격 12 도 함께 스크롤됨 */
export function TabScroll({ contentContainerStyle, onScroll, ...p }: ScrollViewProps & { ref?: React.Ref<ScrollViewInstance> }) {
  const y = useTabScrollY();
  useEffect(() => {
    y?.setValue(0);
  }, [y]);
  return (
    <Animated.ScrollView
      scrollEventThrottle={16}
      showsVerticalScrollIndicator={false}
      {...p}
      contentContainerStyle={[{ paddingTop: TAB_BAR_GAP }, contentContainerStyle]}
      onScroll={y ? Animated.event([{ nativeEvent: { contentOffset: { y } } }], { useNativeDriver: NATIVE, listener: onScroll as never }) : onScroll}
    />
  );
}
