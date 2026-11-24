/* eslint-disable react-hooks/refs -- RN Animated 관용 패턴. React Compiler 켜면 이 파일부터 정리 필요 */
/**
 * 화면 넘어가기 · 큰 제목 · 당겨서 새로고침
 *
 * ① 밀려 들어오는 화면 (Lucian #324 push-navigation-stack)
 *    메모 상세 · 체크리스트 · 기업정보처럼 "안으로 들어가는" 화면은 오른쪽에서 밀려 들어오고, 왼쪽 끝을 끌어 돌아감.
 *    앱(iOS·Android)은 expo-router Stack 이 이미 이 움직임을 기기 방식대로 해 줌 → app/(tabs)/stock/_layout.tsx 등에서
 *      <Stack screenOptions={PUSH_SCREEN_OPTIONS} />
 *    웹은 Stack 이 움직임 없이 바뀌어서, 화면 맨 바깥을 <PushIn> 으로 감싸면 .42s 로 밀려 들어옴 (앱에서는 아무것도 안 함).
 *
 * ② 큰 제목 접기 (Lucian #332 collapsing-large-title)
 *    useLargeTitle(): 화면 위 큰 제목이 스크롤하면 작아지며 사라지고, 위 바(TopBar)의 작은 제목 · 아래 선이 나타남.
 *
 * ③ 당겨서 새로고침 (Lucian #085 pull-to-refresh)
 *    RN 기본 RefreshControl 사용 (기기 기본 돌개). 화면에서 refreshing · onRefresh props 로 받음.
 */
import { useEffect, useRef, type ReactNode } from 'react';
import { Animated, Platform, useWindowDimensions } from 'react-native';
import { EASE, ms, tween, useValue } from '@/components/motion/motion';

/** expo-router <Stack screenOptions> 에 그대로 넣는 값 (react-navigation native-stack 옵션) */
export const PUSH_SCREEN_OPTIONS = {
  headerShown: false,
  animation: 'slide_from_right',
  gestureEnabled: true,
  animationDuration: 350,
} as const;

export function PushIn({ children }: { children: ReactNode }) {
  const { width } = useWindowDimensions();
  const x = useValue(Platform.OS === 'web' ? 1 : 0);
  useEffect(() => { if (Platform.OS === 'web') tween(x, 0, 420, EASE, false).start(); }, [x]);
  if (Platform.OS !== 'web') return <>{children}</>;
  return (
    <Animated.View style={{ flex: 1, transform: [{ translateX: x.interpolate({ inputRange: [0, 1], outputRange: [0, width] }) }] }}>
      {children}
    </Animated.View>
  );
}

/**
 * const lt = useLargeTitle();
 * <ScrollView onScroll={lt.onScroll} scrollEventThrottle={16}> <Animated.Text style={[st.big, lt.bigStyle]}>내 종목</Animated.Text> ...
 * <TopBar ... /> 위에 lt.barTitleOpacity / lt.barLineOpacity 를 넘겨 작은 제목·선을 보이게.
 */
export function useLargeTitle(range = 44) {
  const y = useRef(new Animated.Value(0)).current;
  const onScroll = Animated.event([{ nativeEvent: { contentOffset: { y } } }], { useNativeDriver: false });
  const k = ms(1) ? 1 : 0;
  return {
    scrollY: y,
    onScroll,
    bigStyle: {
      opacity: y.interpolate({ inputRange: [0, range * 0.7], outputRange: [1, k ? 0 : 1], extrapolate: 'clamp' }),
      transform: [{ scale: y.interpolate({ inputRange: [-80, 0, range], outputRange: [k ? 1.08 : 1, 1, k ? 0.92 : 1], extrapolate: 'clamp' }) }],
    },
    barTitleOpacity: y.interpolate({ inputRange: [range * 0.6, range], outputRange: [0, 1], extrapolate: 'clamp' }),
    barLineOpacity: y.interpolate({ inputRange: [0, range], outputRange: [0, 1], extrapolate: 'clamp' }),
  };
}
