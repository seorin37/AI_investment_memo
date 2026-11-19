/**
 * 내 종목 — 설명 · 필터 칩(전체 · 보유 N · 관심 N) · [+ 종목 추가] · 보유/관심 묶음(로고 · 이름 · 새 소식 · 메모 수 · 종가 · 등락).
 * 체험판 stock.html — 움직임:
 *  - 필터 칩 알약이 미끄러짐(#039) · 묶음 · 줄이 차례로 떠오름
 *  - 순서 바꾸기(reorder_mode): ⋮⋮ 를 끌면 줄이 따라오고 다른 줄이 비켜 남 (#317 · .6s) · 끄는 동안 화면 스크롤 멈춤
 */
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View, type GestureResponderHandlers } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { Appear, PopWhen } from '@/components/motion/Appear';
import { SlidingPill } from '@/components/motion/SlidingPill';
import { SortableList } from '@/components/motion/SortableList';
import type { MyStockRow, MyStocksFilter, MyStocksProps } from '@/features/stock/MyStocks.types';

const C = {
  appBg: '#F3F4F6',
  card: '#FFFFFF',
  row: '#F6F7F9',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  up: '#E5484D',
  down: '#2F6BDB',
  red: '#E5484D',
  white: '#FFFFFF',
  accent: '#8569E3',
  chipLine: '#E3E5EA',
  holdBg: '#E4ECFF', hold: '#3D73F0',
  watchBg: '#FFF1C9', watch: '#B07800',
} as const;
const PAD = 16;
const GAP = 14;
const R = { card: 20, row: 16 };
const ROW_H = 66;
const ROW_STEP = ROW_H + 8;

export function MyStocks({ stocks, close_date, onOpenStock, onAddStock, onLongPressStock, reorder_mode, onReorder, onScroll }: MyStocksProps) {
  const [filter, setFilter] = useState<MyStocksFilter>('all');
  const [dragging, setDragging] = useState(false);
  const hold = stocks.filter((s) => s.status === 'holding');
  const watch = stocks.filter((s) => s.status === 'watching');
  const groups: { key: 'holding' | 'watching'; label: string; list: MyStockRow[] }[] = [
    { key: 'holding', label: '보유', list: hold },
    { key: 'watching', label: '관심', list: watch },
  ];
  return (
    <ScrollView style={st.root} contentContainerStyle={st.body} onScroll={onScroll} scrollEventThrottle={16} scrollEnabled={!dragging}>
      <Text style={st.sub}>관심을 둔 이유까지, 메모와 함께 보관해요</Text>
      <View style={st.frow}>
        <SlidingPill<MyStocksFilter> value={filter} onChange={setFilter} gap={6} itemStyle={st.chip} itemOnStyle={st.chipOn} pillStyle={st.chipPill} textStyle={st.chipText} textOnStyle={st.chipTextOn}
          items={[{ key: 'all', label: '전체' }, { key: 'holding', label: `보유 ${hold.length}` }, { key: 'watching', label: `관심 ${watch.length}` }]} />
        <View style={st.flex} />
        <Pressable style={st.addBtn} onPress={onAddStock} accessibilityRole="button">
          <MobileIcon name="plus" size={16} color={C.text} strokeWidth={2.2} />
          <Text style={st.addText}>종목 추가</Text>
        </Pressable>
      </View>

      {stocks.length === 0 && (
        <Appear kind="rise" style={st.empty}>
          <Text style={st.emptyTitle}>아직 담은 종목이 없어요</Text>
          <Text style={st.emptyText}>관심 있는 종목을 추가하고 메모를 남겨 보세요</Text>
        </Appear>
      )}

      {groups.filter((g) => (filter === 'all' || filter === g.key) && g.list.length > 0).map((g, gi) => (
        <Appear key={g.key} kind="up" index={gi} replay={filter} style={st.card}>
          <View style={st.gh}>
            <View style={[st.ghIc, { backgroundColor: g.key === 'holding' ? C.holdBg : C.watchBg }]}>
              <MobileIcon name={g.key} size={16} color={g.key === 'holding' ? C.hold : C.watch} />
            </View>
            <Text style={st.ghText}>{g.label}</Text>
            <Text style={st.ghCount}>{g.list.length}종목</Text>
          </View>
          {reorder_mode ? (
            <SortableList data={g.list} keyOf={(s) => s.stock_code} row_height={ROW_STEP} enabled onDragging={setDragging}
              onReorder={(codes) => onReorder?.(g.key, codes)}
              renderRow={(s, d) => <Row s={s} handle={d.handle} lifted={d.lifted} onPress={() => {}} onLongPress={() => {}} />} />
          ) : (
            g.list.map((s, i) => (
              <Appear key={s.stock_code} kind="up" index={i + 1} replay={filter} style={st.rowGap}>
                <Row s={s} onPress={() => onOpenStock(s.stock_code)} onLongPress={() => onLongPressStock(s.stock_code)} />
              </Appear>
            ))
          )}
        </Appear>
      ))}

      <Text style={st.note}>시세는 {close_date} 종가 기준이에요</Text>
      <Text style={st.note}>종목을 꾹 누르면 여러 개를 옮기거나 빼고, 순서를 바꿀 수 있어요</Text>
    </ScrollView>
  );
}

