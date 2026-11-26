import React from 'react';
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { NudgeArrow, NudgeCross, NudgeSpark } from '@/ui/icons/MemoGlyphs';
import { fpx } from '@/ui/theme';

/**
 * 앱 넛지 알약 — NudgePill.tsx(웹과 같이 씀)와 같고, 문구가 길면 2줄까지 (한 줄일 때 높이 48 그대로).
 * 원본 app.css .mx-nudge: 최소 높이 48 · 최대 380 · 라운드 999 · #15171A · 그림자 0 12 30 .25 · 글 15/23 700 · 가는 줄 1×20 흰 .2 · 닫기 44.
 * NudgePill.tsx 가 바뀌면 같이 맞출 것.
 */
export function NudgePill({ text, onGo, onClose, style }: { text: string; onGo: () => void; onClose: () => void; style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[st.pill, style]}>
      <Pressable onPress={onGo} accessibilityRole="button" style={st.go}>
        <NudgeSpark />
        <Text style={st.t} numberOfLines={2}>
          {text}
        </Text>
        <NudgeArrow />
      </Pressable>
      <View style={st.sep} />
      <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="제안 닫기" style={st.x}>
        <NudgeCross />
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  pill: { flexDirection: 'row', alignItems: 'center', minHeight: 48, maxWidth: 380, borderRadius: 999, backgroundColor: '#15171A', shadowColor: '#14171A', shadowOpacity: 0.25, shadowRadius: 30, shadowOffset: { width: 0, height: 12 }, elevation: 10 },
  go: { flexShrink: 1, minWidth: 0, minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: 8, paddingLeft: 16, paddingRight: 12, paddingVertical: 6 },
  t: { flexShrink: 1, ...fpx(15, 23), fontWeight: '700', color: '#FFFFFF', letterSpacing: -0.2 },
  sep: { width: 1, height: 20, backgroundColor: 'rgba(255,255,255,0.2)' },
  x: { width: 44, minHeight: 48, alignSelf: 'stretch', alignItems: 'center', justifyContent: 'center' },
});
