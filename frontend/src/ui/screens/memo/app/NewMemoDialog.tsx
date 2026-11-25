import React, { useRef, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Line } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { splitMemo } from '@/lib/memoText';
import type { ChecklistItem, MemoColor } from '@/types/models';
import { MemoEditor } from '@/ui/shared/MemoEditor';
import { FullSheet } from '@/ui/shared/app/FullSheet';
import { fpx } from '@/ui/theme';
import type { NewMemoProps } from '../MemoDetail.types';
import type { ChecklistDraft } from '../web/ChecklistTab';
import { AI_OFF, Actions, CloseBtn, INK, Swatches, Tabs2, panel } from '../web/parts';
import { AiFooter } from './AiFooter';
import { ChecklistTab } from './ChecklistTab';
import { usePaper } from '@/ui/shared/Dark';

/**
 * 앱 새 메모: 웹 memo/web/NewMemoDialog.tsx 와 같은 내용을 아래에서 올라오는 전체 높이 시트로
 */
export function AppNewMemoDialog({ open, stockName, initialText, initialAi, aiSpent, onCancel, onSave, onSwitchToChecklist, tab0 = 0, checklist, onSaveChecklist, onEmptyChecklist }: NewMemoProps & {
  open: boolean;
  /** 처음 열 탭 (0 메모 · 1 체크리스트) */
  tab0?: 0 | 1;
  /** 이 종목의 지금 체크리스트 (없으면 새로 만들기) */
  checklist?: { title: string; items: ChecklistItem[] } | null;
  onSaveChecklist?: (d: ChecklistDraft) => void;
  /** 항목을 모두 지우고 저장 (있던 체크리스트면 휴지통으로) */
  onEmptyChecklist?: () => void;
}) {
  const paper = usePaper();
  const [text, setText] = useState(initialText ?? '');
  const [color, setColor] = useState<MemoColor>('yellow');
  const [ai, setAi] = useState(!!initialAi && !aiSpent);
  const [tab, setTab] = useState<0 | 1>(onSaveChecklist ? tab0 : 0);
  const ed = useRef<{ focus: () => void; blur: () => void }>(null);
  const empty = !text.trim();
  const save = () => {
    if (empty) return ed.current?.focus();
    onSave({ ...splitMemo(text), color, ai });
  };
  return (
    <FullSheet open={open} onClose={onCancel} label={tab ? '체크리스트' : '새 메모'}>
      <View style={[panel.box, st.mobileBox]}>
        <View style={st.head}>
          <View style={st.headL}>
            <Text style={st.sub}>{stockName} · 나의 보드</Text>
            <Text style={st.title}>{tab ? (checklist ? '체크리스트' : '새 체크리스트') : '새 메모'}</Text>
          </View>
          <CloseBtn onPress={onCancel} />
        </View>
        <Tabs2 a="메모" b="체크리스트" v={tab} set={(i) => (onSaveChecklist ? setTab(i) : i === 1 && onSwitchToChecklist?.())} />
        {tab === 1 && onSaveChecklist ? (
          <ChecklistTab initial={checklist ?? null} onCancel={onCancel} onSave={onSaveChecklist} onEmpty={() => (onEmptyChecklist ?? onCancel)()} />
        ) : (
        <>
        <View style={[st.area, st.mobileFill]}>
          <View style={[st.paper, { backgroundColor: paper[color].bg }, st.mobileFill]}>
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
        <AiFooter on={ai} set={(v) => setAi(v && !aiSpent)} sub={aiSpent ? 'AI 사용량을 다 써서 일반 메모로만 저장돼요' : ai ? '이 메모에서 1개 항목을 지켜봐요.' : AI_OFF} />
        <Actions note="연결하지 않아도 메모는 그대로 남아요" ok="메모 저장" onCancel={onCancel} onOk={save} />
        </>
        )}
      </View>
    </FullSheet>
  );
}

const st = StyleSheet.create({
  mobileBox: { flex: 1, width: '100%', maxHeight: '100%', borderRadius: 0, borderWidth: 0, shadowOpacity: 0, elevation: 0 },
  mobileFill: { flex: 1, height: 'auto', minHeight: 0 },
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