function Row({ s, onPress, onLongPress, handle, lifted }: { s: MyStockRow; onPress: () => void; onLongPress: () => void; handle?: GestureResponderHandlers; lifted?: boolean }) {
  const up = s.change_rate >= 0;
  return (
    <Pressable style={[st.row, lifted && st.rowLifted]} onPress={onPress} onLongPress={onLongPress} delayLongPress={480} accessibilityRole="button" disabled={!!handle}>
      <View style={[st.logo, { backgroundColor: s.logo_bg }]}><Text style={[st.logoText, { color: s.logo_fg ?? C.white }]}>{s.logo_text}</Text></View>
      <View style={st.flex}>
        <View style={st.nameRow}>
          <Text style={st.name} numberOfLines={1}>{s.name}</Text>
          <PopWhen show={s.new_count > 0} replay={s.new_count} style={st.nb}><Text style={st.nbText}>{s.new_count}</Text></PopWhen>
        </View>
        <Text style={st.meta} numberOfLines={1}>{s.ai_unavailable ? `메모 ${s.memo_count} · AI 연결 준비 중` : `메모 ${s.memo_count} · AI 연결 ${s.ai_memo_count}`}</Text>
      </View>
      <View style={st.priceCol}>
        <Text style={st.price}>{s.close.toLocaleString('ko-KR')}원</Text>
        <Text style={[st.chg, { color: up ? C.up : C.down }]}>{up ? '+' : ''}{s.change_rate.toFixed(2)}%</Text>
      </View>
      {handle && (
        <View style={st.handle} {...handle} accessibilityLabel={`${s.name} 순서 바꾸기 손잡이`}>
          <MobileIcon name="drag" size={20} color={C.muted} />
        </View>
      )}
    </Pressable>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.appBg },
  flex: { flex: 1, minWidth: 0 },
  body: { paddingHorizontal: PAD, paddingBottom: 40, gap: GAP },
  sub: { fontSize: 14, color: C.sub, marginTop: 4 },
  frow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: -4 },
  chip: { height: 36, borderRadius: 18, paddingHorizontal: 14, borderWidth: 1, borderColor: C.chipLine, marginVertical: 4 },
  chipOn: { borderColor: C.accent },
  chipPill: { backgroundColor: C.accent, borderRadius: 18 },
  chipText: { fontSize: 14, fontWeight: '700', color: C.sub },
  chipTextOn: { color: C.white },
  addBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, height: 44, paddingHorizontal: 14, borderRadius: 22, backgroundColor: C.card },
  addText: { fontSize: 14, fontWeight: '700', color: C.text },
  card: { backgroundColor: C.card, borderRadius: R.card, padding: 16, paddingBottom: 8 },
  gh: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  rowGap: { marginBottom: 8 },
  rowLifted: { backgroundColor: C.card },
  handle: { width: 44, height: 44, marginRight: -8, alignItems: 'center', justifyContent: 'center' },
  ghIc: { width: 30, height: 30, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  ghText: { flex: 1, fontSize: 17, fontWeight: '800', color: C.text },
  ghCount: { fontSize: 12.5, color: C.muted },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: C.row, borderRadius: R.row, paddingHorizontal: 12, height: ROW_H },
  logo: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  logoText: { fontSize: 16, fontWeight: '800' },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  name: { fontSize: 16, fontWeight: '800', color: C.text, flexShrink: 1 },
  nb: { minWidth: 20, height: 20, borderRadius: 10, backgroundColor: C.red, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5 },
  nbText: { fontSize: 11.5, fontWeight: '700', color: C.white },
  meta: { fontSize: 12.5, color: C.sub, marginTop: 2 },
  priceCol: { alignItems: 'flex-end' },
  price: { fontSize: 15.5, fontWeight: '800', color: C.text },
  chg: { fontSize: 13, fontWeight: '600', marginTop: 2 },
  empty: { backgroundColor: C.card, borderRadius: R.card, padding: 28, alignItems: 'center' },
  emptyTitle: { fontSize: 16, fontWeight: '800', color: C.text },
  emptyText: { fontSize: 13.5, color: C.sub, marginTop: 6 },
  note: { textAlign: 'center', fontSize: 12, color: C.muted, marginTop: -6 },
});
