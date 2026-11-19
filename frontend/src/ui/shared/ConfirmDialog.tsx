import React from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { FadeIn } from '@/ui/motion/Reveal';
import { appColor, fpx, ft, webColor } from '@/ui/theme';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  body?: string;
  cancelLabel?: string;
  confirmLabel: string;
  /** 위험한 동작 (웹: 빨강 #E45D6A 버튼) */
  danger?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  /**
   * app: 원본 home.html .dialog (막 rgba(12,12,22,.4) · 320 · 라운드 22 · 안쪽 22/20/16 · 제목 17px 700 · 본문 14px/1.6 #575B63
   *      버튼 46 라운드 12 · 취소 #F2F2F5 · 확인 #16171A 흰 글자 15px 700)
   * web: 원본 overlays.tsx ConfirmDanger (400 · 라운드 28 · 테두리 #E8ECF3 · 안쪽 28/27 · 제목 22/31 bold · 본문 15/23 #747D8D
   *      버튼 48 라운드 12 · 취소 #F2F3F4 · 확인 #E45D6A 15/23 medium)
   */
  variant: 'app' | 'web';
}

export function ConfirmDialog({ open, title, body, cancelLabel = '취소', confirmLabel, danger, onCancel, onConfirm, variant }: ConfirmDialogProps) {
  if (!open) return null;
  const app = variant === 'app';
  return (
    <Modal transparent visible animationType="fade" onRequestClose={onCancel} statusBarTranslucent>
      <View style={[st.scrim, { backgroundColor: app ? 'rgba(12,12,22,0.4)' : 'rgba(0,0,0,0.45)' }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onCancel} accessibilityLabel="닫기" />
        <FadeIn>
          <View style={app ? st.app : st.web} accessibilityViewIsModal accessibilityRole="alert">
            <View style={app ? null : st.webText}>
              <Text style={app ? st.appT : st.webT}>{title}</Text>
              {body ? <Text style={app ? st.appB : st.webB}>{body}</Text> : null}
            </View>
            <View style={app ? st.appBtns : st.webBtns}>
              <Pressable onPress={onCancel} accessibilityRole="button" style={[app ? st.appBtn : st.webBtn, { backgroundColor: app ? appColor.sf : webColor.chip }]}>
                <Text style={app ? st.appBtnT : st.webBtnT}>{cancelLabel}</Text>
              </Pressable>
              <Pressable onPress={onConfirm} accessibilityRole="button" style={[app ? st.appBtn : st.webBtn, { backgroundColor: app ? (danger ? appColor.red : appColor.ink) : danger ? webColor.badge : webColor.ink }]}>
                <Text style={[app ? st.appBtnT : st.webBtnT, { color: '#FFFFFF' }]}>{confirmLabel}</Text>
              </Pressable>
            </View>
          </View>
        </FadeIn>
      </View>
    </Modal>
  );
}

const st = StyleSheet.create({
  scrim: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 16 },
  app: { width: 320, maxWidth: '100%', borderRadius: 22, backgroundColor: appColor.surface, paddingTop: 22, paddingHorizontal: 20, paddingBottom: 16 },
  appT: { ...ft(17), fontWeight: '700', color: appColor.ink, marginBottom: 6 },
  appB: { ...ft(14, 1.6), color: appColor.ink2, marginBottom: 18 },
  appBtns: { flexDirection: 'row', gap: 8 },
  appBtn: { flex: 1, minHeight: 46, borderRadius: 12, alignItems: 'center', justifyContent: 'center', paddingVertical: 12 },
  appBtnT: { ...ft(15), fontWeight: '700', color: appColor.ink },
  web: { width: 400, maxWidth: '100%', gap: 24, borderRadius: 28, borderWidth: 1, borderColor: webColor.line3, backgroundColor: webColor.surface, paddingHorizontal: 28, paddingVertical: 27, shadowColor: '#14171C', shadowOpacity: 0.16, shadowRadius: 40, shadowOffset: { width: 0, height: 24 }, elevation: 12 },
  webText: { gap: 8 },
  webT: { ...fpx(22, 31), fontWeight: '700', color: webColor.ink },
  webB: { ...fpx(15, 23), color: '#747D8D' },
  webBtns: { flexDirection: 'row', gap: 8, justifyContent: 'flex-end' },
  webBtn: { flex: 1, minHeight: 48, borderRadius: 12, alignItems: 'center', justifyContent: 'center', paddingVertical: 12 },
  webBtnT: { ...fpx(15, 23), fontWeight: '500', color: webColor.ink },
});
