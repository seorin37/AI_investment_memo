import React, { createContext, useContext, useEffect, useState } from 'react';
import { Animated, View, type NativeScrollEvent, type NativeSyntheticEvent, type ScrollViewInstance, type ScrollViewProps, type StyleProp, type ViewStyle } from 'react-native';
import { NATIVE } from '@/ui/motion/useMotion';
import { MiniSpace } from '@/ui/screens/studio/app/MiniBar';

/** 탭 화면 상단 바 높이 · 첫 본문까지 간격 (탭 위에 덮는 편집·선택 머리도 같은 값을 씀) */
export const TAB_BAR_H = 64;
export const TAB_BAR_GAP = 12;

/** 본문이 올라간 만큼 — TopBar 가 부제목을 같이 올림 */
const ScrollY = createContext<Animated.Value | null>(null);
export const useTabScrollY = () => useContext(ScrollY);
/** 본문이 맨 위에서 내려갔는지 — TopBar 아래 구분선 */
const Scrolled = createContext<{ on: boolean; set: (v: boolean) => void } | null>(null);
export const useTabScrolled = () => useContext(Scrolled)?.on ?? false;

/**
 * 탭 화면 바깥 틀 (탭 5개 공용): 상단 바(64)는 고정, 부제목은 TabScroll 과 함께 올라감.
 * 부제목 자리(제목 아래 6)는 바 높이 안이라 본문과 따로 그리고, 스크롤 값으로 같은 만큼 옮김.
 * 맨 위에서는 바 아래 선 없음, 스크롤을 시작하면 선이 나타남.
 */
export function TabFrame({ style, children }: { style?: StyleProp<ViewStyle>; children: React.ReactNode }) {
  const [y] = useState(() => new Animated.Value(0));
  const [on, set] = useState(false);
  return (
    <ScrollY.Provider value={y}>
      <Scrolled.Provider value={{ on, set }}>
        <View style={style}>{children}</View>
      </Scrolled.Provider>
    </ScrollY.Provider>
  );
}

/** 탭 화면 본문: 바 아래 간격 12 도 함께 스크롤됨 */
export function TabScroll({ children, contentContainerStyle, onScroll, ...p }: ScrollViewProps & { ref?: React.Ref<ScrollViewInstance> }) {
  const y = useTabScrollY();
  const sc = useContext(Scrolled);
  useEffect(() => {
    y?.setValue(0);
    sc?.set(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [y]);
  const listener = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const down = e.nativeEvent.contentOffset.y > 0;
    if (sc && sc.on !== down) sc.set(down);
    onScroll?.(e);
  };
  return (
    <Animated.ScrollView
      scrollEventThrottle={16}
      showsVerticalScrollIndicator={false}
      {...p}
      contentContainerStyle={[{ paddingTop: TAB_BAR_GAP }, contentContainerStyle]}
      onScroll={y ? Animated.event([{ nativeEvent: { contentOffset: { y } } }], { useNativeDriver: NATIVE, listener }) : listener}
    >
      {children}
      <MiniSpace />
    </Animated.ScrollView>
  );
}
