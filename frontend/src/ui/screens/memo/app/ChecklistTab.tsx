import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Text, TextInput } from '@/components/ui/AppText';
import { CheckMark } from '@/ui/icons/BoardGlyphs';
import { useChecklistTone } from '@/ui/shared/Dark';
import { appColor, ft } from '@/ui/theme';
import { SheetActions } from './SheetActions';

export type ChecklistDraft = { title: string; items: { text: string; done: boolean }[] };

/**
 * 앱 새 메모 시트의 [체크리스트] 탭: 항목·문구·동작은 웹 새 메모 창과 같고, 모양은 앱 체크리스트(귤색 종이 · 줄 54 · 상자 24).
 * Enter 로 항목 추가, 저장하면 빈 글은 빼고 입력 칸에 남은 글도 항목으로. 하나도 없으면 onEmpty.
 */
export function ChecklistTab({ onCancel, onSave, onEmpty }: { onCancel: () => void; onSave: (d: ChecklistDraft) => void; onEmpty: () => void }) {
  const tone = useChecklistTone();
  const [title, setTitle] = useState('체크리스트');
  const [items, setItems] = useState<{ k: string; text: string; done: boolean }[]>([]);
  const [add, setAdd] = useState('');
  const done = items.filter((i) => i.done).length;
  /* 한글 조합 중 Enter 도 한 번에 (웹과 같은 방식: 줄바꿈이 들어왔는지로) */
  const typeAdd = (v: string) => {
    if (!v.includes('\n')) return setAdd(v);
    const t = v.replace(/\n/g, '').trim();
    if (t) setItems((l) => [...l, { k: `n${Date.now()}${l.length}`, text: t, done: false }]);
    setAdd('');
  };
  const save = () => {
    const list = items.map(({ text, done: d }) => ({ text: text.trim(), done: d })).filter((i) => i.text);
    if (add.trim()) list.push({ text: add.trim(), done: false });
    if (!list.length) return onEmpty();
    onSave({ title: title.trim() || '체크리스트', items: list });
  };
  return (
    <>
      <ScrollView style={st.flex} contentContainerStyle={st.body} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
        <View style={[st.paper, { backgroundColor: tone.paper }]}>
          <View style={st.lab}><Text style={st.labB}>체크리스트 제목</Text><Text style={st.labS}>보드 카드 제목으로 보여요</Text></View>
          <TextInput value={title} onChangeText={setTitle} accessibilityLabel="체크리스트 제목" style={st.title} />
          <View style={[st.lab, { marginTop: 14 }]}><Text style={st.labB}>확인할 항목</Text><Text style={[st.cnt, { color: tone.ink }]}>{done} / {items.length} 완료</Text></View>
          {items.map((c, i) => (
            <View key={c.k} style={st.row}>
              <Pressable onPress={() => setItems((l) => l.map((x, j) => (j === i ? { ...x, done: !x.done } : x)))} accessibilityRole="checkbox" accessibilityState={{ checked: c.done }} accessibilityLabel={c.text} hitSlop={8} style={[st.box, c.done ? { backgroundColor: tone.tape, borderColor: tone.tape } : { borderColor: tone.cardBox, backgroundColor: tone.cardBoxBg }]}>
                {c.done ? <CheckMark size={14} /> : null}
              </Pressable>
              <TextInput value={c.text} onChangeText={(v) => setItems((l) => l.map((x, j) => (j === i ? { ...x, text: v } : x)))} maxLength={500} accessibilityLabel={`항목 ${i + 1} 고치기`} style={[st.in, c.done && st.inDone]} />
              <Pressable onPress={() => setItems((l) => l.filter((_, j) => j !== i))} accessibilityRole="button" accessibilityLabel={`${c.text} 지우기`} hitSlop={6} style={st.del}><Text style={st.delT}>×</Text></Pressable>
            </View>
          ))}
          <View style={[st.row, { borderBottomWidth: 0 }]}>
            <View style={[st.box, st.plus, { borderColor: tone.cardBox }]}><Text style={[st.plusT, { color: tone.ink }]}>+</Text></View>
            <TextInput value={add} onChangeText={typeAdd} multiline numberOfLines={1} placeholder="항목 추가 · Enter로 바로 추가" placeholderTextColor="#B49A8A" accessibilityLabel="항목 추가" style={[st.in, st.addIn]} />
          </View>
        </View>
        <View style={st.ai}>
          <Text style={st.aiB}>AI 연결 없음</Text>
          <Text style={st.aiS}>체크리스트는 보드에만 저장되고, 뉴스·공시와 연결되지 않아요.</Text>
        </View>
      </ScrollView>
      <SheetActions note="저장 후에도 언제든 고칠 수 있어요" ok="체크리스트 저장" onCancel={onCancel} onOk={save} />
    </>
  );
}

const st = StyleSheet.create({
  flex: { flex: 1, minWidth: 0 },
  body: { paddingHorizontal: 16, paddingBottom: 16 },
  paper: { borderRadius: 22, paddingTop: 20, paddingHorizontal: 18, paddingBottom: 8 },
  lab: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  labB: { ...ft(13), fontWeight: '700', color: '#9A6B4F' },
  labS: { ...ft(12), color: '#B49A8A' },
  cnt: { ...ft(13), fontWeight: '800' },
  title: { fontSize: 22, lineHeight: 30, fontWeight: '800', color: appColor.ink, letterSpacing: -0.4, padding: 0, paddingVertical: 4, ...({ outlineStyle: 'none' } as object) },
  row: { minHeight: 54, flexDirection: 'row', alignItems: 'center', gap: 12, borderBottomWidth: 1, borderBottomColor: 'rgba(194,65,12,0.12)' },
  box: { width: 24, height: 24, borderRadius: 8, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  plus: { borderStyle: 'dashed' },
  plusT: { fontSize: 16, lineHeight: 18, fontWeight: '800' },
  in: { flex: 1, minWidth: 0, fontSize: 15.5, lineHeight: 22.5, fontWeight: '600', color: appColor.ink, padding: 0, ...({ outlineStyle: 'none' } as object) },
  inDone: { color: '#A89A92', textDecorationLine: 'line-through' },
  addIn: { fontWeight: '400', height: 24, ...({ resize: 'none', overflow: 'hidden' } as object) },
  del: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  delT: { fontSize: 20, lineHeight: 24, color: '#C9A792' },
  ai: { backgroundColor: '#FFFFFF', borderRadius: 16, paddingVertical: 14, paddingHorizontal: 16, marginTop: 12 },
  aiB: { ...ft(15), fontWeight: '700', color: appColor.ink },
  aiS: { ...ft(12, 1.4), color: appColor.ink3, marginTop: 2 },
});
