import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { fpx, ft, webColor } from '@/ui/theme';

type HoverState = { pressed: boolean; hovered?: boolean };

/**
 * AI 사용량을 다 썼을 때 안내
 * app: 원본 memo.html .spb (라운드 16 · #FFF6E5 · 테두리 #F6E2B8 · 안쪽 14/14/12 · 제목 15px 800 #5C3800 + 멈춤 18 #B07800
 *      본문 13px 줄 1.6 #7A4B00 · 버튼 40 라운드 12 13.5px 800 — 크레딧 구매 #8A5A00 / 플랜 변경 흰 + 테두리 #F1D9A8)
 * web: 원본 x.tsx SpentBox (라운드 16 · #FFF4E5 · 20/16 · 제목 15/23 bold #7A4A00 · 본문 14/21 #8A5A00
 *      버튼 36 라운드 10 14 bold — 크레딧 구매 #15171A / 플랜 변경 흰 + 안쪽 1 #F1D9B3)
 */
/** onOff(2026-11-24): 'AI 연결 모두 끄기' 링크 (크레딧 0 · AI 연결 메모가 남아 있을 때 = 끄기 대기) */
export function SpentBox({ variant, title, body, onCredit, onPlan, onOff }: { variant: 'app' | 'web'; title: string; body: string; onCredit: () => void; onPlan: () => void; onOff?: () => void }) {
  if (variant === 'app')
    return (
      <View style={st.app}>
        <View style={st.appT}>
          <Svg width={18} height={18} viewBox="0 0 24 24" fill="none">
            <Path d="M9 6v12M15 6v12" stroke="#B07800" strokeWidth={2.4} strokeLinecap="round" />
          </Svg>
          <Text style={st.appTT}>{title}</Text>
        </View>
        <Text style={st.appP}>{body}</Text>
        <View style={st.appBs}>
          <Pressable onPress={onCredit} accessibilityRole="button" style={[st.appB, { backgroundColor: '#8A5A00' }]}>
            <Text style={[st.appBT, { color: '#FFFFFF' }]}>크레딧 구매</Text>
          </Pressable>
          <Pressable onPress={onPlan} accessibilityRole="button" style={[st.appB, st.appPln]}>
            <Text style={[st.appBT, { color: '#7A4B00' }]}>플랜 변경</Text>
          </Pressable>
        </View>
        {onOff ? (
          <Pressable onPress={onOff} accessibilityRole="button" style={st.off}>
            <Text style={st.offT}>AI 연결 모두 끄기</Text>
          </Pressable>
        ) : null}
      </View>
    );
  return (
    <View style={st.web}>
      <Text style={st.webT}>{title}</Text>
      <Text style={st.webP}>{body}</Text>
      <View style={st.webBs}>
        <Pressable onPress={onCredit} accessibilityRole="button" style={({ hovered }: HoverState) => [st.webB, { backgroundColor: hovered ? '#2A2A2A' : webColor.ink }]}>
          <Text style={[st.webBT, { color: '#FFFFFF' }]}>크레딧 구매</Text>
        </Pressable>
        <Pressable onPress={onPlan} accessibilityRole="button" style={({ hovered }: HoverState) => [st.webB, st.webPln, hovered && { backgroundColor: '#FFFAF2' }]}>
          <Text style={[st.webBT, { color: '#7A4A00' }]}>플랜 변경</Text>
        </Pressable>
        {onOff ? (
          <Pressable onPress={onOff} accessibilityRole="button" style={st.offW}>
            <Text style={st.offT}>AI 연결 모두 끄기</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  off: { alignSelf: 'center', paddingTop: 10, paddingHorizontal: 8 },
  offW: { justifyContent: 'center', paddingHorizontal: 8 },
  offT: { ...ft(13), fontWeight: '700', color: '#8A5A00', textDecorationLine: 'underline' },
  app: { borderRadius: 16, backgroundColor: '#FFF6E5', borderWidth: 1, borderColor: '#F6E2B8', paddingTop: 14, paddingHorizontal: 14, paddingBottom: 12 },
  appT: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  appTT: { ...ft(15), fontWeight: '800', color: '#5C3800' },
  appP: { ...ft(13, 1.6), color: '#7A4B00', marginTop: 6, marginBottom: 12 },
  appBs: { flexDirection: 'row', gap: 8 },
  appB: { flex: 1, minHeight: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center', paddingVertical: 10 },
  appPln: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#F1D9A8' },
  appBT: { ...ft(13.5), fontWeight: '800' },
  web: { width: '100%', gap: 4, borderRadius: 16, backgroundColor: '#FFF4E5', paddingHorizontal: 20, paddingVertical: 16 },
  webT: { ...fpx(15, 23), fontWeight: '700', color: '#7A4A00' },
  webP: { ...fpx(14, 21), color: '#8A5A00' },
  webBs: { marginTop: 8, flexDirection: 'row', gap: 8 },
  webB: { minHeight: 36, borderRadius: 10, paddingHorizontal: 14, justifyContent: 'center' },
  webPln: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#F1D9B3' },
  webBT: { ...fpx(14, 21), fontWeight: '700' },
});
