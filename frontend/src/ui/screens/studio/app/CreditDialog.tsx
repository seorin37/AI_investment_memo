import React from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { FadeIn } from '@/ui/motion/Reveal';
import { DarkLayer, SCRIM_DARK, useDark } from '@/ui/shared/Dark';
import { appColor, ft } from '@/ui/theme';

/**
 * 앱 '크레딧을 다 썼어요' 창 — 사용량을 다 쓴 뒤 오디오 · 보고서 · 실험 만들기를 누르면 먼저 뜸.
 * 문구 · 버튼 · 동작은 웹 WebCreditPopup((main)/_layout.tsx) 그대로, 모양은 앱 확인창(ConfirmDialog app)과 같게.
 * 플랜별: 무료 → [닫기][PLUS 살펴보기] + '이번만 크레딧 충전하기' · PLUS → [닫기][크레딧 충전하기] + 'PRO 살펴보기' · PRO → [닫기][크레딧 충전하기]
 */
export function AppCreditDialog({ open, plan = 'free', nextName, nextCredits, packLabel, onClose, onPlan, onCharge }: { open: boolean; plan?: string; nextName?: string; nextCredits?: number; packLabel?: string; onClose: () => void; onPlan: () => void; onCharge: () => void }) {
  const dark = useDark();
  if (!open) return null;
  const free = plan !== 'plus' && plan !== 'pro';
  const title = free ? '이번 달 무료 크레딧을 다 썼어요' : '이번 달 크레딧을 다 썼어요';
  const up = nextName && nextCredits ? `${nextName}는 매달 ${nextCredits} 크레딧이에요. ` : '';
  const pack = packLabel ? `추가 크레딧은 ${packLabel}이에요. ` : '';
  const body = `${free ? up : plan === 'plus' ? pack + up : pack}이미 만든 항목과 오늘의 퀴즈는 계속 쓸 수 있어요.`;
  return (
    <Modal transparent visible animationType="fade" onRequestClose={onClose} statusBarTranslucent>
      <DarkLayer>
        <View style={[st.scrim, { backgroundColor: dark ? SCRIM_DARK : 'rgba(12,12,22,0.4)' }]}>
          <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="닫기" />
          <FadeIn>
            <View style={st.box} accessibilityViewIsModal accessibilityRole="alert">
              <Text style={st.t}>{title}</Text>
              <Text keepAll style={st.b}>{body}</Text>
              <View style={st.btns}>
                <Pressable onPress={onClose} accessibilityRole="button" style={[st.btn, { backgroundColor: appColor.sf }]}>
                  <Text style={st.btnT}>닫기</Text>
                </Pressable>
                <Pressable onPress={free ? onPlan : onCharge} accessibilityRole="button" style={[st.btn, { backgroundColor: appColor.ink }]}>
                  <Text style={[st.btnT, { color: '#FFFFFF' }]}>{free ? `${nextName ?? 'PLUS'} 살펴보기` : '크레딧 충전하기'}</Text>
                </Pressable>
              </View>
              {free || plan === 'plus' ? (
                <Pressable onPress={free ? onCharge : onPlan} accessibilityRole="button" hitSlop={6} style={st.link}>
                  <Text style={st.linkT}>{free ? '이번만 크레딧 충전하기' : `${nextName ?? 'PRO'} 살펴보기`}</Text>
                </Pressable>
              ) : null}
            </View>
          </FadeIn>
        </View>
      </DarkLayer>
    </Modal>
  );
}

const st = StyleSheet.create({
  scrim: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 16 },
  box: { width: 320, maxWidth: '100%', borderRadius: 22, backgroundColor: appColor.surface, paddingTop: 22, paddingHorizontal: 20, paddingBottom: 16 },
  t: { ...ft(17), fontWeight: '700', color: appColor.ink, marginBottom: 6 },
  b: { ...ft(15, 1.6), color: appColor.ink2, marginBottom: 18 },
  btns: { flexDirection: 'row', gap: 8 },
  btn: { flex: 1, minHeight: 46, borderRadius: 12, alignItems: 'center', justifyContent: 'center', paddingVertical: 12 },
  btnT: { ...ft(15.5), fontWeight: '700', color: appColor.ink },
  link: { alignSelf: 'center', marginTop: 12, paddingVertical: 4 },
  linkT: { ...ft(15), fontWeight: '700', color: '#6B7079', textDecorationLine: 'underline' },
});
