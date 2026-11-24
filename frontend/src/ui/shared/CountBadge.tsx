import React from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { appColor, ft } from '@/ui/theme';

/**
 * 빨간 숫자 배지 — 원본 앱 탭바 .tbadge (18×18 · 라운드 9 · 흰 테두리 2 · 11px 700) /
 * 웹 종 버튼 배지 (h18 min-w18 · 테두리 2 흰색 · #E5484D · 11px bold · 좌우 4)
 * 0 이면 그리지 않음.
 */
export function CountBadge({ count, style, borderColor = '#FFFFFF' }: { count: number; style?: StyleProp<ViewStyle>; borderColor?: string }) {
  if (!count) return null;
  return (
    <View style={[st.b, { borderColor }, style]} pointerEvents="none">
      <Text style={st.t}>{count}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  b: { minWidth: 18, height: 18, paddingHorizontal: 4, borderRadius: 9, borderWidth: 2, backgroundColor: appColor.red, alignItems: 'center', justifyContent: 'center' },
  /* 원본 leading-none · 18 안에 글자 11 (테두리 안 14) */
  t: { ...ft(11, 1), fontWeight: '700', color: '#FFFFFF', textAlign: 'center' },
});
