import React from 'react';
import { Image, type ImageStyle, type StyleProp } from 'react-native';
import { APP_ICONS } from './appIcons.data';
import { LOGOS } from './logo.data';
import { SvgIcon, type SvgIconProps } from './SvgIcon';
import { WEB_ICONS } from './webIcons.data';

export type AppIconName = keyof typeof APP_ICONS;
export type WebIconName = keyof typeof WEB_ICONS;

/**
 * 앱 원본 아이콘 (원본UI/app 화면 HTML·app.js 의 svg)
 * 모양이 같은 svg 는 하나로 묶었기 때문에, 기본 색·크기는 원본에서 처음 나온 곳의 값이다.
 * 쓰는 곳의 원본 색·크기가 다르면 size · color 를 꼭 넘길 것.
 */
export function AppIcon({ name, ...p }: SvgIconProps & { name: AppIconName }) {
  return <SvgIcon def={APP_ICONS[name]} {...p} />;
}

/** 웹 원본 아이콘 (fig.tsx Icon 세트 + 화면 tsx 인라인 svg) */
export function WebIcon({ name, ...p }: SvgIconProps & { name: WebIconName }) {
  return <SvgIcon def={WEB_ICONS[name]} {...p} />;
}

/** MEMO'S 글자 로고 — app: 앱 홈 머리 (110×35 원본) · web: 웹 kit.tsx Logo (LOGO_D) */
export function Logo({ kind, ...p }: SvgIconProps & { kind: 'app' | 'web' }) {
  return <SvgIcon def={LOGOS[kind]} {...p} />;
}

/** 웹 사이드바 워드마크 이미지 (원본 assets_wm.ts PNG, 117×72) */
export function WebWordmark({ width = 117, height = 72, style }: { width?: number; height?: number; style?: StyleProp<ImageStyle> }) {
  return <Image source={require('./wordmark-web.png')} style={[{ width, height }, style]} resizeMode="stretch" accessibilityLabel="MEMO'S" />;
}
