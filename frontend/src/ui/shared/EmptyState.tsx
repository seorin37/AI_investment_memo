import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { fpx, ft, tw } from '@/ui/theme';

/**
 * 웹 빈 상태 (원본 kit.tsx Empty: 위아래 56 · 좌우 24 · 그림 상자 56 라운드 16 zinc-100 · 제목 17px bold (위 16)
 * 본문 14px/1.625 zinc-500 (위 6 · 최대 384) · 버튼 줄 (위 20 · 사이 8)).
 * 앱 빈 화면은 화면마다 그림·문구가 달라 각 화면 묶음에서 그림.
 */
export function EmptyState({ icon, title, body, children }: { icon: React.ReactNode; title: string; body: string; children?: React.ReactNode }) {
  return (
    <View style={st.wrap}>
      <View style={st.box}>{icon}</View>
      <Text style={st.t}>{title}</Text>
      <Text style={st.b}>{body}</Text>
      {children ? <View style={st.btns}>{children}</View> : null}
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { alignItems: 'center', paddingHorizontal: 24, paddingVertical: 56 },
  box: { width: 56, height: 56, borderRadius: 16, backgroundColor: tw.zinc100, alignItems: 'center', justifyContent: 'center' },
  t: { ...ft(17), fontWeight: '700', color: '#000000', marginTop: 16, textAlign: 'center' },
  b: { ...fpx(14, 22.75), color: tw.zinc500, marginTop: 6, maxWidth: 384, textAlign: 'center' },
  btns: { marginTop: 20, flexDirection: 'row', gap: 8 },
});
