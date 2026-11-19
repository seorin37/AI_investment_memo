/**
 * 앱 화면용 Text · TextInput — style 의 fontWeight 를 Pretendard 굵기 글꼴로 바꿔 줌 (11.18).
 * 받은 앱 UI 코드는 fontWeight 로 굵기를 적어서, RN 기본 Text 그대로면 시스템 글꼴로 보이고 안드로이드는 굵기도 어긋난다.
 * 400 이하 → Regular · 500 → Medium · 600 → SemiBold · 700 이상 → Bold. fontFamily 를 직접 준 곳은 그대로 둔다.
 * (웹 겸용 기존 화면은 지금처럼 components/ui/Text.tsx 의 <T> 를 쓴다)
 */
import type { ComponentProps } from 'react';
import { Animated, StyleSheet, Text as RNText, TextInput as RNTextInput, type StyleProp, type TextStyle } from 'react-native';
import { fonts } from '@/theme/tokens';

function familyOf(weight: TextStyle['fontWeight']): string {
  const n = weight === 'bold' ? 700 : weight == null || weight === 'normal' ? 400 : Number(weight);
  if (n >= 700) return fonts.bold;
  if (n >= 600) return fonts.semibold;
  if (n >= 500) return fonts.medium;
  return fonts.regular;
}

/* 굵기는 글꼴 파일로 정하고 fontWeight 는 'normal' 로 — 안드로이드가 굵기를 한 번 더 덧입히지(가짜 굵게) 않게 */
function pretendard<S>(style: StyleProp<S>): StyleProp<S> {
  const flat = (StyleSheet.flatten(style as StyleProp<TextStyle>) ?? {}) as TextStyle;
  if (flat.fontFamily) return style;
  return [style, { fontFamily: familyOf(flat.fontWeight), fontWeight: 'normal' }] as StyleProp<S>;
}

export function Text(props: ComponentProps<typeof RNText>) {
  return <RNText {...props} style={pretendard(props.style)} />;
}

export function TextInput(props: ComponentProps<typeof RNTextInput>) {
  return <RNTextInput {...props} style={pretendard(props.style)} />;
}

/** Animated.Text 대신 (TopBar 제목 · 스낵바 · 큰 제목) */
export const AnimatedText = Animated.createAnimatedComponent(Text);
