/**
 * 최신 업데이트 — 읽지 않은 소식 N건 · 종목 칩(새 소식 수) · 종류 칩(전체·공시·뉴스·주가 + 개수) · 종목별 카드(최대 3줄).
 * 체험판 update.html. 상단 바(최신 업데이트 · 모두 읽음 · 검색 · 알림 · 프로필)는 TopBar 로 따로.
 * 움직임: 종목 · 종류 칩 알약이 미끄러짐(#039) · 고르면 카드가 다시 차례로 떠오름 · 읽지 않은 수가 올라감(#098)
 *        · 읽으면 보라 점이 작아지며 사라짐 · 불러오는 동안 뼈대(#079) · 당겨서 새로고침(#085)
 */
import { useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { Appear, PopWhen } from '@/components/motion/Appear';
import { CountUp } from '@/components/motion/CountUp';
import { Shimmer, SkeletonSwap } from '@/components/motion/Skeleton';
import { SlidingPill } from '@/components/motion/SlidingPill';
import type { UpdateType } from '@/types/models';
import type { FeedStock, UpdateFeedProps } from '@/features/updates/UpdateFeed.types';

const C = {
  appBg: '#F3F4F6',
  card: '#FFFFFF',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  dark: '#16171A',
  white: '#FFFFFF',
  line: '#EEF0F3',
  chipLine: '#E3E5EA',
  red: '#E5484D',
  accent: '#8569E3',
  accentDeep: '#6A42AB',
  accentSoft: '#EEE9FB',
  tagBg: '#F1EEFA',
  warnBg: '#FFF6E0',
  warnText: '#7A4B00',
  gRed: '#FFE9E9', gRedText: '#B42318',
  gBlue: '#E4ECFF', gBlueText: '#2F6BDB',
  gGreen: '#E3F5EA', gGreenText: '#1B7A45',
  skeleton: '#E6E8EC',
} as const;
const PAD = 16;
const GAP = 14;
const R = { card: 20, chip: 16 };
const TYPE: Record<UpdateType, { label: string; bg: string; fg: string }> = {
  disclosure: { label: '공시', bg: C.gRed, fg: C.gRedText },
  news: { label: '뉴스', bg: C.gBlue, fg: C.gBlueText },
  price: { label: '주가', bg: C.gGreen, fg: C.gGreenText },
};
type Kind = 'all' | UpdateType;

export function UpdateFeed({ stocks, selected_stock, onSelectStock, onOpenStock, onOpenItem, ai_paused, loading, refreshing, onRefresh, onScroll }: UpdateFeedProps) {
  const [kind, setKind] = useState<Kind>('all');
  const unreadOf = (s: FeedStock) => s.items.filter((i) => i.unread).length;
  const total = stocks.reduce((a, s) => a + unreadOf(s), 0);
  const shownStocks = selected_stock ? stocks.filter((s) => s.stock_code === selected_stock) : stocks;
  const countOf = (k: Kind) => shownStocks.reduce((a, s) => a + s.items.filter((i) => k === 'all' || i.type === k).length, 0);

  return (
    <ScrollView style={st.root} contentContainerStyle={st.body} onScroll={onScroll} scrollEventThrottle={16}
      refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={C.accent} colors={[C.accent]} /> : undefined}>
      <Text style={st.sub}>내 종목의 공시·뉴스·주가 변동을 모아봤어요</Text>
      <View style={st.unread}>
        <View style={st.unreadDot} />
        <Text style={st.unreadText}>읽지 않은 소식 <Text style={st.unreadNum}><CountUp value={total} style={st.unreadNum} />건</Text></Text>
      </View>

      {ai_paused && (
        <Appear kind="up" style={st.paused}>
          <Text style={st.pausedTitle}>AI 업데이트가 잠시 멈췄어요</Text>
          <Text style={st.pausedText}>12월 1일부터 새 소식을 다시 찾아요</Text>
        </Appear>
      )}

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={st.chipRow}>
        <SlidingPill<string> value={selected_stock ?? '__all'} onChange={(k) => onSelectStock(k === '__all' ? null : k)} gap={6}
          itemStyle={st.chip} itemOnStyle={st.chipOnDark} pillStyle={st.pillDark}
          items={[{ key: '__all', label: '전체', render: (on: boolean) => <ChipBody label="전체" on={on} /> },
            ...stocks.map((s) => ({ key: s.stock_code, label: s.name, render: (on: boolean) => <ChipBody label={s.name} on={on} badge={unreadOf(s)} /> }))]} />
      </ScrollView>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={st.chipRow}>
        <SlidingPill<Kind> value={kind} onChange={setKind} gap={6} itemStyle={st.chip} itemOnStyle={st.chipOnDark} pillStyle={st.pillDark}
          items={(['all', 'disclosure', 'news', 'price'] as Kind[]).map((k) => ({ key: k, label: k === 'all' ? '전체' : TYPE[k].label,
            render: (on: boolean) => <ChipBody label={k === 'all' ? '전체' : TYPE[k].label} on={on} count={countOf(k)} /> }))} />
      </ScrollView>

      <SkeletonSwap loading={!!loading} skeleton={<View style={st.cards}>{[0, 1, 2].map((i) => <Shimmer key={i} style={st.skCard} offset_x={PAD} color={C.skeleton} />)}</View>}>
      <View style={st.cards}>
        {shownStocks.map((s, si) => {
          const rows = s.items.filter((i) => kind === 'all' || i.type === kind);
          return (
            <Appear key={s.stock_code} kind="up" index={si} replay={`${kind}|${selected_stock}`} style={st.card}>
              <Pressable style={st.hd} onPress={() => onOpenStock(s.stock_code)} accessibilityRole="button">
                <View style={[st.logo, { backgroundColor: s.logo_bg }]}><Text style={[st.logoText, { color: s.logo_fg ?? C.white }]}>{s.logo_text}</Text></View>
                <View style={st.flex}>
                  <View style={st.nameRow}>
                    <Text style={st.name} numberOfLines={1}>{s.name}</Text>
                    <View style={st.own}><Text style={st.ownText}>{s.status === 'holding' ? '보유' : '관심'}</Text></View>
                  </View>
                  <Text style={st.code}>{s.stock_code} · {s.market}</Text>
                </View>
                <MobileIcon name="chevron_right" size={18} color={C.muted} />
              </Pressable>
              {rows.length === 0 ? (
                <Text style={st.none}>{s.items.length ? '이 종류의 소식은 없어요' : '아직 업데이트가 없어요 · 메모를 AI와 연결해 보세요'}</Text>
              ) : rows.slice(0, 3).map((i) => (
                <Pressable key={i.id} style={st.lr} onPress={() => onOpenItem(s.stock_code, i.id)} accessibilityRole="button">
                  <View style={[st.tag, { backgroundColor: TYPE[i.type].bg }]}><Text style={[st.tagText, { color: TYPE[i.type].fg }]}>{TYPE[i.type].label}</Text></View>
                  <Text style={st.lrTitle} numberOfLines={1}>{i.title}</Text>
                  <Text style={st.ago}>{i.ago}</Text>
                  <View style={st.dotBox}><PopWhen show={i.unread} style={st.dot} /></View>
                </Pressable>
              ))}
              {rows.length > 3 && (
                <Pressable style={st.more} onPress={() => onOpenStock(s.stock_code)}><Text style={st.moreText}>{rows.length - 3}건 더 보기</Text></Pressable>
              )}
            </Appear>
          );
        })}
      </View>
      </SkeletonSwap>
      <Text style={st.end}>최근 30일 업데이트를 모두 확인했어요</Text>
      <Text style={st.disclaimer}>투자 권유가 아닌 참고 정보예요 · AI는 틀릴 수 있어 원문을 꼭 확인해 주세요</Text>
    </ScrollView>
  );
}

