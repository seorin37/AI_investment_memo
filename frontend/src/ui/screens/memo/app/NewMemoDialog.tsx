import React, { useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Line } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { splitMemo } from '@/lib/memoText';
import type { MemoColor } from '@/types/models';
import { CheckMark } from '@/ui/icons/BoardGlyphs';
import { AppIconButton } from '@/ui/shared/IconButton';
import { MemoEditor } from '@/ui/shared/MemoEditor';
import { PaperBox } from '@/ui/shared/PaperBox';
import { PillSeg } from '@/ui/shared/PillSeg';
import { Toggle } from '@/ui/shared/Toggle';
import { FullSheet } from '@/ui/shared/app/FullSheet';
import { usePaper } from '@/ui/shared/Dark';
import { nf } from '@/ui/shared/app/nf';
import { appColor, ft } from '@/ui/theme';
import type { NewMemoProps } from '../MemoDetail.types';
import { ChecklistTab, type ChecklistDraft } from './ChecklistTab';
import { SheetActions } from './SheetActions';

const COLORS: MemoColor[] = ['yellow', 'blue', 'pink', 'green', 'purple'];
const AI_OFF = '켜 두면 하루 한 번 공시·뉴스를 대신 확인해 여기에 붙여 드려요.';

/**
 * 앱 새 메모 시트 (아래에서 올라오는 전체 높이). 들어가는 항목·문구·동작은 웹 새 메모 창과 같고, 모양은 앱:
 * 머리(종목 · 나의 보드 / 20 800 / 닫기) · 메모|체크리스트 알약 · 종이(라운드 22 · 귀퉁이 28 · 앱 편집 칸) · 색상 · AI 연결 칸 · [취소][메모 저장]
 */
export function AppNewMemoDialog({ open, stockName, initialText, initialAi, aiSpent, onCancel, onSave, onSaveChecklist, onEmptyChecklist }: NewMemoProps & {
  open: boolean;
  onSaveChecklist: (d: ChecklistDraft) => void;
  /** 항목 없이 저장 */
  onEmptyChecklist: () => void;
}) {
  const paper = usePaper();
  const [text, setText] = useState(initialText ?? '');
  const [color, setColor] = useState<MemoColor>('yellow');
  const [ai, setAi] = useState(!!initialAi && !aiSpent);
  const [tab, setTab] = useState<'memo' | 'check'>('memo');
  const ed = useRef<{ focus: () => void; blur: () => void }>(null);
  const empty = !text.trim();
  const save = () => {
    if (empty) return ed.current?.focus();
    ed.current?.blur();
    onSave({ ...splitMemo(text), color, ai });
  };
  const pc = paper[color];
  return (
    <FullSheet open={open} onClose={onCancel} label={tab === 'check' ? '체크리스트' : '새 메모'}>
      <View style={st.handle} />
      <View style={st.head}>
        <View style={st.flex}>
          <Text style={st.sub} numberOfLines={1}>{stockName} · 나의 보드</Text>
          <Text style={st.title}>{tab === 'check' ? '새 체크리스트' : '새 메모'}</Text>
        </View>
        <AppIconButton label="닫기" size={42} icon="close" iconSize={20} color={appColor.ink} onPress={onCancel} />
      </View>
      <PillSeg options={[{ key: 'memo', label: '메모' }, { key: 'check', label: '체크리스트' }]} value={tab} onChange={setTab} bg="#ECEDF1" pad={4} radius={14} pillRadius={11} height={38} fontSize={14.5} style={st.tabs} />
      {tab === 'check' ? (
        <ChecklistTab onCancel={onCancel} onSave={onSaveChecklist} onEmpty={onEmptyChecklist} />
      ) : (
        <>
          <ScrollView style={st.flex} contentContainerStyle={st.body} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
            <PaperBox bg={pc.bg} accent={pc.accent} radius={22} cut={28} style={st.paper}>
              {empty ? (
                <View pointerEvents="none" style={st.ph}>
                  <Text style={st.phB}>실적 발표 후 다시 보기</Text>
                  <Text style={st.phP}>{'다음 분기 보고서에서 순이익이 작년보다 늘었는지 확인하기\n종가 ○○원 아래로 내려오면 다시 보기'}</Text>
                  <View style={st.hn}>
                    <Svg width="100%" height={1} style={st.hnLine}>
                      <Line x1="0" y1="0.5" x2="100%" y2="0.5" stroke="rgba(22,22,28,0.18)" strokeWidth={1} strokeDasharray="3 3" />
                    </Svg>
                    <Text style={st.hnT}>{'투자가 막연하세요? 떠오른 생각 한 줄이면 충분해요.\n첫 줄은 제목이 돼요. 확인할 것·다시 볼 조건을 적어 두면 AI가 관련 소식을 더 잘 찾아요.'}</Text>
                  </View>
                </View>
              ) : null}
              <MemoEditor variant="app" value={text} onChangeText={setText} editable autoFocus focusRef={ed} accessibilityLabel="새 메모 (첫 줄은 제목)" />
            </PaperBox>
            <View style={st.box}>
              <View style={st.flex}>
                <Text style={st.boxB}>메모 색상</Text>
                <Text style={st.boxS}>보기·수정 칸에 같은 색상</Text>
              </View>
              <View style={st.dots}>
                {COLORS.map((c) => (
                  <Pressable key={c} onPress={() => setColor(c)} accessibilityRole="button" accessibilityLabel={paper[c].label} accessibilityState={{ selected: color === c }} hitSlop={4} style={[st.dot, { backgroundColor: paper[c].bg }, color === c && st.dotOn]}>
                    {color === c ? <CheckMark size={14} color={appColor.ink} /> : null}
                  </Pressable>
                ))}
              </View>
            </View>
            <View style={st.box}>
              <View style={st.flex}>
                <Text style={st.boxB}>AI 연결</Text>
                <Text style={st.boxS}>{aiSpent ? 'AI 사용량을 다 써서 일반 메모로만 저장돼요' : ai ? '이 메모에서 1개 항목을 지켜봐요.' : AI_OFF}</Text>
              </View>
              <Toggle variant="app" on={ai} onChange={(v) => setAi(v && !aiSpent)} label="AI 연결" />
            </View>
          </ScrollView>
          <SheetActions note="연결하지 않아도 메모는 그대로 남아요" ok="메모 저장" onCancel={onCancel} onOk={save} />
        </>
      )}
    </FullSheet>
  );
}

