import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import type { ChecklistItem } from '@/types/models';
import { fpx } from '@/ui/theme';
import { Actions, INK } from './parts';

type Hover = { pressed: boolean; hovered?: boolean };

/** 저장할 체크리스트 — 서버 id 가 있는 항목은 id 를 그대로, 새 항목은 id 없이 */
export type ChecklistDraft = { title: string; items: { id?: string; text: string; done: boolean }[] };

/**
 * 웹 새 메모 창의 [체크리스트] 탭 (원본 web/src/screens/board.tsx NewDialog 6.2, 2026-11-22 연결)
 * 제목 칸 '체크리스트 제목 · 보드 카드 제목으로 보여요' · '확인할 항목 N / M 완료' + 고리
 * 항목 줄 44 (동그라미 · 글 · ×) · 아래 '항목 추가 · Enter로 바로 추가' · 'AI 연결 없음' 안내 · [취소] [체크리스트 저장]
 * 저장: 빈 글 항목은 빼고, 입력칸에 남은 글도 항목으로. 항목이 하나도 없으면 onEmpty (있던 체크리스트면 휴지통).
 */
export function ChecklistTab({ initial, onCancel, onSave, onEmpty }: {
  initial: { title: string; items: ChecklistItem[] } | null;
  onCancel: () => void;
  onSave: (d: ChecklistDraft) => void;
  onEmpty: () => void;
}) {
  const [title, setTitle] = useState(initial?.title ?? '체크리스트');
  const [items, setItems] = useState<{ id?: string; text: string; done: boolean }[]>(() => initial?.items.map((i) => ({ ...i })) ?? []);
  const [add, setAdd] = useState('');
  const done = items.filter((i) => i.done).length;
  const push = () => {
    const t = add.trim();
    if (!t) return;
    setItems((l) => [...l, { text: t, done: false }]);
    setAdd('');
  };
  const save = () => {
    const list = items.map((i) => ({ ...i, text: i.text.trim() })).filter((i) => i.text);
    if (add.trim()) list.push({ text: add.trim(), done: false });
    if (!list.length) return onEmpty();
    onSave({ title: title.trim() || '체크리스트', items: list });
  };
  return (
    <>
      <ScrollView style={st.body} contentContainerStyle={st.bodyIn} showsVerticalScrollIndicator={false}>
        <View style={st.row}>
          <Text style={st.label}>체크리스트 제목</Text>
          <Text style={st.hint}>보드 카드 제목으로 보여요</Text>
        </View>
        <TextInput value={title} onChangeText={setTitle} accessibilityLabel="체크리스트 제목" style={st.titleIn} />
        <View style={st.row}>
          <Text style={st.label}>확인할 항목</Text>
          <View style={st.count}>
            <Text style={st.hint}>
              {done} / {items.length} 완료
            </Text>
            <Ring done={done} n={items.length} />
          </View>
        </View>
        <View style={st.list}>
          {items.map((c, i) => (
            <View key={c.id ?? `new-${i}`} style={st.item}>
              <Pressable
                onPress={() => setItems((l) => l.map((x, j) => (j === i ? { ...x, done: !x.done } : x)))}
                accessibilityRole="checkbox"
                accessibilityState={{ checked: c.done }}
                accessibilityLabel={c.text}
                hitSlop={8}
              >
                <Dot on={c.done} />
              </Pressable>
              <Text numberOfLines={1} style={[st.itemT, c.done && st.itemDone]}>
                {c.text}
              </Text>
              <Pressable onPress={() => setItems((l) => l.filter((_, j) => j !== i))} accessibilityRole="button" accessibilityLabel={`${c.text} 지우기`} hitSlop={6}>
                {({ hovered }: Hover) => <Text style={[st.x, hovered && { color: INK }]}>×</Text>}
              </Pressable>
            </View>
          ))}
          <View style={st.sep} />
          <View style={st.item}>
            <View style={st.plus}>
              <Text style={st.plusT}>+</Text>
            </View>
            <TextInput
              value={add}
              onChangeText={setAdd}
              onSubmitEditing={push}
              blurOnSubmit={false}
              placeholder="항목 추가 · Enter로 바로 추가"
              placeholderTextColor="#9AA3B2"
              accessibilityLabel="항목 추가"
              style={st.addIn}
            />
          </View>
        </View>
      </ScrollView>
      <View style={st.aiWrap}>
        <View style={st.ai}>
          <View style={st.i}>
            <Text style={st.iT}>i</Text>
          </View>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text style={st.aiT}>AI 연결 없음</Text>
            <Text style={st.aiS}>체크리스트는 보드에만 저장되고, 뉴스·공시와 연결되지 않아요.</Text>
          </View>
        </View>
      </View>
      <Actions note="저장 후에도 언제든 고칠 수 있어요" ok="체크리스트 저장" onCancel={onCancel} onOk={save} pl={24} />
    </>
  );
}

