import React from 'react';
import { Pressable, type StyleProp, type ViewStyle } from 'react-native';
import { AppIcon, type AppIconName, WebIcon, type WebIconName } from '@/ui/icons/Icon';
import { webColor } from '@/ui/theme';

type Common = {
  label: string;
  onPress?: () => void;
  /** 버튼 크기 (원본 앱 .ib 40·42 · 웹 32·40) */
  size: number;
  iconSize?: number;
  color?: string;
  style?: StyleProp<ViewStyle>;
  children?: React.ReactNode;
  disabled?: boolean;
};

/** 앱 둥근 아이콘 버튼 (원본 .ib/.iconbtn: 정사각 · 라운드 절반 · 바탕 없음) — 누르는 영역은 44 이상으로 */
export function AppIconButton({ label, onPress, size, icon, iconSize, color, style, children, disabled }: Common & { icon?: AppIconName }) {
  const slop = Math.max(0, (44 - size) / 2);
  return (
    <Pressable onPress={onPress} disabled={disabled} accessibilityRole="button" accessibilityLabel={label} hitSlop={slop} style={({ pressed }) => [{ width: size, height: size, borderRadius: size / 2, alignItems: 'center', justifyContent: 'center', backgroundColor: pressed ? 'rgba(0,0,0,0.05)' : 'transparent' }, style]}>
      {icon ? <AppIcon name={icon} size={iconSize} color={color} /> : null}
      {children}
    </Pressable>
  );
}

/** 웹 네모 아이콘 버튼 (원본: 라운드 8 · hover #F9F9F9) */
export function WebIconButton({ label, onPress, size, icon, iconSize, color, style, children, disabled, radius = 8, on }: Common & { icon?: WebIconName; radius?: number; on?: boolean }) {
  return (
    <Pressable onPress={onPress} disabled={disabled} accessibilityRole="button" accessibilityLabel={label} style={({ hovered }: { hovered?: boolean; pressed: boolean }) => [{ width: size, height: size, borderRadius: radius, alignItems: 'center', justifyContent: 'center', backgroundColor: on ? webColor.selBg : hovered ? webColor.hover : 'transparent' }, style]}>
      {icon ? <WebIcon name={icon} size={iconSize} color={color} /> : null}
      {children}
    </Pressable>
  );
}