const st = StyleSheet.create({
  flex: { flex: 1, minWidth: 0 },
  handle: { alignSelf: 'center', width: 40, height: 5, borderRadius: 3, backgroundColor: '#D5D8DD', marginTop: 10 },
  head: { flexDirection: 'row', alignItems: 'center', paddingLeft: 18, paddingRight: 8, paddingTop: 8, paddingBottom: 10 },
  sub: { ...ft(12.5), color: appColor.ink3 },
  title: { ...ft(21), fontWeight: '800', color: appColor.ink, marginTop: 2 },
  tabs: { marginHorizontal: 16, marginBottom: 12 },
  body: { paddingHorizontal: 16, paddingBottom: 16 },
  paper: { minHeight: 300, paddingTop: 26, paddingHorizontal: 20, paddingBottom: 34 },
  ph: { position: 'absolute', left: 20, right: 20, top: 26 },
  phB: { ...ft(21, 1.4), fontWeight: '700', color: 'rgba(22,22,28,0.3)', marginTop: 4, marginBottom: 8 },
  phP: { ...ft(15.5, 1.8), color: 'rgba(22,22,28,0.32)' },
  hn: { marginTop: 12, paddingTop: 10 },
  hnLine: { position: 'absolute', left: 0, right: 0, top: 0 },
  hnT: { ...ft(12.5, 1.6), color: 'rgba(22,22,28,0.4)' },
  box: { backgroundColor: '#FFFFFF', borderRadius: 16, paddingVertical: 14, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 12 },
  boxB: { ...nf(15), fontWeight: '700', color: appColor.ink },
  boxS: { ...ft(12, 1.4), color: appColor.ink3, marginTop: 2 },
  dots: { flexDirection: 'row', gap: 8 },
  dot: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  dotOn: { borderWidth: 2, borderColor: appColor.ink },
});
