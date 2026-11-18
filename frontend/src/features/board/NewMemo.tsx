/**
 * 새 메모 — 노란 메모지에 첫 줄이 제목. 빈 칸이면 예시 글과 안내가 흐리게 보이고, 아래 AI 연결 스위치.
 * 체험판 memo.html '11 새 메모'. 상단 바(취소 · 종목 · 새 메모 · 완료)는 TopBar 로 따로.
 * 움직임: 메모지가 .96배에서 펼쳐지듯 나타남 · 예시 글은 쓰기 시작하면 .25초에 걸쳐 흐려짐 · AI 연결 스위치(.4s spring)
 */
import { useEffect } from 'react';
import { Animated, ScrollView, StyleSheet, View } from 'react-native';
import { Text, TextInput } from '@/components/ui/AppText';
import Svg, { Polygon } from 'react-native-svg';
import { Appear } from '@/components/motion/Appear';
import { EASE, ND, tween, useValue } from '@/components/motion/motion';
import { Toggle } from '@/components/motion/Toggle';
import { BOARD_C as C, MEMO_PAPER } from '@/features/board/boardTokens';
import type { NewMemoProps } from '@/features/board/NewMemo.types';

const PAD = 16;
const R = { paper: 22, box: 16 };
const PAPER = MEMO_PAPER.yellow;

export function NewMemo({ value, onChangeValue, ai_link, onChangeAiLink, ai_unavailable, placeholder_title, placeholder_lines }: NewMemoProps) {
  const empty = value.trim().length === 0;
  const ph = useValue(empty ? 1 : 0);
  useEffect(() => { tween(ph, empty ? 1 : 0, 250, EASE, ND).start(); }, [empty, ph]);
  return (
    <ScrollView style={st.root} contentContainerStyle={st.body} keyboardShouldPersistTaps="handled">
      <Appear kind="tab" style={[st.paper, { backgroundColor: PAPER.bg }]}>
        <Animated.View style={[st.ph, { opacity: ph }]} pointerEvents="none">
            <Text style={st.phTitle}>{placeholder_title}</Text>
            {placeholder_lines.map((l) => <Text key={l} style={st.phLine}>{l}</Text>)}
            <Text style={st.hint}>투자가 막연하세요? 떠오른 생각 한 줄이면 충분해요.{'\n'}첫 줄은 제목이 돼요. 확인할 것·다시 볼 조건을 적어 두면 AI가 관련 소식을 더 잘 찾아요.</Text>
        </Animated.View>
        <TextInput style={st.input} value={value} onChangeText={onChangeValue} multiline autoFocus textAlignVertical="top" accessibilityLabel="새 메모 (첫 줄은 제목)" />
        <Svg width={28} height={28} style={st.fold}>
          <Polygon points="28,0 28,28 0,28" fill={C.card} />
          <Polygon points="0,0 28,0 0,28" fill={PAPER.fold} />
        </Svg>
      </Appear>
      <Text style={st.caption}>연결하지 않아도 메모는 그대로 남아요 · 예시 글은 저장되지 않아요</Text>
      <Appear kind="up" index={2} style={st.aisw}>
        <View style={st.flex}>
          <Text style={st.aiTitle}>AI 연결</Text>
          <Text style={st.aiSub}>{ai_unavailable ? 'AI 연결 준비 중인 종목이에요' : '켜 두면 하루 한 번 공시·뉴스를 대신 확인해 여기에 붙여 드려요'}</Text>
        </View>
        <Toggle value={ai_link} onChange={onChangeAiLink} disabled={ai_unavailable} onColor={C.accent} offColor={C.chipLine} accessibilityLabel="AI 연결" />
      </Appear>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.card },
  flex: { flex: 1, minWidth: 0 },
  body: { padding: PAD, paddingBottom: 40 },
  paper: { borderRadius: R.paper, minHeight: 250, paddingHorizontal: 20, paddingTop: 26, paddingBottom: 34, overflow: 'hidden' },
  ph: { position: 'absolute', left: 20, right: 20, top: 26 },
  phTitle: { fontSize: 21, fontWeight: '800', lineHeight: 29, color: C.text, opacity: 0.3, marginTop: 4, marginBottom: 8 },
  phLine: { fontSize: 15.5, lineHeight: 28, color: C.text, opacity: 0.3 },
  hint: { fontSize: 12.5, lineHeight: 19, color: C.sub, marginTop: 14 },
  input: { fontSize: 15.5, lineHeight: 28, color: C.body, minHeight: 190, padding: 0 },
  fold: { position: 'absolute', right: 0, bottom: 0 },
  caption: { textAlign: 'center', fontSize: 12.5, color: C.muted, marginTop: 12 },
  aisw: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 14, borderRadius: R.box, backgroundColor: C.appBg, padding: 16, minHeight: 64 },
  aiTitle: { fontSize: 15, fontWeight: '800', color: C.text },
  aiSub: { fontSize: 12.5, lineHeight: 18, color: C.sub, marginTop: 2 },
});
