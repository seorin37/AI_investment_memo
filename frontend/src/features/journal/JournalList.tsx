/**
 * 투자 기록 — 검색칸(+ 받아쓰기) · 새 기록 버튼 · 고정됨 / 기간별 묶음 · N개의 기록.
 * 체험판 journal.html — 움직임:
 *  - 검색칸을 누르면 칸이 넓어지고 새 기록 버튼은 접히며 [취소]가 나옴 (#027 · .35s)
 *  - 결과가 없으면 돋보기가 갸웃하며 안내가 떠오름 (#092)
 *  - 묶음 제목을 누르면 접고 펼침(.42s) · 줄이 차례로 떠오름 · 기록 수가 올라감(#098)
 *  - 줄 밀기: 오른쪽 → 주황 "고정"(70px 넘으면 아이콘이 커지고 놓으면 고정) · 왼쪽 → [휴지통] 88px (끝까지 밀어도 바로 지우지 않음) (11.18 스와이프 허용 결정)
 *  - 줄을 꾹 누르면 onLongPress (고르기)
 */
import { useEffect, useRef, useState } from 'react';
import { Animated, Keyboard, Pressable, ScrollView, StyleSheet, Text, TextInput, View, type TextInputInstance } from 'react-native';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { Appear } from '@/components/motion/Appear';
import { Chevron, Collapse } from '@/components/motion/Collapse';
import { CountUp } from '@/components/motion/CountUp';
import { EASE, tween, useValue } from '@/components/motion/motion';
import { NoResults } from '@/components/motion/StateMotion';
import { SwipeRow } from '@/components/motion/SwipeRow';
import type { JournalListProps, JournalNote } from '@/features/journal/JournalList.types';
import { useBackClose } from '@/hooks/useBackClose';

const C = {
  appBg: '#F3F4F6',
  card: '#FFFFFF',
  search: '#E8EAEE',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  line: '#EEF0F3',
  accentDeep: '#6A42AB',
  accentSoft: '#EEE9FB',
  pinSwipe: '#F29A1F',
  red: '#E5484D',
} as const;
const PAD = 16;
const R = { card: 20, search: 12 };

