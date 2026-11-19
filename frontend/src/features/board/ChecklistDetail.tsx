/* eslint-disable react-hooks/refs -- RN Animated 관용 패턴. React Compiler 켜면 이 파일부터 정리 필요 */
/**
 * 체크리스트 — 귤색 종이 위에 이름(바로 수정) · 작성일 · 진행 수 · 막대 · 항목 줄(체크 · ×) · 맨 끝 "항목 추가" 줄.
 * 다 끝내면 "모두 확인했어요" 배지. AI 연결은 없음.
 * 움직임 (체험판 memo.html · Lucian #093 · #014):
 *  - 체크: 상자가 .6 → 1.15 → 1 로 톡 · 안이 번지며 채워지고 · 둘레로 점 8개 · 글자에 줄이 그어짐(.35s)
 *  - 막대가 spring 으로 차오름(.6s) · 새 항목은 위에서 8px 내려오며(.45s spring)
 *  - 마지막 항목: "모두 확인했어요" 칸이 펼쳐지고(.45s) 배지가 돌며 튀어나와 물결(1.1s) · 색종이 90개
 */
import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, View, type LayoutChangeEvent, type TextInputInstance } from 'react-native';
import { Text, TextInput } from '@/components/ui/AppText';
import Svg, { Polygon } from 'react-native-svg';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { Appear } from '@/components/motion/Appear';
import { Confetti } from '@/components/motion/Celebrate';
import { Collapse } from '@/components/motion/Collapse';
import { InkCheck } from '@/components/motion/InkCheck';
import { EASE, ND, SPRING, tween, useValue } from '@/components/motion/motion';
import { BOARD_C as C, CHECKLIST_C as CK } from '@/features/board/boardTokens';
import type { ChecklistDetailProps } from '@/features/board/ChecklistDetail.types';

const PAD = 16;
const R = { paper: 22, box: 8, win: 16, badge: 16 };

export function ChecklistDetail({ mode, title, date_full, items, pinned, onChangeTitle, onToggleItem, onDeleteItem, onAddItem, onAllDone }: ChecklistDetailProps) {
  const [draft, setDraft] = useState('');
  const inputRef = useRef<TextInputInstance>(null);
  const L = items.length;
  const d = items.filter((x) => x.done).length;
  const all = L > 0 && d === L;
  const [W, setW] = useState(0);
  const [confetti, setConfetti] = useState<{ x: number; y: number; id: number } | null>(null);
  const bar = useValue(L ? d / L : 0);
  useEffect(() => { tween(bar, L ? d / L : 0, 600, SPRING, false).start(); }, [d, L, bar]);
  /** 처음부터 있던 줄은 그대로, 나중에 더한 줄만 내려오며 나타남 */
  const known = useRef(new Set(items.map((x) => x.id)));
  const wasAll = useRef(all);
  useEffect(() => {
    if (all && !wasAll.current) setTimeout(() => setConfetti({ x: W / 2, y: 120, id: Date.now() }), 320);
    wasAll.current = all;
  }, [all, W]);

  const add = () => {
    const v = draft.trim();
    if (!v) return;
    onAddItem(v);
    setDraft('');
    inputRef.current?.focus();
  };
  const toggle = (id: string) => {
    const it = items.find((x) => x.id === id);
    onToggleItem(id);
    if (it && !it.done && d + 1 === L) onAllDone?.();
  };

  return (
    <View style={st.root} onLayout={(e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width)}>
    <ScrollView style={st.root} contentContainerStyle={st.body} keyboardShouldPersistTaps="handled">
      <View style={st.paper}>
        {pinned && mode === 'edit' && (
          <Svg width={57} height={19} style={st.tape}>
            <Polygon points="0,0 57,0 54.7,3.2 57,6.3 54.7,9.5 57,12.7 54.7,15.8 57,19 0,19 2.3,15.8 0,12.7 2.3,9.5 0,6.3 2.3,3.2" fill={CK.tape} fillOpacity={0.82} />
          </Svg>
        )}
        <TextInput style={st.title} value={title} onChangeText={onChangeTitle} maxLength={20} accessibilityLabel="체크리스트 이름" />
        <View style={st.meta}>
          <Text style={st.metaText}>{date_full}</Text>
          <Text style={st.count}>{d} / {L}</Text>
        </View>
        <View style={st.bar}><Animated.View style={[st.barFill, { width: bar.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'], extrapolate: 'clamp' }) }]} /></View>

        <Collapse open={all} duration={450}>
          <WinBadge on={all} />
        </Collapse>

        {items.map((x) => {
          const row = (
            <View style={st.row}>
              <Pressable style={st.rowBtn} onPress={() => toggle(x.id)} accessibilityRole="checkbox" accessibilityState={{ checked: x.done }}>
                <InkCheck checked={x.done} color={CK.check} lineColor={CK.boxLine} bg={C.card} size={24} radius={R.box} burst />
                <StrikeText text={x.text} done={x.done} />
              </Pressable>
              <Pressable style={st.del} onPress={() => onDeleteItem(x.id)} accessibilityLabel="항목 지우기">
                <MobileIcon name="close" size={16} color={CK.more} />
              </Pressable>
            </View>
          );
          return known.current.has(x.id) ? <View key={x.id}>{row}</View> : <Appear key={x.id} kind="drop">{row}</Appear>;
        })}

        <Pressable style={st.addRow} onPress={() => inputRef.current?.focus()}>
          <View style={st.plus}><MobileIcon name="plus" size={14} color={CK.deep} strokeWidth={2.6} /></View>
          <TextInput
            ref={inputRef}
            style={st.addInput}
            value={draft}
            onChangeText={setDraft}
            onSubmitEditing={add}
            submitBehavior="submit"
            returnKeyType="done"
            maxLength={40}
            autoFocus={mode === 'new'}
            placeholder={L ? '항목 추가' : '확인할 일을 한 줄씩 적어 보세요'}
            placeholderTextColor={CK.more}
          />
        </Pressable>
      </View>
      <Text style={st.note}>체크리스트는 AI 연결 없이 나만 보는 확인 목록이에요</Text>
    </ScrollView>
    <Confetti fire={confetti} />
    </View>
  );
}

/** 글자에 줄이 왼쪽부터 그어짐 (.35s) · 글자색은 흐려짐 */
function StrikeText({ text, done }: { text: string; done: boolean }) {
  const t = useValue(done ? 1 : 0);
  useEffect(() => { tween(t, done ? 1 : 0, 350, EASE, false).start(); }, [done, t]);
  return (
    <View style={st.flex}>
      <Text style={[st.itemText, done && st.itemDone]}>{text}</Text>
      <Animated.View pointerEvents="none" style={[st.strike, { width: t.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] }) }]} />
    </View>
  );
}

