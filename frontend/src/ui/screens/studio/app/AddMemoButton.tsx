import React from 'react';
import { Pressable, StyleSheet } from 'react-native';
import { Text } from '@/components/ui/AppText';

/** [메모에 추가] 32 · 라운드 10 · 검정 → 추가하면 '✓ 추가됨' (회색 · 못 누름) */
export function AddMemoButton({ added, onPress }: { added: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} disabled={added} accessibilityRole="button" accessibilityState={{ disabled: added }} style={[st.btn, added && st.off]}>
      <Text style={[st.t, added && st.offT]}>{added ? '✓ 추가됨' : '메모에 추가'}</Text>
    </Pressable>
  );
}

const st = StyleSheet.create({
  btn: { height: 32, paddingHorizontal: 12, borderRadius: 10, backgroundColor: '#16171A', justifyContent: 'center' },
  t: { fontSize: 12.5, lineHeight: 17, fontWeight: '700', color: '#FFFFFF' },
  off: { backgroundColor: '#F3F4F6' },
  offT: { color: '#9A9EA7' },
});
