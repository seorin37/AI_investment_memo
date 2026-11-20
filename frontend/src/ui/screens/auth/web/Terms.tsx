import React, { useCallback } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { BackGlyph, CheckGlyph, ChevronGlyph } from '@/ui/screens/auth/AuthGlyphs';
import { allTermsChecked, requiredComplete, type TermsProps } from '@/ui/screens/auth/Auth.types';
import { LegalDocumentView } from '@/ui/screens/auth/LegalDocumentView';
import { ConfirmDialog } from '@/ui/shared/ConfirmDialog';
import { fpx, webTracking } from '@/ui/theme';

import { useEscape } from './authKeyboard.web';

export function WebTerms(p: TermsProps) {
  const all = allTermsChecked(p.items, p.checked);
  const ready = requiredComplete(p.items, p.checked);
  const escape = useCallback(() => {
    if (p.document) p.onCloseDocument();
    else if (p.leave_open) p.onCancelLeave();
    else p.onBack();
  }, [p]);
  useEscape(escape);
  return (
    <View style={st.screen}>
      <View style={st.card}>
        {p.document ? (
          <View style={st.docPane}>
            <View style={st.docHeader}>
              <Pressable onPress={p.onCloseDocument} style={st.back} accessibilityLabel="약관으로 돌아가기"><BackGlyph /></Pressable>
              <Text style={st.docTitle}>{p.document.title}</Text>
            </View>
            <View style={st.docBody}><LegalDocumentView html={p.document.html} variant="web" /></View>
            <Pressable onPress={p.onCloseDocument} style={st.docClose}><Text style={st.docCloseText}>닫기</Text></Pressable>
          </View>
        ) : (
          <>
            <View style={st.top}>
              <Pressable onPress={p.onBack} style={st.back} accessibilityLabel="뒤로"><BackGlyph /></Pressable>
              <View style={st.progress}><View style={[st.progressDot, st.progressOn]} /><View style={st.progressDot} /><View style={st.progressDot} /></View>
            </View>
            <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={st.content}>
              <Text style={st.title}>memo&apos;s를 시작하기 전에{String.fromCharCode(10)}확인해 주세요</Text>
              <Text style={st.sub}>필수 항목을 확인하고 시작해요.</Text>
              <Pressable onPress={p.onToggleAll} style={st.all} accessibilityRole="checkbox" accessibilityState={{ checked: all }}>
                <View style={[st.check, all && st.checkOn]}>{all ? <CheckGlyph /> : null}</View>
                <Text style={st.allText}>필수 항목 모두 확인하기</Text>
              </Pressable>
              <View style={st.items}>
                {p.items.map((item) => {
                  const on = p.checked[item.key];
                  return (
                    <View key={item.key} style={st.item}>
                      <Pressable onPress={() => p.onToggle(item.key)} style={st.itemMain} accessibilityRole="checkbox" accessibilityState={{ checked: on }}>
                        <View style={[st.check, on && st.checkOn]}>{on ? <CheckGlyph /> : null}</View>
                        <Text style={st.itemText}>{item.label}</Text>
                      </Pressable>
                      {item.document ? <Pressable onPress={() => p.onOpenDocument(item.document!)} style={st.viewLink}><Text style={st.viewText}>보기</Text><ChevronGlyph /></Pressable> : null}
                    </View>
                  );
                })}
              </View>
              <Pressable onPress={() => p.onOpenDocument('privacy')} style={st.privacy}><Text style={st.privacyText}>개인정보 처리방침 확인하기</Text><ChevronGlyph color="#575B63" /></Pressable>
              <Text style={st.draft}>이 화면의 약관 문구는 초안이에요 · 출시 전 법 검토 필요</Text>
              <Pressable disabled={!ready} onPress={p.onContinue} style={[st.cta, ready && st.ctaOn]}><Text style={st.ctaText}>동의하고 시작하기</Text></Pressable>
            </ScrollView>
          </>
        )}
      </View>
      <ConfirmDialog
        open={p.leave_open}
        variant="web"
        title="가입을 그만둘까요?"
        body="지금 나가면 동의한 내용은 저장되지 않아요. 다음에 로그인하면 이어서 할 수 있어요."
        cancelLabel="계속하기"
        confirmLabel="그만두기"
        onCancel={p.onCancelLeave}
        onConfirm={p.onConfirmLeave}
      />
    </View>
  );
}

const st = StyleSheet.create({
  screen: { flex: 1, minHeight: 600, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FDFDFD', padding: 16 },
  card: { width: 640, maxWidth: '100%', minHeight: 610, maxHeight: 760, borderRadius: 24, borderWidth: 1, borderColor: '#E5E8EB', backgroundColor: '#FFFFFF', paddingHorizontal: 56, paddingTop: 24, paddingBottom: 32 },
  top: { height: 42, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  back: { width: 42, height: 42, marginLeft: -10, alignItems: 'center', justifyContent: 'center', borderRadius: 21 },
  progress: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  progressDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D5D8DD' },
  progressOn: { width: 18, backgroundColor: '#111111' },
  content: { paddingTop: 17 },
  title: { ...fpx(26, 35), color: '#18181C', fontWeight: '700', letterSpacing: webTracking(26) },
  sub: { ...fpx(14, 21), marginTop: 6, color: '#A4A8B3', letterSpacing: webTracking(14) },
  all: { minHeight: 58, marginTop: 24, borderRadius: 16, backgroundColor: '#F2F2F5', paddingHorizontal: 16, paddingVertical: 14, flexDirection: 'row', alignItems: 'center', gap: 12 },
  check: { width: 26, height: 26, borderRadius: 13, backgroundColor: '#D5D8DD', alignItems: 'center', justifyContent: 'center' },
  checkOn: { backgroundColor: '#111111' },
  allText: { ...fpx(17, 26), color: '#18181C', fontWeight: '700' },
  items: { marginTop: 8 },
  item: { minHeight: 54, flexDirection: 'row', alignItems: 'center', paddingVertical: 14, paddingLeft: 5 },
  itemMain: { minWidth: 0, flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12 },
  itemText: { ...fpx(15, 23), flex: 1, color: '#2E2E38', letterSpacing: webTracking(15) },
  viewLink: { minHeight: 40, paddingLeft: 12, flexDirection: 'row', alignItems: 'center', gap: 2 },
  viewText: { ...fpx(13, 20), color: '#A4A8B3' },
  privacy: { alignSelf: 'center', marginTop: 24, flexDirection: 'row', alignItems: 'center', gap: 2 },
  privacyText: { ...fpx(14, 21), color: '#575B63', fontWeight: '500' },
  draft: { ...fpx(13, 20), marginTop: 4, color: '#A4A8B3', textAlign: 'center' },
  cta: { minHeight: 56, marginTop: 14, borderRadius: 16, backgroundColor: '#D0D3D9', alignItems: 'center', justifyContent: 'center' },
  ctaOn: { backgroundColor: '#111111' },
  ctaText: { ...fpx(17, 26), color: '#FFFFFF', fontWeight: '700' },
  docPane: { flex: 1 },
  docHeader: { height: 42, flexDirection: 'row', alignItems: 'center', gap: 1 },
  docTitle: { ...fpx(17, 26), color: '#18181C', fontWeight: '700' },
  docBody: { height: 520, marginTop: 4 },
  docClose: { minHeight: 56, marginTop: 10, borderRadius: 16, backgroundColor: '#111111', alignItems: 'center', justifyContent: 'center' },
  docCloseText: { ...fpx(17, 26), color: '#FFFFFF', fontWeight: '700' },
});
