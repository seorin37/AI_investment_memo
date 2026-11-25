import React from 'react';
import { View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';

/* Pretendard 에 없는 기호를 글 안에 그림으로 (앱) */
/** ✦ */
export function InlineSpark({ size = 10, color }: { size?: number; color: string }) {
  return (
    <View style={{ width: size, height: size }} importantForAccessibility="no" accessible={false}>
      <Svg width={size} height={size} viewBox="0 0 12 12"><Path d="M6 0C6.6 3.6 8.4 5.4 12 6C8.4 6.6 6.6 8.4 6 12C5.4 8.4 3.6 6.6 0 6C3.6 5.4 5.4 3.6 6 0Z" fill={color} /></Svg>
    </View>
  );
}
/** ⋮⋮ */
export function InlineGrip({ color }: { color: string }) {
  return (
    <View style={{ width: 8, height: 10 }} importantForAccessibility="no" accessible={false}>
      <Svg width={8} height={10} viewBox="0 0 8 10">{[2, 6].map((x) => [1.5, 5, 8.5].map((y) => <Circle key={`${x}${y}`} cx={x} cy={y} r={1} fill={color} />))}</Svg>
    </View>
  );
}
