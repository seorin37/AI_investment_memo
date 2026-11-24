import React from 'react';
import Svg, { Circle, Path } from 'react-native-svg';

export function KakaoGlyph({ size = 24 }: { size?: number }) {
  return <Svg width={size} height={size} viewBox="0 0 24 24"><Path d="M12 3C6.48 3 2 6.49 2 10.8c0 2.77 1.85 5.2 4.63 6.58l-1.17 4.3c-.1.34.29.6.58.42l5.08-3.48c.29.02.58.03.88.03 5.52 0 10-3.5 10-7.85C22 6.45 17.52 3 12 3Z" fill="#191919" /></Svg>;
}

export function NaverGlyph({ size = 24 }: { size?: number }) {
  return <Svg width={size} height={size} viewBox="0 0 24 24"><Path d="M3 3h6.2l5.6 8.2V3H21v18h-6.2l-5.6-8.2V21H3V3Z" fill="#FFFFFF" /></Svg>;
}

export function GoogleGlyph({ size = 24 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path d="M21.8 10.25H12V14h5.65a6 6 0 0 1-2.05 2.8l3.1 2.6A10 10 0 0 0 22 12c0-.6-.05-1.2-.2-1.75Z" fill="#4285F4" />
      <Path d="M12 22a9.8 9.8 0 0 0 6.7-2.6l-3.1-2.6A6 6 0 0 1 6.35 14l-3.3 2.55A10 10 0 0 0 12 22Z" fill="#34A853" />
      <Path d="M6.35 14A6 6 0 0 1 6.45 9.75l-3.3-2.4a10 10 0 0 0-.1 9.2L6.35 14Z" fill="#FBBC05" />
      <Path d="M12 5.4c1.7 0 3.2.58 4.45 1.6l2.85-2.85A10 10 0 0 0 3.15 7.35l3.3 2.4A6 6 0 0 1 12 5.4Z" fill="#EA4335" />
    </Svg>
  );
}

export function CheckGlyph({ size = 12, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return <Svg width={size} height={size} viewBox="0 0 12 12"><Path d="M2.5 6.2 5 8.6l4.5-5" fill="none" stroke={color} strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" /></Svg>;
}

export function BackGlyph({ size = 22, color = '#18181C' }: { size?: number; color?: string }) {
  return <Svg width={size} height={size} viewBox="0 0 22 22"><Path d="M13.5 4.5 7.5 11l6 6.5" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" /></Svg>;
}

export function ChevronGlyph({ size = 14, color = '#A4A8B3' }: { size?: number; color?: string }) {
  return <Svg width={size} height={size} viewBox="0 0 14 14"><Path d="m5.25 3.5 3.5 3.5-3.5 3.5" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" /></Svg>;
}

export function WifiOffGlyph() {
  return <Svg width={18} height={18} viewBox="0 0 20 20"><Path d="M2.2 3.2 17 18M3.5 7.2A11.2 11.2 0 0 1 14.7 6M6.2 10.2a7.2 7.2 0 0 1 5.7-.7M8.8 13.3c.7-.2 1.4-.1 2 .2" fill="none" stroke="#FFFFFF" strokeWidth={1.8} strokeLinecap="round" /><Circle cx={10} cy={16.2} r={1.1} fill="#FFFFFF" /></Svg>;
}
