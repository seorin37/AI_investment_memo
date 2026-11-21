import React from 'react';
import { Platform, View, type StyleProp, type ViewProps, type ViewStyle } from 'react-native';
import { useTheme } from '@/store/theme';
import type { MemoColor } from '@/types/models';
import { checklistTone, paper, paperDarkPre } from '@/ui/theme';

/*
 * 다크 모드 = 원본과 같은 반전 방식 (웹 theme.css · 앱 x/app.css)
 * Figma 에 다크 색이 없어서 화면 전체를 반전(색상은 유지)하고, 로고·사진·종목 로고·스위치만 원래 색으로 되돌림.
 */
/** 화면 반전 (원본 invert(1) hue-rotate(180deg) contrast(.88)) */
export const DARK_FILTER = [{ invert: 1 }, { hueRotate: '180deg' }, { contrast: 0.88 }] as ViewStyle['filter'];
/** 원래 색 유지 (원본 .dk-keep: contrast(1.1364) invert(1) hue-rotate(180deg)) */
const KEEP_FILTER = (Platform.OS === 'web' ? 'contrast(1.1364) invert(1) hue-rotate(180deg)' : [{ contrast: 1.1364 }, { invert: 1 }, { hueRotate: '180deg' }]) as ViewStyle['filter'];

/** 팝업 뒤 막: 반전 때문에 다크에서 밝게 덮이던 것을 어둡게 (원본 웹 theme.css 11.18 .m-scrim) */
export const SCRIM_DARK = 'rgba(255,255,255,0.5)';

/** iOS 는 filter 가 brightness·opacity 만 돼서 다크 모드를 쓰지 않음 (스위치도 숨김) */
export const DARK_SUPPORTED = Platform.OS !== 'ios';

export const useDark = () => useTheme((s) => s.dark) && DARK_SUPPORTED;

/**
 * 앱: 반전을 거는 바탕. 최상위와, 따로 그려지는 Modal(시트·확인창·인앱 브라우저) 안쪽에 씀.
 * 웹은 html 전체에 CSS 로 걸려서(darkMode.web) 여기서는 아무것도 안 함.
 */
export function DarkLayer({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  const dark = useDark();
  if (Platform.OS === 'web') return <View style={[{ flex: 1 }, style]}>{children}</View>;
  return <View style={[{ flex: 1 }, style, dark ? { filter: DARK_FILTER } : null]}>{children}</View>;
}

/** 원래 색 유지 (원본 .dk-keep) — 종목 로고 · 프로필 사진 · 다크 스위치 · 소셜 로그인 버튼 */
export function Keep({ children, style, ...rest }: ViewProps & { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  const dark = useDark();
  return (
    <View {...rest} style={[style, dark ? { filter: KEEP_FILTER } : null]}>
      {children}
    </View>
  );
}

/**
 * 메모지 색: 다크면 원본 다크 종이색(웹 data.ts PAPER[].dk)이 반전 뒤에 보이도록 미리 계산한 색 (원본 웹 theme.css --pp-* · 앱 memo.html 과 같은 방식).
 * 종이 위 글자는 반전을 그대로 받아 밝아짐.
 */
export function usePaper(): Record<MemoColor, { bg: string; accent: string; label: string }> {
  return useDark() ? paperDarkPre : paper;
}

/** 체크리스트 색: 다크면 원본 다크 체크리스트 색이 반전 뒤에 보이도록 미리 계산한 값 */
export function useChecklistTone() {
  return useDark() ? checklistTone.dark : checklistTone.light;
}
