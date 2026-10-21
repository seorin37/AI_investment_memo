import { useWindowDimensions } from 'react-native';
import { layout, colors } from '@/theme/tokens';
import { useSettings } from './queries';

/** 웹 우선(데스크톱 1440 기준) → 태블릿 → 모바일 순으로 축소 */
export function useBreakpoint() {
  const { width, height } = useWindowDimensions();
  const isMobile = width < layout.breakpoints.mobile;
  const isDesktop = width >= layout.breakpoints.desktop;
  return { width, height, isMobile, isTablet: !isMobile && !isDesktop, isDesktop };
}

/** 설정 '등락 색상'(상승 빨강·하락 파랑 / 상승 초록·하락 빨강)을 반영한 색 */
export function useMarketColors() {
  const { data } = useSettings();
  const scheme = data?.updown_color ?? 'red_up';
  const up = scheme === 'red_up' ? colors.up : colors.upAlt;
  const down = scheme === 'red_up' ? colors.down : colors.downAlt;
  return {
    up,
    down,
    flat: colors.textSub,
    of: (delta: number) => (delta > 0 ? up : delta < 0 ? down : colors.textSub),
  };
}