export function JournalList({ notes, onOpen, onNew, onDictate, onLongPress, onPin, onDelete, onScroll }: JournalListProps) {
  const [openRow, setOpenRow] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [focus, setFocus] = useState(false);
  const [closed, setClosed] = useState<string[]>([]);
  const inputRef = useRef<TextInputInstance>(null);
  /* 안드로이드 뒤로가기: 밀린 줄 닫기 → 검색 닫기 순서로 먼저 처리 */
  useBackClose(() => {
    if (openRow) { setOpenRow(null); return true; }
    if (focus) { inputRef.current?.blur(); Keyboard.dismiss(); setFocus(false); return true; }
    return false;
  });
  /** #027: 0 = 평소(새 기록 버튼) · 1 = 검색 중([취소]) */
  const f = useValue(0);
  useEffect(() => { tween(f, focus ? 1 : 0, 350, EASE, false).start(); }, [focus, f]);
  const list = q.trim() ? notes.filter((n) => (n.title + n.preview).includes(q.trim())) : notes;
  const pins = list.filter((n) => n.pinned);
  const groups: { name: string; items: JournalNote[] }[] = [];
  list.filter((n) => !n.pinned).forEach((n) => {
    const g = groups.find((x) => x.name === n.group);
    if (g) g.items.push(n); else groups.push({ name: n.group, items: [n] });
  });
  if (pins.length) groups.unshift({ name: '고정됨', items: pins });

  return (
    <ScrollView style={st.root} contentContainerStyle={st.body} onScroll={onScroll} scrollEventThrottle={16} keyboardShouldPersistTaps="handled">
      <View style={st.searchRow}>
        <View style={st.search}>
          <MobileIcon name="search" size={18} color={C.muted} />
          <TextInput ref={inputRef} style={st.input} value={q} onChangeText={setQ} placeholder="검색" placeholderTextColor={C.muted} returnKeyType="search"
            onFocus={() => setFocus(true)} onBlur={() => { if (!q) setFocus(false); }} />
          {!!onDictate && (
            <Pressable onPress={onDictate} hitSlop={{ top: 11, bottom: 11, left: 13, right: 13 }} accessibilityLabel="받아쓰기">
              <MobileIcon name="mic" size={18} color={C.muted} />
            </Pressable>
          )}
        </View>
        <Animated.View pointerEvents={focus ? 'none' : 'auto'} style={[st.newWrap, { width: f.interpolate({ inputRange: [0, 1], outputRange: [44, 0] }), opacity: f.interpolate({ inputRange: [0, 0.5], outputRange: [1, 0], extrapolate: 'clamp' }) }]}>
          <Pressable style={st.newBtn} onPress={onNew} accessibilityLabel="새 기록">
            <MobileIcon name="edit" size={22} color={C.accentDeep} />
          </Pressable>
        </Animated.View>
        <Animated.View pointerEvents={focus ? 'auto' : 'none'} style={[st.cancelWrap, { width: f.interpolate({ inputRange: [0, 1], outputRange: [0, 52] }), opacity: f.interpolate({ inputRange: [0.5, 1], outputRange: [0, 1], extrapolate: 'clamp' }) }]}>
          <Pressable style={st.cancel} onPress={() => { setQ(''); Keyboard.dismiss(); setFocus(false); }} accessibilityRole="button">
            <Text style={st.cancelText} numberOfLines={1}>취소</Text>
          </Pressable>
        </Animated.View>
      </View>

      {list.length === 0 ? (
        q ? (
          <NoResults query={q.trim()} hint="다른 낱말로 찾아보세요" iconColor={C.accentDeep} iconBg={C.accentSoft} titleStyle={st.emptyTitle} hintStyle={st.emptyText} />
        ) : (
          <Appear kind="rise" style={st.empty}>
            <Text style={st.emptyTitle}>아직 기록이 없어요</Text>
            <Text style={st.emptyText}>오늘 본 것, 다음에 확인할 것을{'\n'}나만의 투자 기록으로 남겨 보세요</Text>
          </Appear>
        )
      ) : groups.map((g, gi) => (
        <Appear key={g.name} kind="up" index={gi}>
          <Pressable style={st.ghRow} onPress={() => setClosed((c) => (c.includes(g.name) ? c.filter((x) => x !== g.name) : [...c, g.name]))}
            accessibilityRole="button" accessibilityState={{ expanded: !closed.includes(g.name) }}>
            <Text style={st.gh}>{g.name}</Text>
            <Text style={st.ghN}>{g.items.length}</Text>
            <Chevron open={!closed.includes(g.name)} color={C.muted} />
          </Pressable>
          <Collapse open={!closed.includes(g.name)}>
          <View style={st.card}>
            {g.items.map((n, i) => (
              <SwipeRow key={n.id} enabled={!!(onPin || onDelete)} open={openRow === n.id} onOpenChange={(o) => setOpenRow(o ? n.id : null)} left_max={70} action_width={88}
                left={onPin ? { label: n.pinned ? '고정 해제' : '고정', icon: 'pin', color: C.pinSwipe, onTrigger: () => onPin(n.id, !n.pinned) } : undefined}
                right={onDelete ? [{ key: 'del', label: '휴지통', icon: 'trash', color: C.red, onPress: () => onDelete(n.id) }] : []}>
              <Pressable style={[st.row, i > 0 && st.rowLine]} onPress={() => onOpen(n.id)} onLongPress={onLongPress ? () => onLongPress(n.id) : undefined} delayLongPress={480} accessibilityRole="button">
                <View style={st.titleRow}>
                  {n.pinned && <MobileIcon name="pin" size={14} color={C.sub} />}
                  <Text style={st.title} numberOfLines={1}>{n.title}</Text>
                </View>
                <Text style={st.sub} numberOfLines={1}>
                  <Text style={st.date}>{n.date_label}  </Text>
                  {n.preview || '추가 텍스트 없음'}
                </Text>
              </Pressable>
              </SwipeRow>
            ))}
          </View>
          </Collapse>
        </Appear>
      ))}
      <Text style={st.count}><CountUp value={list.length} style={st.count} />개의 기록</Text>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.appBg },
  body: { paddingHorizontal: PAD, paddingBottom: 40 },
  searchRow: { flexDirection: 'row', alignItems: 'center', marginTop: 4 },
  newWrap: { overflow: 'hidden', alignItems: 'flex-end' },
  cancelWrap: { overflow: 'hidden', alignItems: 'flex-end' },
  cancel: { height: 44, width: 52, alignItems: 'flex-end', justifyContent: 'center' },
  cancelText: { fontSize: 15, fontWeight: '700', color: C.accentDeep },
  ghRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 22, marginBottom: 10, minHeight: 44 },
  ghN: { flex: 1, fontSize: 14, fontWeight: '700', color: C.muted },
  search: { flex: 1, height: 44, borderRadius: R.search, backgroundColor: C.search, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, gap: 8, marginRight: 8 },
  input: { flex: 1, fontSize: 15, color: C.text, padding: 0 },
  newBtn: { width: 44, height: 44, borderRadius: R.search, backgroundColor: C.accentSoft, alignItems: 'center', justifyContent: 'center' },
  gh: { fontSize: 20, fontWeight: '800', color: C.text },
  card: { backgroundColor: C.card, borderRadius: R.card, paddingHorizontal: 16 },
  row: { paddingVertical: 14, minHeight: 64, backgroundColor: C.card },
  rowLine: { borderTopWidth: 1, borderTopColor: C.line },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  title: { flex: 1, fontSize: 16, fontWeight: '800', color: C.text },
  sub: { fontSize: 13, color: C.muted, marginTop: 4 },
  date: { color: C.sub, fontWeight: '600' },
  empty: { alignItems: 'center', paddingVertical: 60 },
  emptyTitle: { fontSize: 17, fontWeight: '800', color: C.text },
  emptyText: { fontSize: 14, lineHeight: 22, color: C.sub, textAlign: 'center', marginTop: 8 },
  count: { textAlign: 'center', fontSize: 12.5, color: C.muted, marginTop: 30 },
});
