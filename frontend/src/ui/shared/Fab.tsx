import React from 'react';
import { StyleSheet, type StyleProp, type ViewStyle } from 'react-native';
import { AppIcon } from '@/ui/icons/Icon';
import { PressScale } from '@/ui/motion/PressScale';
import { appColor, shadow } from '@/ui/theme';

/**
 * 앱 + 버튼 (원본 memo.html .fab: 58 · 라운드 29 · #8569E3 · 그림자 0 10px 22px -8px rgba(106,66,171,.6) · 흰 + 26
 * 자리: 오른쪽 18 · 아래 16 — 위치는 부모(style)가 정함). 부채꼴(#011) 펼침은 ③ 메모 보드에서.
 */
export function Fab({ onPress, label = '새로 만들기', style }: { onPress: () => void; label?: string; style?: StyleProp<ViewStyle> }) {
  return (
    <PressScale onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={[st.fab, style]}>
      <AppIcon name="plusWhite" size={26} color="#FFFFFF" />
    </PressScale>
  );
}

const st = StyleSheet.create({
  fab: { width: 58, height: 58, borderRadius: 29, backgroundColor: appColor.accent, alignItems: 'center', justifyContent: 'center', ...shadow.fab },
});
