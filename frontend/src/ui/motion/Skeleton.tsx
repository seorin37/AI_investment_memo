import React, { useEffect, useId, useState } from 'react';
import { Animated, Easing, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';
import { NATIVE, useMotionK } from './useMotion';

/**
 * 뼈대 (원본 .m-sk: 바탕 #ECEEF2 · 라운드 10 · 흰 빛 띠(30%~70%, 가운데 .9)가 600px 폭으로 1.1s 마다 지나감)
 * 동작 줄이기면 빛 띠 없이 바탕만.
 */
export function Skeleton({ style, radius = 10 }: { style?: StyleProp<ViewStyle>; radius?: number }) {
  const k = useMotionK();
  const [x] = useState(() => new Animated.Value(0));
  /* 2026-11-23: 뼈대가 여러 개·화면이 쌓여도 id 가 겹치지 않게 (Sparkline 과 같은 방식) */
  const gid = `msk${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  useEffect(() => {
    if (k < 1) return;
    const a = Animated.loop(Animated.timing(x, { toValue: 1, duration: 1100, easing: Easing.linear, useNativeDriver: NATIVE }));
    a.start();
    return () => a.stop();
  }, [x, k]);
  return (
    <View style={[st.box, { borderRadius: radius }, style]}>
      {k === 1 && (
        <Animated.View pointerEvents="none" style={[st.band, { transform: [{ translateX: x.interpolate({ inputRange: [0, 1], outputRange: [-600, 600] }) }] }]}>
          <Svg width={600} height="100%" preserveAspectRatio="none">
            <Defs>
              <LinearGradient id={gid} x1="0" y1="0" x2="1" y2="0">
                <Stop offset="0.3" stopColor="#FFFFFF" stopOpacity={0} />
                <Stop offset="0.5" stopColor="#FFFFFF" stopOpacity={0.9} />
                <Stop offset="0.7" stopColor="#FFFFFF" stopOpacity={0} />
              </LinearGradient>
            </Defs>
            <Rect x="0" y="0" width="600" height="100%" fill={`url(#${gid})`} />
          </Svg>
        </Animated.View>
      )}
    </View>
  );
}

const st = StyleSheet.create({
  box: { backgroundColor: '#ECEEF2', overflow: 'hidden' },
  band: { position: 'absolute', top: 0, bottom: 0, left: 0, width: 600 },
});