function ChipBody({ label, on, badge, count }: { label: string; on: boolean; badge?: number; count?: number }) {
  return (
    <>
      <Text style={[st.chipText, on && st.chipTextOn]}>{label}</Text>
      {count !== undefined && <Text style={[st.chipCount, on && st.chipCountOn]}>{count}</Text>}
      <PopWhen show={!!badge} replay={badge} style={st.chipBadge}><Text style={st.chipBadgeText}>{badge}</Text></PopWhen>
    </>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.appBg },
  flex: { flex: 1, minWidth: 0 },
  body: { paddingBottom: 40 },
  sub: { fontSize: 14, color: C.sub, paddingHorizontal: PAD, marginTop: 4 },
  unread: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', backgroundColor: C.accentSoft, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6, marginHorizontal: PAD, marginTop: 10 },
  unreadDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: C.red },
  unreadText: { fontSize: 13.5, fontWeight: '700', color: C.accentDeep },
  unreadNum: { fontWeight: '800', color: C.accentDeep },
  paused: { marginHorizontal: PAD, marginTop: 12, borderRadius: 14, padding: 14, backgroundColor: C.warnBg },
  pausedTitle: { fontSize: 14.5, fontWeight: '800', color: C.warnText },
  pausedText: { fontSize: 13, color: C.warnText, marginTop: 4 },
  chipRow: { paddingHorizontal: PAD, gap: 6, paddingTop: 6 },
  chip: { height: 36, borderRadius: 18, paddingHorizontal: 14, gap: 5, borderWidth: 1, borderColor: C.chipLine, marginVertical: 4 },
  chipOnDark: { borderColor: C.dark },
  pillDark: { backgroundColor: C.dark, borderRadius: 18 },
  chipText: { fontSize: 14, fontWeight: '700', color: C.sub },
  chipTextOn: { color: C.white },
  chipCount: { fontSize: 13, color: C.muted },
  chipCountOn: { color: C.white },
  chipBadge: { minWidth: 18, height: 18, borderRadius: 9, backgroundColor: C.red, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4 },
  chipBadgeText: { fontSize: 11, fontWeight: '700', color: C.white },
  cards: { paddingHorizontal: PAD, gap: GAP, marginTop: 8 },
  card: { backgroundColor: C.card, borderRadius: R.card, paddingHorizontal: 16, paddingVertical: 8 },
  hd: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 60 },
  logo: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  logoText: { fontSize: 16, fontWeight: '800' },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  name: { fontSize: 16.5, fontWeight: '800', color: C.text, flexShrink: 1 },
  own: { backgroundColor: C.tagBg, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1 },
  ownText: { fontSize: 11.5, fontWeight: '700', color: C.accentDeep },
  code: { fontSize: 12, color: C.muted, marginTop: 1 },
  lr: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 48, borderTopWidth: 1, borderTopColor: C.line },
  tag: { borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  tagText: { fontSize: 11.5, fontWeight: '800' },
  lrTitle: { flex: 1, fontSize: 14.5, color: C.text },
  ago: { fontSize: 12, color: C.muted },
  dotBox: { width: 7, height: 7 },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: C.accent },
  skCard: { height: 200, borderRadius: R.card },
  none: { fontSize: 13, color: C.muted, textAlign: 'center', paddingVertical: 14, borderTopWidth: 1, borderTopColor: C.line },
  more: { minHeight: 44, alignItems: 'center', justifyContent: 'center', borderTopWidth: 1, borderTopColor: C.line },
  moreText: { fontSize: 13.5, fontWeight: '700', color: C.accentDeep },
  end: { textAlign: 'center', fontSize: 13, color: C.muted, marginTop: 40 },
  disclaimer: { textAlign: 'center', fontSize: 12, lineHeight: 19, color: C.muted, marginTop: 10, paddingHorizontal: 30 },
});
