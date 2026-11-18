import React from 'react';
import { Platform, Text, type TextProps, type TextStyle } from 'react-native';
import { colors, fonts, type FontWeightKey } from '@/theme/tokens';

export interface TProps extends TextProps {
  size?: number;
  weight?: FontWeightKey;
  color?: string;
  align?: TextStyle['textAlign'];
  lh?: number; // line-height 배수
  tabular?: boolean; // 숫자 고정폭
  strike?: boolean;
}

/**
 * 모든 텍스트는 이 컴포넌트로 — Pretendard 굵기별 폰트 패밀리를 지정합니다.
 * (안드로이드는 커스텀 폰트에 fontWeight 가 적용되지 않으므로 패밀리로 굵기를 고릅니다)
 */
export function T({ size = 15, weight = 'regular', color = colors.text, align, lh = 1.45, tabular, strike, style, ...rest }: TProps) {
  return (
    <Text
      {...rest}
      style={[
        {
          fontFamily: fonts[weight],
          fontSize: size,
          lineHeight: Math.round(size * lh),
          color,
          textAlign: align,
          letterSpacing: size >= 22 ? -0.4 : size >= 16 ? -0.2 : -0.1,
        },
        tabular && { fontVariant: ['tabular-nums'] },
        strike && { textDecorationLine: 'line-through' },
        Platform.OS === 'web' && ({ wordBreak: 'keep-all' } as TextStyle),
        style,
      ]}
    />
  );
}
