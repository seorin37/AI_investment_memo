import React, { useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import type { Checklist, ChecklistItem } from '@/types/models';
import { AppPin, CheckMark, CkiMark } from '@/ui/icons/BoardGlyphs';
import { appColor, checklistColor, fpx, ft } from '@/ui/theme';
import { DotBurst } from '@/components/motion/Celebrate';
import { useChecklistTone } from './Dark';
import { SelCircle } from './MemoCard';
import { AppTape } from './MemoPaper';
import { ListCheck } from './MemoRow';

/**
 * 원본 11.17 검수: 안 한 항목 먼저, 체크한 줄은 0.7초 뒤 아래로 정리 (손가락 밑에서 바로 줄이 바뀌지 않게).
 * 카드가 정렬 순서를 들고 있다가 체크가 바뀌면 0.7초 뒤에 다시 정렬.
 */
const sortNow = (list: ChecklistItem[]) => [...list.filter((x) => !x.done), ...list.filter((x) => x.done)];
function useDelayedOrder(items: ChecklistItem[]): ChecklistItem[] {
  const [ids, setIds] = useState(() => sortNow(items).map((x) => x.id));
  useEffect(() => {
    const t = setTimeout(() => setIds(sortNow(items).map((x) => x.id)), 700);
    return () => clearTimeout(t);
  }, [items]);
  const byId = new Map(items.map((x) => [x.id, x]));
  const ordered = ids.map((id) => byId.get(id)).filter((x): x is ChecklistItem => !!x);
  const extra = items.filter((x) => !ids.includes(x.id));
  return [...extra, ...ordered];
}

export interface AppChecklistCardProps {
  checklist: Checklist;
  width: number;
  height: number;
  selecting: boolean;
  selected: boolean;
  onPress: () => void;
  onLongPress: () => void;
  onToggleItem: (id: string) => void;
}

/**
 * 앱 2열 체크리스트 카드 (원본 memo.html .item.ck .grid: 바탕 #FFEADB · 라운드 16 · 안쪽 14·13
 * 머리 22: 표 22 (라운드 7 #FFDCC4 · 체크 #C2410C) · 이름 14px 800 · 'n/N' 12px 700 #C2410C
 * 항목 (위 8 · 사이 6): 동그라미 17 (안쪽 1.6 #E9B48F · 흰 .7 / 한 것 #FF7A1A) · 12.5px · 한 것 #B49A8A 줄 긋기
 * 3개까지 + '+N개 더' 11.5px 600 #B07A55. 항목 줄을 누르면 체크, 그 밖을 누르면 체크리스트 화면)
 */
export function AppChecklistCard({ checklist, width, height, selecting, selected, onPress, onLongPress, onToggleItem, onAllDone }: AppChecklistCardProps & { onAllDone?: (center: { x: number; y: number }) => void }) {
  const L = checklist.items.length;
  /* 축하 (원본 memo.html toggleCk: 체크할 때 점이 튀고 · 마지막 항목이면 .32초 뒤 카드 가운데서 색종이) */
  const outer = useRef<React.ComponentRef<typeof View>>(null);
  const [pop, setPop] = useState<{ id: string; n: number } | null>(null);
  const toggle = (id: string) => {
    const it = checklist.items.find((x) => x.id === id);
    const was = checklist.items.every((x) => x.done);
    const will = checklist.items.every((x) => (x.id === id ? !x.done : x.done));
    if (it && !it.done) setPop((p) => ({ id, n: (p?.n ?? 0) + 1 }));
    onToggleItem(id);
    if (!was && will && onAllDone) setTimeout(() => outer.current?.measureInWindow((x, y, w, h) => onAllDone({ x: x + w / 2, y: y + h / 2 })), 320);
  };
  const d = checklist.items.filter((x) => x.done).length;
  const ord = useDelayedOrder(checklist.items);
  /* 다크면 원본 다크 체크리스트 색 (반전 전 값) */
  const tone = useChecklistTone();
  return (
    <View ref={outer} collapsable={false} style={{ width, height }}>
      <Pressable onPress={onPress} onLongPress={onLongPress} delayLongPress={480} accessibilityRole="button" accessibilityLabel={checklist.title || '체크리스트'} style={[st.face, { width, height, backgroundColor: tone.paper }, selected && st.faceSel]}>
        <View style={st.ckh}>
          <View style={st.cki}>
            <CkiMark size={14} />
          </View>
          <Text style={st.ckhT} numberOfLines={1}>
            {checklist.title || '체크리스트'}
          </Text>
          <Text style={[st.ckn, { color: tone.ink }]}>
            {d}/{L}
          </Text>
        </View>
        <View style={st.ckl}>
          {L ? (
            ord.slice(0, 3).map((x) => (
              <Pressable key={x.id} onPress={() => (selecting ? onPress() : toggle(x.id))} onLongPress={onLongPress} delayLongPress={480} accessibilityRole="checkbox" accessibilityState={{ checked: x.done }} accessibilityLabel={x.text} style={({ pressed }) => [st.cr, pressed && { backgroundColor: 'rgba(255,122,26,0.12)' }]}>
                <View style={[st.cc, x.done ? [st.ccOn, { backgroundColor: tone.tape }] : [st.ccOff, { borderColor: tone.cardBox, backgroundColor: tone.cardBoxBg }]]}>
                  {x.done ? <CheckMark kind="cki" size={11} stroke={1.9} /> : null}
                  <DotBurst fire={pop?.id === x.id ? pop.n : 0} size={17} />
                </View>
                <Text style={[st.ct, x.done && st.ctDone]} numberOfLines={1}>
                  {x.text}
                </Text>
              </Pressable>
            ))
          ) : (
            <Text style={[st.cmore, { paddingLeft: 0 }]}>확인할 일을 추가해 보세요</Text>
          )}
          {L > 3 ? <Text style={st.cmore}>+{L - 3}개 더</Text> : null}
        </View>
      </Pressable>
      {/* 원본 renderCheck: 고정하면 귤색 테이프 (메모와 같은 자리) */}
      {checklist.pinned ? <AppTape color={tone.tape} /> : null}
      <SelCircle visible={selecting} on={selected} style={st.gchk} />
    </View>
  );
}

/** 앱 목록 체크리스트 줄 (원본 .list .item.ck: 흰 바탕 · 아래 선 · 표 36 (라운드 11) · 이름 15.5px 800 · 'n/N 완료 · 다음 항목' 12.5px) */
export function AppChecklistRow({ checklist, width, selecting, selected, onPress, onLongPress }: Omit<AppChecklistCardProps, 'height' | 'onToggleItem'>) {
  const L = checklist.items.length;
  const d = checklist.items.filter((x) => x.done).length;
  const next = checklist.items.find((x) => !x.done)?.text ?? '모두 끝냈어요';
  return (
    <Pressable onPress={onPress} onLongPress={onLongPress} delayLongPress={480} accessibilityRole="button" accessibilityLabel={checklist.title || '체크리스트'} style={({ pressed }) => [st.row, { width, backgroundColor: selected ? '#F4F0FF' : pressed ? '#F1F1F4' : '#FFFFFF' }]}>
      <ListCheck visible={selecting} on={selected} />
      <View style={st.ckiBig}>
        <CkiMark size={18} />
      </View>
      <View style={st.lt}>
        <View style={st.aRow}>
          {checklist.pinned ? <AppPin size={14} color={appColor.ink2} /> : null}
          <Text style={st.aT} numberOfLines={1}>
            {checklist.title || '체크리스트'}
          </Text>
        </View>
        <Text style={st.b} numberOfLines={1}>
          {L ? `${d}/${L} 완료 · ${next}` : '확인할 일을 추가해 보세요'}
        </Text>
      </View>
    </Pressable>
  );
}

/** 웹 진행 고리 (원본 board.tsx Ring: 34 · r14 · 선 3 · 바탕 #ECEAF1 · 진행 #AB98CD · 글자 11/16 500 #777080) */
function Ring({ done, n }: { done: number; n: number }) {
  const C = 2 * Math.PI * 14;
  return (
    <View style={st.ring}>
      <Svg width={34} height={34} viewBox="0 0 34 34" style={StyleSheet.absoluteFill}>
        <Circle cx={17} cy={17} r={14} stroke="#ECEAF1" strokeWidth={3} fill="none" />
        {done ? <Circle cx={17} cy={17} r={14} stroke="#AB98CD" strokeWidth={3} fill="none" strokeLinecap="round" strokeDasharray={`${C}`} strokeDashoffset={C * (1 - (n ? done / n : 0))} transform="rotate(-90 17 17)" /> : null}
      </Svg>
      <Text style={st.ringT}>
        {done}/{n}
      </Text>
    </View>
  );
}

/**
 * 웹 체크리스트 카드 (원본 board.tsx ChecklistCard: 276 칸 · 높이 200 · 라운드 16 · 테두리 #EBE9ED · 흰 · 좌우 20 · 위 16 · 아래 8
 * 이름 17/26 bold #191F28 · '하나씩 확인해 보세요' 13/20 #8A8592 · 고리 34
 * 항목 줄 40 (위 선 #F0EEF2 · 사이 10): 동그라미 18 (안쪽 1.4 #D8D4DE / 한 것 #ADA0C5) · 15/23 #3D3945 (한 것 #A29DA9 줄 긋기)
 * 4개 이상이면 2개 + '외 N개 더 있어요 · 눌러서 모두 보기' 14/21 500 #8A8592)
 */
export function WebChecklistCard({ checklist, onOpen, onToggleItem }: { checklist: Checklist; onOpen: () => void; onToggleItem: (id: string) => void }) {
  const L = checklist.items.length;
  const d = checklist.items.filter((x) => x.done).length;
  const shown = L > 3 ? checklist.items.slice(0, 2) : checklist.items;
  return (
    <Pressable onPress={onOpen} accessibilityLabel={checklist.title} style={st.web}>
      <View style={st.webHead}>
        <View style={st.webHeadT}>
          <Text style={st.webTitle}>{checklist.title}</Text>
          <Text style={st.webSub}>하나씩 확인해 보세요</Text>
        </View>
        <Ring done={d} n={L} />
      </View>
      {shown.map((c) => (
        <View key={c.id} style={st.webRow}>
          <Pressable onPress={() => onToggleItem(c.id)} accessibilityRole="checkbox" accessibilityState={{ checked: c.done }} accessibilityLabel={c.text} style={[st.dot, c.done ? { backgroundColor: '#ADA0C5' } : st.dotOff]}>
            {c.done ? <CheckMark kind="cki" size={12} stroke={1.6} /> : null}
          </Pressable>
          <Text style={[st.webItem, c.done && st.webItemDone]} numberOfLines={1}>
            {c.text}
          </Text>
        </View>
      ))}
      {L > 3 ? <Text style={st.webMore}>외 {L - 2}개 더 있어요 · 눌러서 모두 보기</Text> : null}
    </Pressable>
  );
}

const st = StyleSheet.create({
  face: { borderRadius: 16, backgroundColor: checklistColor.paper, paddingTop: 14, paddingHorizontal: 13, overflow: 'hidden' },
  faceSel: { borderWidth: 2.5, borderColor: appColor.accent, paddingTop: 11.5, paddingHorizontal: 10.5 },
  ckh: { flexDirection: 'row', alignItems: 'center', gap: 6, height: 22 },
  cki: { width: 22, height: 22, borderRadius: 7, backgroundColor: '#FFDCC4', alignItems: 'center', justifyContent: 'center' },
  ckhT: { ...ft(14), fontWeight: '800', color: appColor.ink, flexShrink: 1 },
  ckn: { marginLeft: 'auto', ...ft(12), fontWeight: '700', color: checklistColor.ink },
  ckl: { marginTop: 8, gap: 6 },
  cr: { flexDirection: 'row', alignItems: 'center', gap: 7, paddingVertical: 2, paddingHorizontal: 4, marginVertical: -2, marginHorizontal: -4, borderRadius: 8, minWidth: 0 },
  cc: { width: 17, height: 17, borderRadius: 8.5, alignItems: 'center', justifyContent: 'center' },
  ccOff: { backgroundColor: 'rgba(255,255,255,0.7)', borderWidth: 1.6, borderColor: '#E9B48F' },
  ccOn: { backgroundColor: checklistColor.tape },
  ct: { ...ft(12.5), color: appColor.ink, flexShrink: 1 },
  ctDone: { color: '#B49A8A', textDecorationLine: 'line-through' },
  cmore: { ...ft(11.5), fontWeight: '600', color: '#B07A55', paddingLeft: 24 },
  gchk: { position: 'absolute', top: -10, left: -8 },
  row: { height: 64, flexDirection: 'row', alignItems: 'center', gap: 12, paddingLeft: 20, paddingRight: 16, borderBottomWidth: 1, borderBottomColor: appColor.line },
  ckiBig: { width: 36, height: 36, borderRadius: 11, backgroundColor: '#FFDCC4', alignItems: 'center', justifyContent: 'center' },
  lt: { flex: 1, minWidth: 0 },
  aRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  aT: { ...ft(15.5), fontWeight: '800', color: appColor.ink, flexShrink: 1 },
  b: { ...ft(12.5), color: appColor.ink2, marginTop: 2 },
  ring: { width: 34, height: 34, alignItems: 'center', justifyContent: 'center' },
  ringT: { ...fpx(11, 16), fontWeight: '500', color: '#777080' },
  web: { width: 276, height: 200, overflow: 'hidden', borderRadius: 16, borderWidth: 1, borderColor: '#EBE9ED', backgroundColor: '#FFFFFF', paddingHorizontal: 20, paddingBottom: 8, paddingTop: 16 },
  webHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 8 },
  webHeadT: { gap: 1 },
  webTitle: { ...fpx(17, 26), fontWeight: '700', color: '#191F28' },
  webSub: { ...fpx(13, 20), color: '#8A8592' },
  webRow: { height: 40, flexDirection: 'row', alignItems: 'center', gap: 10, borderTopWidth: 1, borderTopColor: '#F0EEF2' },
  dot: { width: 18, height: 18, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  dotOff: { borderWidth: 1.4, borderColor: '#D8D4DE' },
  webItem: { ...fpx(15, 23), color: '#3D3945', flexShrink: 1 },
  webItemDone: { color: '#A29DA9', textDecorationLine: 'line-through' },
  webMore: { height: 40, borderTopWidth: 1, borderTopColor: '#F0EEF2', ...fpx(14, 40), fontWeight: '500', color: '#8A8592' },
});
