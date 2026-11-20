import React from 'react';
import { Image, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { appColor, ft, webColor } from '@/ui/theme';
import { Keep } from './Dark';

export interface AvatarProps {
  /** 이름 (첫 글자를 보여 줌) */
  name: string;
  /** 사진 주소 (웹 원본: 사진이 있으면 사진) */
  photoUrl?: string | null;
  size: number;
  /** app: 연보라 바탕 + 보라 글자 (원본 .av) · web: #F3F1EF 바탕 + 검정 글자 (원본 overlays.tsx Avatar) */
  variant: 'app' | 'web';
  /** 글자 크기 (없으면 app 13·size 32 기준 비율, web size × .45) */
  fontSize?: number;
}

export function Avatar({ name, photoUrl, size, variant, fontSize }: AvatarProps) {
  const r = size / 2;
  if (photoUrl)
    return (
      <Keep>
        <Image source={{ uri: photoUrl }} style={{ width: size, height: size, borderRadius: r }} accessibilityIgnoresInvertColors />
      </Keep>
    );
  const fs = fontSize ?? (variant === 'app' ? Math.round((size * 13) / 32) : size * 0.45);
  const app = variant === 'app';
  return (
    <View style={[st.box, { width: size, height: size, borderRadius: r, backgroundColor: app ? appColor.accentSoft : '#F3F1EF' }]}>
      <Text style={[ft(fs), { fontWeight: '700', color: app ? appColor.deepPurple : webColor.ink }]} numberOfLines={1}>
        {name.trim().slice(0, 1) || '?'}
      </Text>
    </View>
  );
}

const st = StyleSheet.create({ box: { alignItems: 'center', justifyContent: 'center', overflow: 'hidden' } });
