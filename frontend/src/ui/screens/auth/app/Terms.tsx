import React, { useEffect } from 'react';
import { BackHandler, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { BackGlyph, CheckGlyph, ChevronGlyph } from '@/ui/screens/auth/AuthGlyphs';
import { allTermsChecked, requiredComplete, type TermsProps } from '@/ui/screens/auth/Auth.types';
import { LegalDocumentView } from '@/ui/screens/auth/LegalDocumentView';
import { ConfirmDialog } from '@/ui/shared/ConfirmDialog';
import { appColor, ft } from '@/ui/theme';

export function AppTerms(p: TermsProps) {
  const insets = useSafeAreaInsets();
  const all = allTermsChecked(p.items, p.checked);
  const ready = requiredComplete(p.items, p.checked);
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (p.document) p.onCloseDocument();
      else if (p.leave_open) p.onCancelLeave();
      else p.onBack();
      return true;
    });
    return () => sub.remove();
  }, [p]);
  if (p.document) {
    return (
      <View style={[st.screen, { paddingTop: insets.top }]}>
        <View style={st.docHeader}>
          <Pressable onPress={p.onCloseDocument} style={st.back} accessibilityLabel="약관으로 돌아가기"><BackGlyph /></Pressable>
          <Text style={st.docTitle}>{p.document.title}</Text>
        </View>
        <LegalDocumentView html={p.document.html} variant="app" />
        <View style={[st.docBottom, { paddingBottom: Math.max(insets.bottom, 16) }]}>
          <Pressable onPress={p.onCloseDocument} style={st.docClose}><Text style={st.docCloseText}>닫기</Text></Pressable>
        </View>
      </View>
    );
  }
  return (
    <View style={[st.screen, { paddingTop: insets.top }]}>
      {/* 아래 고정 영역 높이만큼 여백. 저장 실패 줄이 보일 때만 그 높이(ERROR_H)를 더해 마지막 약관이 가려지지 않게 */}
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={[st.content, { paddingBottom: 146 + insets.bottom + (p.error ? ERROR_H : 0) }]}>
        <View style={st.top}>
          <Pressable onPress={p.onBack} style={st.back} accessibilityLabel="뒤로"><BackGlyph /></Pressable>
          <View style={st.progress}><View style={[st.progressDot, st.progressOn]} /><View style={st.progressDot} /><View style={st.progressDot} /></View>
        </View>
        <Text style={st.title}>memo&apos;s를 시작하기 전에{String.fromCharCode(10)}확인해 주세요</Text>
        <Text style={st.sub}>필수 항목을 확인하고 시작해요.</Text>
        <Pressable onPress={p.onToggleAll} style={[st.all, all && st.allOn]} accessibilityRole="checkbox" accessibilityState={{ checked: all }}>
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
                  <Text keepAll numberOfLines={2} style={st.itemText}>{item.label}</Text>
                </Pressable>
                {item.document ? <Pressable onPress={() => p.onOpenDocument(item.document!)} style={st.viewLink} hitSlop={{ top: 4, bottom: 4 }}><Text style={st.viewText}>보기</Text><ChevronGlyph /></Pressable> : null}
              </View>
            );
          })}
        </View>
      </ScrollView>
      <View style={[st.bottom, { paddingBottom: Math.max(insets.bottom, 30) }]}>
        <Pressable onPress={() => p.onOpenDocument('privacy')} style={st.privacy}><Text style={st.privacyText}>개인정보 처리방침 확인하기</Text><ChevronGlyph color={appColor.deepPurple} /></Pressable>
        {p.error ? <View accessibilityRole="alert" style={st.errorToast}><Text style={st.errorText}>{p.error}</Text></View> : null}
        <Pressable disabled={!ready || !!p.saving} onPress={p.onContinue} style={[st.cta, ready && !p.saving && st.ctaOn]}>
          <Text style={st.ctaText}>동의하고 시작하기</Text>
        </Pressable>
      </View>
      <ConfirmDialog
        open={p.leave_open}
        variant="app"
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

/** 저장 실패 줄이 아래 고정 영역에 더하는 높이: 위 14 + 상자(글자 13 · 위아래 10) 약 40 + 아래 8 + 간격 2 */
const ERROR_H = 64;

