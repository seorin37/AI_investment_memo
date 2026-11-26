import { useWindowDimensions } from 'react-native';

/** 앱 글자 크기 상한 (AppText.native 의 maxFontSizeMultiplier 와 같음) */
export const MAX_FONT_SCALE = 1.3;

/** 지금 화면에 쓰이는 글자 배율 (시스템 설정 · 상한 1.3). 설정이 바뀌면 다시 그림 */
export function useFontScale(): number {
  const { fontScale } = useWindowDimensions();
  return Math.min(MAX_FONT_SCALE, Math.max(1, fontScale || 1));
}
