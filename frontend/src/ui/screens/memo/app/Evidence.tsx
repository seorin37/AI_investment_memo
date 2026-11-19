import React from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { BackChevron } from '@/ui/icons/MemoGlyphs';
import { appColor, ft } from '@/ui/theme';
import { EvidenceBody, evidenceActions, evidenceTitle } from '../EvidenceContent';
import { HistoryContent } from '../HistoryContent';
import type { EvidenceProps, MemoHistoryProps } from '../MemoDetail.types';

/**
 * 앱 근거 상세 (원본 memo.html #ev: 메모 상세 위로 밀려 들어오는 회색 #F3F4F6 화면)
 * 머리 56: 뒤로 + '업데이트 근거' / '뉴스 근거' / '가격 조건' 17px 600 · 내용 (안쪽 4·16 · 아래 120) · 아래 버튼 줄 (흰 · 위 선)
 */
export function AppEvidence(p: EvidenceProps) {
  const insets = useSafeAreaInsets();
  const acts = evidenceActions(p.item);
  return (
    <View style={[st.root, st.gray, { paddingTop: insets.top }]}>
      <Head title={evidenceTitle(p.item)} onBack={p.onBack} />
      <ScrollView style={st.flex} contentContainerStyle={[st.ob, { paddingBottom: 120 + insets.bottom }]} showsVerticalScrollIndicator={false}>
        <EvidenceBody item={p.item} memo={p.memo} version={p.version} onOpenSource={p.onOpenSource} onOpenHistory={p.onOpenHistory} />
      </ScrollView>
      <View style={[st.obar, { paddingBottom: 18 + insets.bottom }]}>
        {acts.map((a) => (
          <Pressable key={a.label} onPress={() => (a.a === 'memo' ? p.onShowMemo() : p.onOpenSource(p.item))} accessibilityRole="button" style={({ pressed }) => [st.bt, a.gray && st.btGray, pressed && st.press]}>
            <Text style={[st.btT, a.gray && { color: appColor.ink }]}>{a.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

/** 앱 수정 이력 (원본 #hist: 흰 화면 · 머리 '메모') */
export function AppMemoHistory(p: MemoHistoryProps) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <Head title="메모" onBack={p.onBack} />
      <ScrollView style={st.flex} contentContainerStyle={[st.ob, { paddingBottom: 120 + insets.bottom }]} showsVerticalScrollIndicator={false}>
        <HistoryContent memo={p.memo} versions={p.versions} openVersion={p.openVersion} />
      </ScrollView>
    </View>
  );
}

function Head({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <View style={st.oh}>
      <Pressable onPress={onBack} accessibilityRole="button" accessibilityLabel="뒤로" style={st.iconbtn}>
        <BackChevron />
      </Pressable>
      <Text style={st.ohT} numberOfLines={1}>
        {title}
      </Text>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: appColor.surface },
  gray: { backgroundColor: appColor.bg },
  flex: { flex: 1 },
  oh: { height: 56, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 6 },
  iconbtn: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  ohT: { flex: 1, ...ft(17), fontWeight: '600', color: appColor.ink },
  ob: { paddingTop: 4, paddingHorizontal: 16 },
  obar: { position: 'absolute', left: 0, right: 0, bottom: 0, flexDirection: 'row', gap: 8, paddingTop: 12, paddingHorizontal: 16, backgroundColor: '#FFFFFF', borderTopWidth: 1, borderTopColor: appColor.line },
  bt: { flex: 1, minHeight: 52, borderRadius: 14, backgroundColor: appColor.ink, alignItems: 'center', justifyContent: 'center', paddingVertical: 14 },
  btGray: { flexGrow: 0, flexBasis: 108, backgroundColor: '#ECEDF1' },
  press: { transform: [{ scale: 0.97 }] },
  btT: { ...ft(15.5), fontWeight: '700', color: '#FFFFFF' },
});