const st = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { paddingHorizontal: 16 },
  /* 원본 .hd 56 · .ib 42 (화면 왼쪽 6) · .prog margin-right 16 */
  top: { height: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  back: { width: 42, height: 42, marginLeft: -10, alignItems: 'center', justifyContent: 'center', borderRadius: 21 },
  progress: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  progressDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D5D8DD' },
  progressOn: { width: 18, backgroundColor: appColor.accent },
  /* .tt 25 / 1.4 · 800 · margin 10 18 6 · .ts 14 / 1.6 ink3 · margin-bottom 24 */
  title: { fontSize: 25, lineHeight: 35, marginTop: 10, marginHorizontal: 2, color: '#16171A', fontWeight: '800' },
  sub: { fontSize: 15, lineHeight: 24, marginTop: 6, marginHorizontal: 2, color: '#6B7079' },
  /* .all 58 · r16 · #F4F0FF · gap 12 · 16.5 800 */
  all: { minHeight: 58, marginTop: 24, borderRadius: 16, backgroundColor: '#F4F0FF', paddingHorizontal: 16, paddingVertical: 14, flexDirection: 'row', alignItems: 'center', gap: 12 },
  allOn: {},
  check: { width: 26, height: 26, borderRadius: 13, backgroundColor: '#D5D8DD', alignItems: 'center', justifyContent: 'center' },
  checkOn: { backgroundColor: appColor.accent, transform: [{ scale: 1.08 }] },
  allText: { fontSize: 16.5, lineHeight: 24, color: '#16171A', fontWeight: '800' },
  /* .tr min-height 54 · padding 0 20 0 26 (화면 기준) · 14.5 #2E2E38 · .tx line 1.5 padding 8 0 */
  items: { marginTop: 8 },
  item: { minHeight: 54, flexDirection: 'row', alignItems: 'center', paddingLeft: 10, paddingRight: 4 },
  itemMain: { minWidth: 0, flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12 },
  itemText: { fontSize: 15.5, lineHeight: 23.5, paddingVertical: 8, minWidth: 0, flex: 1, color: '#2E2E38' },
  /* .tr .v ink3 13 · padding 8 0 8 10 (터치는 hitSlop으로 44) */
  viewLink: { paddingVertical: 8, paddingLeft: 10, flexDirection: 'row', alignItems: 'center', gap: 2 },
  viewText: { fontSize: 14, lineHeight: 20.5, color: '#6B7079' },
  /* .pvl bottom 100 · 13.5 600 #6A42AB · padding 12 8 · .bottom bottom 30 */
  bottom: { position: 'absolute', left: 0, right: 0, bottom: 0, backgroundColor: '#FFFFFF', paddingHorizontal: 16, paddingTop: 8, gap: 2 },
  privacy: { alignSelf: 'center', minHeight: 44, paddingVertical: 12, paddingHorizontal: 8, flexDirection: 'row', alignItems: 'center', gap: 2 },
  privacyText: { fontSize: 14.5, lineHeight: 21.5, color: appColor.deepPurple, fontWeight: '600' },
  cta: { minHeight: 56, borderRadius: 16, backgroundColor: '#D5D8DD', paddingVertical: 14, alignItems: 'center', justifyContent: 'center' },
  /* 저장 실패 한 줄 = 앱 로그인 errorToast · errorText 와 같은 모양 (버튼과 8 띄움) */
  errorToast: { alignSelf: 'center', marginTop: 14, marginBottom: 8, borderRadius: 12, backgroundColor: '#303139', paddingHorizontal: 16, paddingVertical: 10 },
  errorText: { ...ft(14), color: '#FFFFFF', fontWeight: '600' },
  ctaOn: { backgroundColor: appColor.accent },
  ctaText: { fontSize: 16.5, lineHeight: 24, color: '#FFFFFF', fontWeight: '800' },
  docHeader: { height: 58, paddingHorizontal: 22, flexDirection: 'row', alignItems: 'center', gap: 2 },
  docTitle: { ...ft(17), color: '#18181C', fontWeight: '700' },
  docBottom: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: 16, paddingTop: 14, backgroundColor: '#FFFFFF' },
  docClose: { minHeight: 56, borderRadius: 16, backgroundColor: '#16171A', alignItems: 'center', justifyContent: 'center' },
  docCloseText: { fontSize: 16.5, lineHeight: 24, color: '#FFFFFF', fontWeight: '800' },
});
