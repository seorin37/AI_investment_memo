import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { AppPlug } from '@/ui/icons/BoardGlyphs';
import { appColor, ft } from '@/ui/theme';
import { Sheet } from './Sheet';

/**
 * 앱 AI 연결 해제 확인 (원본 memo.html 12.2 askOff · .gsh: 안쪽 좌우 18 · 아래 22
 * 그림 44 라운드 14 #FFE9EF (빨간 플러그 20) · 제목 19px · 종목 칩 + 메모 제목 13.5px #575B63
 * 목록 #F6F6F8 라운드 14 (✕ 빨강 · ✓ 초록 13.5px) · [연결 해제] 빨강 52 · [취소] 회색)
 */
export function AiOffSheet({ open, stockName, title, itemCount, onConfirm, onClose }: { open: boolean; stockName: string; title: string; itemCount: number; onConfirm: () => void; onClose: () => void }) {
  return (
    <Sheet open={open} onClose={onClose} label="AI 연결 해제 확인">
      <View style={st.body}>
        <View style={st.ic}>
          <AppPlug size={20} color={appColor.red} stroke={2.4} />
        </View>
        <Text style={st.h}>이 메모의 AI 연결을 해제할까요?</Text>
        <View style={st.mc}>
          <View style={st.chip}>
            <Text style={st.chipT}>{stockName}</Text>
          </View>
          <Text style={st.mcT} numberOfLines={1}>
            {title}
          </Text>
        </View>
        <View style={st.ul}>
          <Li mark="✕" color={appColor.red} text={`추적 항목 ${itemCount}개에 대한 새 소식 연결을 멈춰요`} />
          <Li mark="✓" color="#2FAE68" text="메모는 일반 메모로 계속 볼 수 있어요" />
          <Li mark="✓" color="#2FAE68" text="이미 받은 업데이트는 그대로 남아요" />
        </View>
        <Pressable onPress={onConfirm} accessibilityRole="button" style={({ pressed }) => [st.bt, st.red, pressed && st.press]}>
          <Text style={st.btT}>연결 해제</Text>
        </Pressable>
        <Pressable onPress={onClose} accessibilityRole="button" style={({ pressed }) => [st.bt, st.gray, pressed && st.press]}>
          <Text style={[st.btT, { color: appColor.ink }]}>취소</Text>
        </Pressable>
      </View>
    </Sheet>
  );
}

function Li({ mark, color, text }: { mark: string; color: string; text: string }) {
  return (
    <View style={st.li}>
      <Text style={[st.liT, { color }]}>{mark}</Text>
      <Text style={[st.liT, st.flex]}>{text}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  flex: { flex: 1 },
  body: { paddingHorizontal: 18, paddingTop: 2, paddingBottom: 8 },
  ic: { width: 44, height: 44, borderRadius: 14, backgroundColor: '#FFE9EF', alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  h: { ...ft(19), fontWeight: '700', color: appColor.ink, marginBottom: 6 },
  mc: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12 },
  chip: { backgroundColor: '#EEF0F3', borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 },
  chipT: { ...ft(11.5), fontWeight: '700', color: appColor.ink2 },
  mcT: { ...ft(13.5), color: appColor.ink2, flexShrink: 1 },
  ul: { marginBottom: 14, paddingVertical: 12, paddingHorizontal: 14, backgroundColor: '#F6F6F8', borderRadius: 14 },
  li: { flexDirection: 'row', gap: 8, paddingVertical: 4 },
  liT: { ...ft(13.5, 1.5), color: appColor.ink },
  bt: { minHeight: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center', paddingVertical: 14, marginTop: 8 },
  red: { backgroundColor: appColor.red },
  gray: { backgroundColor: '#ECEDF1' },
  press: { transform: [{ scale: 0.97 }] },
  btT: { ...ft(15.5), fontWeight: '700', color: '#FFFFFF' },
});