/** 모두 끝냄: 배지가 -25° · .3배에서 돌며 튀어나오고(.6s spring) .45초 뒤 물결이 퍼짐 */
function WinBadge({ on }: { on: boolean }) {
  const b = useValue(on ? 1 : 0);
  const wave = useValue(0);
  useEffect(() => {
    if (!on) { b.setValue(0); return; }
    b.setValue(0); wave.setValue(0);
    Animated.parallel([tween(b, 1, 600, SPRING, ND, 150), tween(wave, 1, 1100, EASE, ND, 450)]).start();
  }, [on, b, wave]);
  return (
    <View style={st.winWrap}><View style={st.win}>
      <View>
        <Animated.View pointerEvents="none" style={[st.winWave, { opacity: wave.interpolate({ inputRange: [0, 0.01, 1], outputRange: [0, 0.5, 0] }), transform: [{ scale: wave.interpolate({ inputRange: [0, 1], outputRange: [1, 1.95] }) }] }]} />
        <Animated.View style={[st.winBadge, { transform: [{ scale: b.interpolate({ inputRange: [0, 1], outputRange: [0.3, 1] }) }, { rotate: b.interpolate({ inputRange: [0, 1], outputRange: ['-25deg', '0deg'] }) }] }]}>
          <MobileIcon name="check" size={24} color={C.white} strokeWidth={2.6} />
        </Animated.View>
      </View>
      <View style={st.flex}>
        <Text style={st.winTitle}>모두 확인했어요</Text>
        <Text style={st.winSub}>다 끝낸 체크리스트도 보드에 그대로 남아요</Text>
      </View>
    </View></View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.card },
  flex: { flex: 1, minWidth: 0 },
  body: { padding: PAD, paddingBottom: 160 },
  paper: { borderRadius: R.paper, backgroundColor: CK.paper, paddingHorizontal: 18, paddingTop: 24, paddingBottom: 8 },
  tape: { position: 'absolute', top: -8, alignSelf: 'center', transform: [{ rotate: '-3deg' }] },
  title: { fontSize: 22, fontWeight: '800', color: C.text, padding: 0, minHeight: 32 },
  meta: { flexDirection: 'row', alignItems: 'center', marginTop: 6, marginBottom: 10 },
  metaText: { flex: 1, fontSize: 12.5, color: CK.meta },
  count: { fontSize: 14, fontWeight: '800', color: CK.deep },
  bar: { height: 8, borderRadius: 4, backgroundColor: CK.barTrack, overflow: 'hidden', marginBottom: 6 },
  barFill: { height: 8, borderRadius: 4, backgroundColor: CK.check },
  winWrap: { paddingTop: 12, paddingBottom: 6 },
  win: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: C.card, borderRadius: R.win, padding: 12 },
  winBadge: { width: 46, height: 46, borderRadius: R.badge, backgroundColor: CK.check, alignItems: 'center', justifyContent: 'center' },
  winWave: { position: 'absolute', left: 0, top: 0, width: 46, height: 46, borderRadius: R.badge, backgroundColor: CK.check },
  strike: { position: 'absolute', left: -2, top: '52%', height: 2, borderRadius: 1, backgroundColor: CK.doneText },
  winTitle: { fontSize: 16, fontWeight: '800', color: C.text },
  winSub: { fontSize: 12.5, color: C.sub, marginTop: 2 },
  row: { flexDirection: 'row', alignItems: 'center', borderBottomWidth: 1, borderBottomColor: CK.line },
  rowBtn: { flex: 1, minHeight: 54, flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 8 },
  itemText: { flex: 1, fontSize: 15.5, fontWeight: '600', color: C.text, lineHeight: 22 },
  itemDone: { color: CK.doneText },
  del: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  addRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56 },
  plus: { width: 24, height: 24, borderRadius: R.box, borderWidth: 2, borderStyle: 'dashed', borderColor: CK.boxLine, alignItems: 'center', justifyContent: 'center' },
  addInput: { flex: 1, fontSize: 15.5, color: C.text, minHeight: 44, padding: 0 },
  note: { textAlign: 'center', fontSize: 12, color: C.muted, marginTop: 14 },
});
