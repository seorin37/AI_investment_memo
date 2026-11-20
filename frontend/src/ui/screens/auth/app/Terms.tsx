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
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={[st.content, { paddingBottom: 146 + insets.bottom }]}>
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
                  <Text numberOfLines={2} style={st.itemText}>{item.label}</Text>
                </Pressable>
                {item.document ? <Pressable onPress={() => p.onOpenDocument(item.document!)} style={st.viewLink}><Text style={st.viewText}>보기</Text><ChevronGlyph /></Pressable> : null}
              </View>
            );
          })}
        </View>
      </ScrollView>
      <View style={[st.bottom, { paddingBottom: Math.max(insets.bottom, 14) }]}>
        <Pressable onPress={() => p.onOpenDocument('privacy')} style={st.privacy}><Text style={st.privacyText}>개인정보 처리방침 확인하기</Text><ChevronGlyph color={appColor.deepPurple} /></Pressable>
        <Pressable disabled={!ready} onPress={p.onContinue} style={[st.cta, ready && st.ctaOn]}>
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

const st = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { paddingHorizontal: 16 },
  top: { height: 64, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  back: { width: 44, height: 44, marginLeft: -10, alignItems: 'center', justifyContent: 'center', borderRadius: 22 },
  progress: { flexDirection: 'row', alignItems: 'center', gap: 6, marginRight: 6 },
  progressDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D5D8DD' },
  progressOn: { width: 18, backgroundColor: appColor.accent },
  title: { ...ft(26, 1.48), marginTop: 9, color: '#18181C', fontWeight: '700' },
  sub: { ...ft(14, 1.5), marginTop: 6, color: '#A4A8B3' },
  all: { minHeight: 58, marginTop: 26, borderRadius: 16, backgroundColor: '#F2F2F5', paddingHorizontal: 16, paddingVertical: 14, flexDirection: 'row', alignItems: 'center', gap: 12 },
  allOn: { backgroundColor: '#F0ECFF' },
  check: { width: 26, height: 26, borderRadius: 13, backgroundColor: '#D5D8DD', alignItems: 'center', justifyContent: 'center' },
  checkOn: { backgroundColor: appColor.accent },
  allText: { ...ft(17), color: '#18181C', fontWeight: '700' },
  items: { marginTop: 8 },
  item: { minHeight: 54, flexDirection: 'row', alignItems: 'center', paddingVertical: 13, paddingLeft: 9 },
  itemMain: { minWidth: 0, flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12 },
  itemText: { ...ft(15, 1.5), minWidth: 0, flex: 1, color: '#575B63' },
  viewLink: { minHeight: 44, paddingLeft: 10, flexDirection: 'row', alignItems: 'center', gap: 2 },
  viewText: { ...ft(13), color: '#A4A8B3' },
  bottom: { position: 'absolute', left: 0, right: 0, bottom: 0, backgroundColor: '#FFFFFF', paddingHorizontal: 16, paddingTop: 8, gap: 14 },
  privacy: { alignSelf: 'center', minHeight: 30, flexDirection: 'row', alignItems: 'center', gap: 2 },
  privacyText: { ...ft(14), color: appColor.deepPurple, fontWeight: '500' },
  cta: { minHeight: 56, borderRadius: 16, backgroundColor: '#D0D3D9', paddingVertical: 14, alignItems: 'center', justifyContent: 'center' },
  ctaOn: { backgroundColor: appColor.accent },
  ctaText: { ...ft(17), color: '#FFFFFF', fontWeight: '700' },
  docHeader: { height: 58, paddingHorizontal: 22, flexDirection: 'row', alignItems: 'center', gap: 2 },
  docTitle: { ...ft(17), color: '#18181C', fontWeight: '700' },
  docBottom: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: 16, paddingTop: 14, backgroundColor: '#FFFFFF' },
  docClose: { minHeight: 56, borderRadius: 16, backgroundColor: '#16171A', alignItems: 'center', justifyContent: 'center' },
  docCloseText: { ...ft(17), color: '#FFFFFF', fontWeight: '700' },
});
