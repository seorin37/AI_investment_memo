import React from 'react';
import { StyleSheet, View } from 'react-native';
import { MiniInline } from '@/ui/screens/studio/app/MiniBar';
import { Text } from '@/components/ui/AppText';
import { PressScale } from '@/ui/motion/PressScale';
import { appColor, ft } from '@/ui/theme';

/** 새 메모 시트 아래: 안내 한 줄 · [취소] [저장] (앱 버튼 54 · 라운드 15) */
export function SheetActions({ note, ok, onCancel, onOk }: { note: string; ok: string; onCancel: () => void; onOk: () => void }) {
  return (
    <>
    <MiniInline beforeOpen={onCancel} />
    <View style={st.wrap}>
      <Text style={st.note}>{note}</Text>
      <View style={st.row}>
        <PressScale onPress={onCancel} accessibilityRole="button" style={[st.btn, st.gray]}><Text style={st.btnT}>취소</Text></PressScale>
        <View style={{ flex: 1 }}>
          <PressScale onPress={onOk} accessibilityRole="button" style={[st.btn, st.ink]}><Text style={[st.btnT, { color: '#FFFFFF' }]}>{ok}</Text></PressScale>
        </View>
      </View>
    </View>
    </>
  );
}

const st = StyleSheet.create({
  wrap: { paddingHorizontal: 16, paddingTop: 10, paddingBottom: 14, borderTopWidth: 1, borderTopColor: '#E6E8EC' },
  note: { ...ft(12.5), color: appColor.ink3, textAlign: 'center', marginBottom: 10 },
  row: { flexDirection: 'row', gap: 8 },
  btn: { height: 54, borderRadius: 15, paddingHorizontal: 24, alignItems: 'center', justifyContent: 'center' },
  gray: { backgroundColor: '#E6E8EC' },
  ink: { backgroundColor: appColor.ink },
  btnT: { ...ft(16), fontWeight: '800', color: appColor.ink },
});
