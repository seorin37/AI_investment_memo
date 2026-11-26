/**
 * 앱 화면용 Text · TextInput — style 의 fontWeight 를 Pretendard 굵기 글꼴로 바꿔 줌 (11.18).
 * 받은 앱 UI 코드는 fontWeight 로 굵기를 적어서, RN 기본 Text 그대로면 시스템 글꼴로 보이고 안드로이드는 굵기도 어긋난다.
 * 400 이하 → Regular · 500 → Medium · 600 → SemiBold · 700 → Bold · 800 이상 → ExtraBold (11.19 UI v2). fontFamily 를 직접 준 곳은 그대로 둔다.
 * (웹 겸용 기존 화면은 지금처럼 components/ui/Text.tsx 의 <T> 를 쓴다)
 */
import { Children, type ComponentProps, type ReactNode } from 'react';
import { Animated, Platform, StyleSheet, Text as RNText, TextInput as RNTextInput, type StyleProp, type TextStyle } from 'react-native';
import { fonts } from '@/theme/tokens';

function familyOf(weight: TextStyle['fontWeight']): string {
  const n = weight === 'bold' ? 700 : weight == null || weight === 'normal' ? 400 : Number(weight);
  if (n >= 800) return fonts.extrabold;
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

/**
 * keepAll — CSS word-break: keep-all (원본 body 기본값). 기본 꺼짐.
 * RN 0.88 안드로이드 Text 에는 어절 줄바꿈 옵션이 없어(textBreakStrategy 만 있음) 어절 안 글자 사이에
 * WORD JOINER(U+2060)를 넣는다. 화면에 안 보이고 스크린 리더도 읽지 않는다. 웹은 CSS 로.
 * 고정 문구(제목·설명·버튼)에만 켠다. 사용자 입력·메모 본문에는 쓰지 않는다 (복사하면 U+2060 이 같이 복사됨).
 */
const WJ = '⁠';
export function keepAllText(text: string): string {
  return text
    .split('\n')
    .map((line) => line.split(' ').map((word) => Array.from(word).join(WJ)).join(' '))
    .join('\n');
}
function keepAllChildren(children: ReactNode): ReactNode {
  return Children.map(children, (c) => (typeof c === 'string' ? keepAllText(c) : c));
}

type AppTextProps = ComponentProps<typeof RNText> & { keepAll?: boolean };

/* 웹: 한글을 어절 단위로 줄바꿈 (keep-all) · 긴 영문·URL 은 칸 안에서 끊음 (anywhere) — 2026-11-26 수정 77 */
const WEB_WRAP = { wordBreak: 'keep-all', overflowWrap: 'anywhere' } as TextStyle;

export function Text({ keepAll, children, ...props }: AppTextProps) {
  if (Platform.OS === 'web') {
    return <RNText {...props} style={[pretendard(props.style), WEB_WRAP]}>{children}</RNText>;
  }
  return (
    <RNText {...props} style={pretendard(props.style)}>
      {keepAll ? keepAllChildren(children) : children}
    </RNText>
  );
}

export function TextInput(props: ComponentProps<typeof RNTextInput>) {
  return <RNTextInput {...props} style={pretendard(props.style)} />;
}

/** Animated.Text 대신 (TopBar 제목 · 스낵바 · 큰 제목) */
export const AnimatedText = Animated.createAnimatedComponent(Text);