/** 원본 CheckDot: 18 · 끔 테두리 #D1D6DE · 켬 #14171C 채움 + 흰 체크 */
function Dot({ on }: { on: boolean }) {
  return (
    <Svg width={18} height={18} viewBox="0 0 18 18">
      {on ? (
        <>
          <Circle cx={9} cy={9} r={9} fill="#14171C" />
          <Path d="M5.2 9.2l2.4 2.4 5-5" stroke="#FFFFFF" strokeWidth={1.6} fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </>
      ) : (
        <Circle cx={9} cy={9} r={8.3} stroke="#D1D6DE" strokeWidth={1.4} fill="none" />
      )}
    </Svg>
  );
}

/** 원본 Ring (창 안 색: 바탕 #E8ECF3 · 진행 #14171C) */
function Ring({ done, n }: { done: number; n: number }) {
  const C = 2 * Math.PI * 7;
  return (
    <Svg width={18} height={18} viewBox="0 0 18 18">
      <Circle cx={9} cy={9} r={7} stroke="#E8ECF3" strokeWidth={2.4} fill="none" />
      {done ? (
        <Circle cx={9} cy={9} r={7} stroke="#14171C" strokeWidth={2.4} fill="none" strokeLinecap="round" strokeDasharray={`${C}`} strokeDashoffset={C * (1 - (n ? done / n : 0))} transform="rotate(-90 9 9)" />
      ) : null}
    </Svg>
  );
}

const st = StyleSheet.create({
  body: { flexShrink: 1, minHeight: 0 },
  bodyIn: { paddingTop: 8, paddingHorizontal: 24, paddingBottom: 16, gap: 12 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  label: { ...fpx(17, 26), fontWeight: '700', color: INK },
  hint: { ...fpx(13, 20), fontWeight: '500', color: '#747D8D' },
  count: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  titleIn: { height: 48, borderRadius: 12, borderWidth: 1, borderColor: '#E8ECF3', backgroundColor: '#FAFBFC', paddingHorizontal: 16, ...fpx(15, 23), fontWeight: '700', color: INK },
  list: { borderRadius: 16, borderWidth: 1, borderColor: '#E8ECF3', backgroundColor: '#FFFFFF', paddingHorizontal: 16, paddingVertical: 4 },
  item: { height: 44, flexDirection: 'row', alignItems: 'center', gap: 12 },
  itemT: { flex: 1, minWidth: 0, ...fpx(15, 23), color: '#333D4B' },
  itemDone: { color: '#9AA3B2', textDecorationLine: 'line-through' },
  x: { ...fpx(20, 29), fontWeight: '500', color: '#9AA3B2' },
  sep: { height: 1, backgroundColor: '#E8ECF3' },
  plus: { width: 18, height: 18, borderRadius: 5, borderWidth: 1, borderStyle: 'dashed', borderColor: '#D1D6DE', alignItems: 'center', justifyContent: 'center' },
  plusT: { ...fpx(13, 20), fontWeight: '500', color: '#9AA3B2' },
  addIn: { flex: 1, minWidth: 0, ...fpx(15, 23), color: '#333D4B' },
  aiWrap: { paddingHorizontal: 24, paddingVertical: 12 },
  ai: { flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 12, backgroundColor: '#F2F3F4', paddingHorizontal: 16, paddingVertical: 12 },
  i: { width: 20, height: 20, borderRadius: 10, borderWidth: 1, borderColor: '#9AA3B2', alignItems: 'center', justifyContent: 'center' },
  iT: { ...fpx(13, 20), fontWeight: '700', color: '#747D8D' },
  aiT: { ...fpx(17, 26), fontWeight: '500', color: INK },
  aiS: { ...fpx(14, 21), fontWeight: '500', color: '#4E5968' },
});
