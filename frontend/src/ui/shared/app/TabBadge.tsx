import React from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { appColor, ft } from '@/ui/theme';

/**
 * 앱 탭바 숫자 배지 — shared/CountBadge 와 같은 모양(18 · 라운드 9 · 흰 테두리 2 · 11px 700), 99 넘으면 '99+'.
 * CountBadge 는 웹과 같이 써서 앱 것을 따로 둠. 0 이면 그리지 않음.
 */
export function TabBadge({ count, style }: { count: number; style?: StyleProp<ViewStyle> }) {
  if (!count) return null;
  return (
    <View style={[st.b, style]} pointerEvents="none">
      <Text style={st.t}>{count > 99 ? '99+' : count}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  b: { minWidth: 18, height: 18, paddingHorizontal: 4, borderRadius: 9, borderWidth: 2, borderColor: '#FFFFFF', backgroundColor: appColor.red, alignItems: 'center', justifyContent: 'center' },
  t: { ...ft(11, 1), fontWeight: '700', color: '#FFFFFF', textAlign: 'center' },
});
