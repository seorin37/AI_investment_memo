import React from 'react';
import { Text } from '@/components/ui/AppText';
import { ft } from '@/ui/theme';
import { Keep } from './Dark';

export interface StockLogoProps {
  /** 로고 글자 (예: 'S', '삼', 'KB') */
  logo: string;
  /** 로고 바탕 색 */
  bg: string;
  /** 로고 글자 색 (없으면 흰색) */
  ink?: string;
  size: number;
  /**
   * app: 원본 앱 .logo/.lo (40 · 라운드 11 · 16px 800)
   * webSide: 웹 fig.tsx SLogo (24 · 라운드 size×.3 · 글자 size×.425/.34/.28 · bold)
   * web: 웹 kit.tsx StockLogo (라운드 8 · 글자 size×.44/.34 · black)
   */
  variant: 'app' | 'webSide' | 'web';
  radius?: number;
  fontSize?: number;
}

export function StockLogo({ logo, bg, ink = '#FFFFFF', size, variant, radius, fontSize }: StockLogoProps) {
  const len = logo.length;
  const r = radius ?? (variant === 'app' ? Math.round((size * 11) / 40) : variant === 'webSide' ? size * 0.3 : 8);
  const fs =
    fontSize ??
    (variant === 'app' ? Math.round((size * 16) / 40) : variant === 'webSide' ? size * (len > 2 ? 0.28 : len > 1 ? 0.34 : 0.425) : size * (len > 1 ? 0.34 : 0.44));
  const fw = variant === 'webSide' ? '700' : '800';
  return (
    <Keep style={{ width: size, height: size, borderRadius: r, backgroundColor: bg, alignItems: 'center', justifyContent: 'center' }} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Text style={[ft(fs, 1), { fontWeight: fw, color: ink }]} numberOfLines={1}>
        {logo}
      </Text>
    </Keep>
  );
}
