import React, { useEffect, useRef, useState } from 'react';
import { BackHandler, KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Line } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { splitMemo } from '@/lib/memoText';
import { MemoEditor } from '@/ui/shared/MemoEditor';
import { PaperBox } from '@/ui/shared/PaperBox';
import { Toggle } from '@/ui/shared/Toggle';
import { appColor, ft } from '@/ui/theme';
import type { NewMemoProps } from '../MemoDetail.types';
import { usePaper } from '@/ui/shared/Dark';

/**
 * 앱 새 메모 (원본 memo.html 11 · #nm: 아래에서 올라오는 전체 화면)
 * 머리 56 (좌우 16): [취소] 15.5px · '종목 · 새 메모' 15.5px 800 가운데 · [완료] 15.5px 800 #6A42AB
 * 노란 종이 (최소 250) + 예시 글(비면 보임: 제목 21px · 본문 15.5px 줄 1.8 · 점선 아래 안내 12.5px) · 안내 12.5px #9A9EA7
 * AI 연결 칸 (#F6F6F8 라운드 16 · 안쪽 14·16 · 위 14). 저장: 첫 줄 = 제목 (splitMemo)
 */
export function AppNewMemo({ stockName, initialText, initialAi, onCancel, onEmpty, onSave }: NewMemoProps) {
  const paper = usePaper();
  const insets = useSafeAreaInsets();
  const [text, setText] = useState(initialText ? `${initialText}\n` : '');
  const [ai, setAi] = useState(!!initialAi);
  const ed = useRef<{ focus: () => void; blur: () => void }>(null);
  const pc = paper.yellow;
  const empty = !text.trim();
  useEffect(() => {
    const t = setTimeout(() => ed.current?.focus(), 350);
    return () => clearTimeout(t);
  }, []);
  /* 안드로이드 뒤로 = 취소 */
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      onCancel();
      return true;
    });
    return () => sub.remove();
  }, [onCancel]);
  const save = () => {
    ed.current?.blur();
    if (empty) return (onEmpty ?? onCancel)();
    const r = splitMemo(text);
    onSave({ ...r, color: 'yellow', ai });
  };
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <View style={st.nmh}>
        <Pressable onPress={onCancel} accessibilityRole="button" style={st.hb}>
          <Text style={st.hbT}>취소</Text>
        </Pressable>
        <Text style={st.ttl} numberOfLines={1}>
          {stockName} · 새 메모
        </Text>
        <Pressable onPress={save} accessibilityRole="button" style={st.hb}>
          <Text style={[st.hbT, st.ok]}>완료</Text>
        </Pressable>
      </View>
      <KeyboardAvoidingView style={st.flex} behavior="padding">
        <ScrollView style={st.flex} contentContainerStyle={[st.nmb, { paddingBottom: 40 + insets.bottom }]} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
          <PaperBox bg={pc.bg} accent={pc.accent} radius={22} cut={28} style={st.paper}>
            {empty ? (
              <View pointerEvents="none" style={st.phd}>
                <Text style={st.phdB}>HBM 실적 계속 보기</Text>
                <Text style={st.phdP}>{'다음 정기보고서에서 HBM 매출 비중 확인하기\n종가 ○○만원 아래로 내려오면 다시 보기'}</Text>
                <View style={st.hn}>
                  {/* 원본 border-top 1px dashed (RN 은 한쪽만 점선이 안 되어 선을 그림) */}
                  <Svg width="100%" height={1} style={st.hnLine}>
                    <Line x1="0" y1="0.5" x2="100%" y2="0.5" stroke="rgba(22,22,28,0.18)" strokeWidth={1} strokeDasharray="3 3" />
                  </Svg>
                  <Text style={st.hnT}>{'투자가 막연하세요? 떠오른 생각 한 줄이면 충분해요.\n첫 줄은 제목이 돼요. 확인할 것·다시 볼 조건을 적어 두면 AI가 관련 소식을 더 잘 찾아요.'}</Text>
                </View>
              </View>
            ) : null}
            <MemoEditor variant="app" value={text} onChangeText={setText} editable focusRef={ed} accessibilityLabel="새 메모 (첫 줄은 제목)" />
          </PaperBox>
          <Text style={st.ecap}>연결하지 않아도 메모는 그대로 남아요 · 예시 글은 저장되지 않아요</Text>
          <View style={st.aisw}>
            <View style={st.flex}>
              <Text style={st.aiswB}>AI 연결</Text>
              <Text style={st.aiswS}>켜 두면 하루 한 번 공시·뉴스를 대신 확인해 여기에 붙여 드려요</Text>
            </View>
            <Toggle variant="app" on={ai} onChange={setAi} label="AI 연결" />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: appColor.surface },
  flex: { flex: 1 },
  nmh: { height: 56, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16 },
  hb: { paddingVertical: 8, paddingHorizontal: 2, minHeight: 44, justifyContent: 'center' },
  hbT: { ...ft(15.5), color: appColor.ink },
  ok: { fontWeight: '800', color: appColor.deepPurple },
  ttl: { flex: 1, textAlign: 'center', ...ft(15.5), fontWeight: '800', color: appColor.ink },
  nmb: { paddingTop: 4, paddingHorizontal: 16 },
  paper: { minHeight: 250, paddingTop: 26, paddingHorizontal: 20, paddingBottom: 34 },
  phd: { position: 'absolute', left: 20, right: 20, top: 26 },
  phdB: { ...ft(21, 1.4), fontWeight: '700', color: 'rgba(22,22,28,0.3)', marginTop: 4, marginBottom: 8 },
  phdP: { ...ft(15.5, 1.8), color: 'rgba(22,22,28,0.32)' },
  hn: { marginTop: 12, paddingTop: 10 },
  hnLine: { position: 'absolute', left: 0, right: 0, top: 0 },
  hnT: { ...ft(12.5, 1.6), color: 'rgba(22,22,28,0.4)' },
  ecap: { textAlign: 'center', ...ft(12.5), color: appColor.ink3, marginTop: 12 },
  aisw: { backgroundColor: '#F6F6F8', borderRadius: 16, paddingVertical: 14, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 14 },
  aiswB: { ...ft(15), fontWeight: '700', color: appColor.ink },
  aiswS: { ...ft(12), color: appColor.ink3 },
});
