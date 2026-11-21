import React, { useRef, useState } from 'react';
import { ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import Svg, { Line } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { splitMemo } from '@/lib/memoText';
import type { MemoColor } from '@/types/models';
import { MemoEditor } from '@/ui/shared/MemoEditor';
import { Sheet } from '@/ui/shared/Sheet';
import { fpx } from '@/ui/theme';
import type { NewMemoProps } from '../MemoDetail.types';
import { AI_OFF, Actions, AiFooter, CloseBtn, INK, Swatches, Tabs2, panel } from './parts';
import { usePaper } from '@/ui/shared/Dark';

/**
 * 웹 새 메모 창 (원본 board.tsx NewDialog 6.1: 680 가운데 창)
 * 머리 96: '종목 · 나의 보드' 13/20 · '새 메모' 20/29 700 · × / [메모 | 체크리스트] / 종이 277 (비면 예시 글: 제목 22/31 · 본문 17 줄 1.6 · 점선 아래 안내 13)
 * 메모 색상 · AI 연결 칸 · [취소] [메모 저장]. 비어 있으면 저장 안 함.
 */
export function WebNewMemoDialog({ open, stockName, initialText, onCancel, onSave, onSwitchToChecklist }: NewMemoProps & { open: boolean }) {
  const paper = usePaper();
  const { height: H } = useWindowDimensions();
  const [text, setText] = useState(initialText ?? '');
  const [color, setColor] = useState<MemoColor>('yellow');
  const [ai, setAi] = useState(false);
  const ed = useRef<{ focus: () => void; blur: () => void }>(null);
  const empty = !text.trim();
  const save = () => {
    if (empty) return ed.current?.focus();
    onSave({ ...splitMemo(text), color, ai });
  };
  return (
    <Sheet open={open} onClose={onCancel} width={680} label="새 메모">
      <View style={[panel.box, { maxHeight: H - 32 }]}>
        <View style={st.head}>
          <View style={st.headL}>
            <Text style={st.sub}>{stockName} · 나의 보드</Text>
            <Text style={st.title}>새 메모</Text>
          </View>
          <CloseBtn onPress={onCancel} />
        </View>
        <Tabs2 a="메모" b="체크리스트" v={0} set={(i) => i === 1 && onSwitchToChecklist?.()} />
        <View style={st.area}>
          <View style={[st.paper, { backgroundColor: paper[color].bg }]}>
            {empty ? (
              <View pointerEvents="none" style={st.ph}>
                <Text style={st.phT}>실적 발표 후 다시 보기</Text>
                <Text style={st.phP}>{'다음 분기 보고서에서 순이익이 작년보다 늘었는지 확인하기\n종가 ○○원 아래로 내려오면 다시 보기'}</Text>
                <View style={st.phN}>
                  <Svg width="100%" height={1} style={st.phLine}>
                    <Line x1="0" y1="0.5" x2="100%" y2="0.5" stroke="rgba(22,22,28,0.18)" strokeWidth={1} strokeDasharray="3 3" />
                  </Svg>
                  <Text style={st.phNT}>{'투자가 막연하세요? 떠오른 생각 한 줄이면 충분해요.\n첫 줄은 제목이 돼요. 확인할 것·다시 볼 조건을 적어 두면 AI가 관련 소식을 더 잘 찾아요.'}</Text>
                </View>
              </View>
            ) : null}
            <ScrollView showsVerticalScrollIndicator={false}>
              <MemoEditor variant="web" value={text} onChangeText={setText} editable autoFocus focusRef={ed} accessibilityLabel="새 메모 (첫 줄은 제목)" />
            </ScrollView>
          </View>
          <Swatches v={color} set={setColor} />
        </View>
        <AiFooter on={ai} set={setAi} sub={ai ? '이 메모에서 1개 항목을 지켜봐요.' : AI_OFF} />
        <Actions note="연결하지 않아도 메모는 그대로 남아요" ok="메모 저장" onCancel={onCancel} onOk={save} />
      </View>
    </Sheet>
  );
}

const st = StyleSheet.create({
  head: { minHeight: 96, flexDirection: 'row', alignItems: 'center', gap: 12, paddingTop: 20, paddingHorizontal: 24, paddingBottom: 24 },
  headL: { flex: 1, minWidth: 0, gap: 4 },
  sub: { ...fpx(13, 20), fontWeight: '500', color: '#747D8D' },
  title: { ...fpx(20, 29), fontWeight: '700', color: INK },
  area: { height: 348, paddingTop: 8, paddingHorizontal: 24, paddingBottom: 16, gap: 13 },
  paper: { height: 277, borderRadius: 16, padding: 20 },
  ph: { position: 'absolute', left: 20, right: 20, top: 20, gap: 8 },
  phT: { ...fpx(22, 31), fontWeight: '700', color: '#16161C', opacity: 0.3 },
  phP: { ...fpx(17, 27.2), color: '#16161C', opacity: 0.32 },
  phN: { paddingTop: 10 },
  phLine: { position: 'absolute', left: 0, right: 0, top: 0 },
  phNT: { ...fpx(13, 19.5), color: '#16161C', opacity: 0.38 },
});
