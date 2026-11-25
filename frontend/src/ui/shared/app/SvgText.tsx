import React from 'react';
import { Platform } from 'react-native';
import { Text, type TextProps } from 'react-native-svg';
import { fonts } from '@/theme/tokens';

/** 차트 글자: 굵기를 Pretendard 패밀리로 (react-native-svg 글자는 AppText 를 안 거쳐 시스템 글꼴로 떨어짐) */
export function SvgText({ bold, ...p }: Omit<TextProps, 'fontWeight' | 'fontFamily'> & { bold?: boolean }) {
  return <Text fontFamily={bold ? fonts.bold : fonts.regular} {...p} />;
}

/* 웹과 함께 쓰는 차트(EvidenceContent 의 가격 차트)는 파일을 못 고치므로, 앱에서만 기본 글꼴을 줌 */
if (Platform.OS !== 'web') {
  const T = Text as unknown as { defaultProps?: object };
  T.defaultProps = { ...T.defaultProps, fontFamily: fonts.regular };
}
