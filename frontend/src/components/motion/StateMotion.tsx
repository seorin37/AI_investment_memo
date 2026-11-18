/**
 * 상태 안내 움직임
 *  - ErrorRetry (Lucian #090 error-retry): 못 불러오면 안내 상자가 좌우로 살짝 흔들림(.4s) ·
 *    [다시 시도]를 누르면 화살표가 돌아가고(.8s 반복) 버튼은 잠깐 눌림 상태 · 또 실패하면 다시 흔들림.
 *  - NoResults (Lucian #092 no-results-search): 검색 결과가 없으면 돋보기가 갸웃(좌우 기울임 2번) 하고 글이 떠오름.
 *  - Spinner: 둥근 고리가 .8초에 한 바퀴 (체험판 .scan i · .ptr.spin)
 */
import { useEffect, useRef } from 'react';
import { Animated, Pressable, StyleSheet, View, type StyleProp, type TextStyle, type ViewStyle } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { Appear } from '@/components/motion/Appear';
import { EASE, LINEAR, ND, SPRING, tween, useReduceMotion, useValue } from '@/components/motion/motion';

export function Spinner({ size = 16, color, track }: { size?: number; color: string; track: string }) {
  const r = useValue(0);
  const still = useReduceMotion();
  useEffect(() => {
    if (still) return;
    const loop = Animated.loop(tween(r, 1, 800, LINEAR, ND));
    loop.start();
    return () => loop.stop();
  }, [r, still]);
  return (
    <Animated.View style={{ width: size, height: size, borderRadius: size / 2, borderWidth: 2.5, borderColor: track, borderTopColor: color,
      transform: [{ rotate: r.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }] }} />
  );
}

export interface ErrorRetryProps {
  message: string;
  retrying: boolean;
  onRetry: () => void;
  /** 실패할 때마다 1씩 올려 주면 다시 흔들림 */
  fail_count: number;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
  buttonStyle?: StyleProp<ViewStyle>;
  buttonTextStyle?: StyleProp<TextStyle>;
  iconColor: string;
}

export function ErrorRetry({ message, retrying, onRetry, fail_count, style, textStyle, buttonStyle, buttonTextStyle, iconColor }: ErrorRetryProps) {
  const shake = useValue(0);
  const spin = useValue(0);
  const still = useReduceMotion();
  useEffect(() => {
    shake.setValue(0);
    tween(shake, 1, 400, LINEAR, ND).start();
  }, [fail_count, shake]);
  useEffect(() => {
    if (!retrying || still) { spin.setValue(0); return; }
    const loop = Animated.loop(tween(spin, 1, 800, LINEAR, ND));
    loop.start();
    return () => loop.stop();
  }, [retrying, still, spin]);
  const translateX = shake.interpolate({ inputRange: [0, 0.15, 0.35, 0.55, 0.75, 1], outputRange: [0, -6, 5, -3, 2, 0] });
  return (
    <Animated.View style={[style, { transform: [{ translateX }] }]}>
      <Text style={textStyle}>{message}</Text>
      <Pressable onPress={onRetry} disabled={retrying} style={[buttonStyle, retrying && st.dim]} accessibilityRole="button" accessibilityState={{ busy: retrying }}>
        <Animated.View style={{ transform: [{ rotate: spin.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }] }}>
          <MobileIcon name="refresh" size={15} color={iconColor} />
        </Animated.View>
        <Text style={buttonTextStyle}>{retrying ? '불러오는 중' : '다시 시도'}</Text>
      </Pressable>
    </Animated.View>
  );
}

export function NoResults({ query, hint, iconColor, iconBg, titleStyle, hintStyle }: {
  query: string; hint: string; iconColor: string; iconBg: string; titleStyle?: StyleProp<TextStyle>; hintStyle?: StyleProp<TextStyle>;
}) {
  const tilt = useValue(0);
  const prev = useRef('');
  useEffect(() => {
    if (prev.current === query) return;
    prev.current = query;
    tilt.setValue(0);
    Animated.sequence([Animated.delay(120), tween(tilt, 1, 900, EASE, ND)]).start();
  }, [query, tilt]);
  const rotate = tilt.interpolate({ inputRange: [0, 0.2, 0.45, 0.7, 1], outputRange: ['0deg', '-14deg', '10deg', '-6deg', '0deg'] });
  return (
    <View style={st.nr}>
      <Appear kind="pop" replay={query}>
        <Animated.View style={[st.nrIcon, { backgroundColor: iconBg, transform: [{ rotate }] }]}>
          <MobileIcon name="search" size={26} color={iconColor} />
        </Animated.View>
      </Appear>
      <Appear kind="up" index={1} replay={query}><Text style={titleStyle}>‘{query}’ 결과가 없어요</Text></Appear>
      <Appear kind="up" index={2} replay={query}><Text style={hintStyle}>{hint}</Text></Appear>
    </View>
  );
}

/** 누르면 살짝 작아졌다 spring 으로 돌아오는 버튼 겉 (체험판 .bt · .pp transform .3s spring) */
export function usePressScale(to = 0.96) {
  const s = useValue(1);
  return {
    scale: s,
    onPressIn: () => tween(s, to, 90, EASE, ND).start(),
    onPressOut: () => tween(s, 1, 300, SPRING, ND).start(),
  };
}

const st = StyleSheet.create({
  dim: { opacity: 0.7 },
  nr: { alignItems: 'center', paddingVertical: 40, gap: 8 },
  nrIcon: { width: 60, height: 60, borderRadius: 30, alignItems: 'center', justifyContent: 'center', marginBottom: 6 },
});
