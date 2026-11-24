import React, { useState } from 'react';
import { Image, StyleSheet, View, type StyleProp, type TextStyle, type ViewStyle } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { appColor, ft, webColor } from '@/ui/theme';
import { Keep } from './Dark';

export interface AvatarProps {
  /** 이름 (첫 글자를 보여 줌) */
  name: string;
  /** 사진 주소 (웹 원본: 사진이 있으면 사진). 불러오지 못하면 이니셜 */
  photoUrl?: string | null;
  size: number;
  /** app: 연보라 바탕 + 보라 글자 (원본 .av) · web: #F3F1EF 바탕 + 검정 글자 (원본 overlays.tsx Avatar) */
  variant: 'app' | 'web';
  /** 글자 크기 (없으면 app 13·size 32 기준 비율, web size × .45) */
  fontSize?: number;
  /** 화면이 원래 쓰던 동그라미 모양 · 글자 모양을 그대로 쓰고 싶을 때 (앱 MY · 내 프로필) */
  boxStyle?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
}

export function Avatar({ name, photoUrl, size, variant, fontSize, boxStyle, textStyle }: AvatarProps) {
  const r = size / 2;
  /* 사진을 못 불러오면(주소 만료 · 막힘) 이니셜로. 주소가 바뀌면 다시 시도 */
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const url = photoUrl && photoUrl !== failedUrl ? photoUrl : null;
  if (url)
    return (
      /* 이니셜과 같은 동그라미 자리 (boxStyle 의 여백 · 정렬도 그대로) */
      <Keep style={[st.box, { width: size, height: size, borderRadius: r }, boxStyle]}>
        <Image
          source={{ uri: url }}
          style={{ width: size, height: size, borderRadius: r }}
          accessibilityIgnoresInvertColors
          onError={() => setFailedUrl(url)}
        />
      </Keep>
    );
  const fs = fontSize ?? (variant === 'app' ? Math.round((size * 13) / 32) : size * 0.45);
  const app = variant === 'app';
  return (
    <View style={[st.box, { width: size, height: size, borderRadius: r, backgroundColor: app ? appColor.accentSoft : '#F3F1EF' }, boxStyle]}>
      <Text style={[ft(fs), { fontWeight: '700', color: app ? appColor.deepPurple : webColor.ink }, textStyle]} numberOfLines={1}>
        {name.trim().slice(0, 1) || '?'}
      </Text>
    </View>
  );
}

const st = StyleSheet.create({ box: { alignItems: 'center', justifyContent: 'center', overflow: 'hidden' } });
