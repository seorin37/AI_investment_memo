import React, { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { FadeIn } from '@/ui/motion/Reveal';
import { Sheet } from '@/ui/shared/Sheet';
import { fpx } from '@/ui/theme';
import type { CustomItem, CustomWidget, MarketEvent, WebHomeProps } from '../Home.types';
import { ago, hm, mmdd } from '../homeFormat';
import { GridBg, MoveHandle } from './homeDom.web';
import { MarketCardBase } from './HomeWidgets';

type Hover = { pressed: boolean; hovered?: boolean };
type Box = { x: number; y: number; w: number; h: number };

/* 원본 custom.tsx: 24 격자 · 보드 안쪽 폭 626 · 위젯 기본 크기 */
const G = 24;
const BW = 626;
const DEF: Record<CustomWidget, { t: string; w: number; h: number }> = {
  market: { t: '시장 지수·환율', w: BW, h: 277 },
  updates: { t: '종목별 업데이트', w: 248, h: 512 },
  schedule: { t: '주요 증시 일정', w: 512, h: 512 },
  news: { t: '뉴스', w: 254, h: 572 },
};
const hit = (a: Box, b: Box) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
function findSlot(items: Box[], w: number, h: number): Box {
  const ok = (r: Box) => !items.some((i) => hit(r, { x: i.x - G + 1, y: i.y - G + 1, w: i.w + G * 2 - 2, h: i.h + G * 2 - 2 }));
  for (let y = 0; y < 4000; y += G) for (let x = 0; x + w <= BW; x += G) if (ok({ x, y, w, h })) return { x, y, w, h };
  return { x: 0, y: 0, w, h };
}
/** 위젯 추가 칸 자리: Figma처럼 240 (공간이 모자라면 168까지) */
function addSlot(items: Box[]) {
  if (!items.length) return { x: 0, y: 0, w: 280, h: 280 };
  for (const w of [240, 216, 192, 168]) {
    const r = findSlot(items, w, 240);
    if (r.y + 240 <= 572) return r;
  }
  return findSlot(items, 240, 240);
}

/**
 * 웹 홈 직접 사용자화 (원본 web/src/screens/custom.tsx · 2.2 · 2.4.1~2.4.4 위젯)
 * 회색 보드(최대 674 · 24px 격자) 위에 위젯을 놓고 상단 손잡이로 옮김 — 놓으면 격자에 맞추고, 겹치면 빈 자리로.
 * 크기 조절(모서리 손잡이)은 ② 결정으로 뺌. 위젯: 시장 지수·환율 · 종목별 업데이트 · 주요 증시 일정(달력 · mock) · 뉴스.
 */
export function CustomHome(p: WebHomeProps) {
  const board = p.board;
  const ref = useRef(board);
  useEffect(() => {
    ref.current = board;
  }, [board]);
  const set = (f: (b: CustomItem[]) => CustomItem[]) => {
    const n = f(ref.current);
    ref.current = n;
    p.onChangeBoard(n);
  };
  const [sel, setSel] = useState<CustomWidget | null>(board[board.length - 1]?.id ?? null);
  const [pick, setPick] = useState(false);
  const add = addSlot(board);
  const bottom = Math.max(572, add.y + add.h, ...board.map((b) => b.y + b.h));
  const addWidget = (id: CustomWidget) => {
    const d = DEF[id];
    const s = findSlot(board, d.w, d.h);
    set((b) => [...b, { id, ...s }]);
    setSel(id);
    setPick(false);
  };
  /* 옮기기: 끄는 동안 자유롭게 → 놓으면 24 격자에 맞추고, 겹치면 빈 자리 */
  const move = (it: CustomItem, dx: number, dy: number) => set((b) => b.map((x) => (x.id === it.id ? { ...it, x: Math.max(0, Math.min(BW - it.w, it.x + dx)), y: Math.max(0, it.y + dy) } : x)));
  const drop = (id: CustomWidget) => {
    set((b) => {
      const me = b.find((x) => x.id === id);
      if (!me) return b;
      const snap = (v: number) => Math.round(v / G) * G;
      let n: CustomItem = { ...me, x: Math.min(BW - me.w, snap(me.x)), y: snap(me.y) };
      const others = b.filter((x) => x.id !== id);
      if (others.some((x) => hit(n, x))) n = { ...n, ...findSlot(others, n.w, n.h) };
      return b.map((x) => (x.id === id ? n : x));
    });
  };
  return (
    <ScrollView style={st.flex} contentContainerStyle={st.page}>
      <View style={st.head}>
        <View style={st.headL}>
          <Text style={st.title}>홈 직접 사용자화</Text>
          <Text style={st.sub}>필요한 위젯을 추가해 나만의 투자 홈을 만들어 보세요.</Text>
        </View>
        <Pressable onPress={p.onGoStart} accessibilityRole="button" style={({ hovered }: Hover) => [st.startB, hovered && { backgroundColor: '#F9F9F9' }]}>
          <Text style={st.startBT}>시작 화면으로</Text>
        </Pressable>
      </View>
      {p.firstStart ? <View style={{ width: 860, maxWidth: '100%', marginBottom: 20 }}>{p.firstStart}</View> : null}
      <View style={[st.board, { height: bottom + 48 }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={() => setSel(null)} accessibilityLabel="위젯 고르기 풀기" />
        {board.length > 0 ? <GridBg /> : null}
        <Pressable onPress={() => setPick(true)} accessibilityRole="button" style={({ hovered }: Hover) => [st.addSlot, { left: 24 + add.x, top: 24 + add.y, width: add.w, height: add.h, borderColor: hovered ? '#D7DCE6' : '#E8ECF3' }]}>
          <Text style={st.addPlus}>＋</Text>
          <Text style={st.addB}>위젯 추가</Text>
          <Text style={st.addT}>클릭해서 위젯을 골라보세요</Text>
        </Pressable>
        {board.map((it) => {
          const on = sel === it.id;
          return (
            <FadeIn key={it.id} style={[st.frame, { left: 24 + it.x, top: 24 + it.y, width: it.w, height: it.h, borderColor: on ? '#477BFF' : 'transparent', zIndex: on ? 10 : 1 }]}>
              <Pressable onPressIn={() => setSel(it.id)} style={st.flex}>
                <MoveHandle
                  onDown={() => setSel(it.id)}
                  onMove={(dx, dy) => move(it, dx, dy)}
                  onUp={() => drop(it.id)}
                >
                  <Text style={st.hdT}>⠿ {'  '}끌어서 이동</Text>
                  {on ? (
                    <Pressable
                      onPress={() => {
                        set((b) => b.filter((x) => x.id !== it.id));
                        setSel(null);
                      }}
                    >
                      {({ hovered }: Hover) => <Text style={[st.hdT, hovered && { color: '#15171A' }]}>삭제</Text>}
                    </Pressable>
                  ) : null}
                </MoveHandle>
                <View style={st.body}>
                  <WidgetBody id={it.id} p={p} />
                </View>
              </Pressable>
            </FadeIn>
          );
        })}
      </View>
      <Text style={st.foot}>{board.length ? '상단 손잡이로 이동 · 24px 격자에 맞춰 배치' : '추가한 위젯은 언제든 바꾸거나 삭제할 수 있어요.'}</Text>
      <WidgetPicker open={pick} onClose={() => setPick(false)} have={board.map((b) => b.id)} onAdd={addWidget} />
    </ScrollView>
  );
}

function WidgetBody({ id, p }: { id: CustomWidget; p: WebHomeProps }) {
  if (id === 'market')
    return (
      <View style={st.mk}>
        {(p.market ?? []).map((q) => (
          <MarketCardBase key={q.key} q={q} h={245} usdLabel="미국 USD" onMore={() => {}} />
        ))}
      </View>
    );
  if (id === 'updates') return <UpdatesW p={p} />;
  if (id === 'schedule') return <CalendarW events={p.schedule} now={p.now} />;
  return <NewsW p={p} />;
}

/* 원본 CARD: 라운드 20 · 흰 바탕 · 그림자 0 5 22 rgba(20,26,46,.04) */
function UpdatesW({ p }: { p: WebHomeProps }) {
  const [hov, setHov] = useState(p.updates[0]?.stock_code ?? '');
  return (
    <View style={[st.card, { gap: 12, padding: 24 }]}>
      <Text style={st.cTitle}>업데이트</Text>
      <Text style={st.cSub}>내 종목의 새로운 소식</Text>
      <ScrollView style={st.flex} contentContainerStyle={{ gap: 12 }} showsVerticalScrollIndicator={false}>
        {!p.updates.length ? <Text style={[st.cSub, { paddingVertical: 16 }]}>종목을 추가하면 여기에 모여요</Text> : null}
        {p.updates.map((u) => (
          <Pressable key={u.stock_code} onHoverIn={() => setHov(u.stock_code)} onPress={() => p.onOpenStockUpdates(u.stock_code)} style={[st.uRow, hov === u.stock_code ? { borderColor: '#111111', backgroundColor: '#F7F7F7' } : null]}>
            <View style={st.uTop}>
              <Text style={st.uN}>{u.name}</Text>
              {u.new_count ? (
                <View style={st.uBadge}>
                  <Text style={st.uBadgeT}>{u.new_count}</Text>
                </View>
              ) : null}
            </View>
            <Text style={st.cSub}>
              {u.status === 'holding' ? '보유' : '관심'} · {u.new_count ? `새 업데이트 ${u.new_count}건` : '모두 확인했어요'}
            </Text>
          </Pressable>
        ))}
      </ScrollView>
      <Pressable onPress={p.onOpenUpdates}>
        <Text style={st.uAll}>전체 업데이트 보기 {'  '}→</Text>
      </Pressable>
    </View>
  );
}

/** 주요 증시 일정 달력 (원본 CalendarW · 실제 데이터 연결 안 함 — mock 일정) */
function CalendarW({ events, now }: { events: MarketEvent[]; now: string }) {
  const ty = Number(now.slice(0, 4));
  const tm = Number(now.slice(5, 7)) - 1;
  const td = Number(now.slice(8, 10));
  const [ym, setYm] = useState<[number, number]>([ty, tm]);
  const first = new Date(ym[0], ym[1], 1);
  const n = new Date(ym[0], ym[1] + 1, 0).getDate();
  const days: (number | null)[] = [...Array.from({ length: first.getDay() }, () => null), ...Array.from({ length: n }, (_, i) => i + 1)];
  const weeks = Array.from({ length: Math.ceil(days.length / 7) }, (_, i) => days.slice(i * 7, i * 7 + 7));
  const evs = events.filter((e) => +e.date.slice(0, 4) === ym[0] && +e.date.slice(5, 7) === ym[1] + 1);
  const ev = new Set(evs.map((e) => +e.date.slice(8, 10)));
  const today = ty === ym[0] && tm === ym[1] ? td : -1;
  const mv = (d: number) =>
    setYm(([y, m]) => {
      const t = new Date(y, m + d, 1);
      return [t.getFullYear(), t.getMonth()];
    });
  return (
    <View style={[st.card, { gap: 12, padding: 24 }]}>
      <Text style={st.cTitle}>주요 증시 일정</Text>
      <View style={st.calHead}>
        <Text style={st.calYm}>
          {ym[0]}년 {ym[1] + 1}월
        </Text>
        <View style={st.calNav}>
          <Pressable onPress={() => mv(-1)} accessibilityLabel="이전 달" style={{ paddingHorizontal: 4 }}>
            {({ hovered }: Hover) => <Text style={[st.cSub, hovered && { color: '#15171A' }]}>‹</Text>}
          </Pressable>
          <Pressable onPress={() => setYm([ty, tm])}>{({ hovered }: Hover) => <Text style={[st.cSub, hovered && { color: '#15171A' }]}>오늘</Text>}</Pressable>
          <Pressable onPress={() => mv(1)} accessibilityLabel="다음 달" style={{ paddingHorizontal: 4 }}>
            {({ hovered }: Hover) => <Text style={[st.cSub, hovered && { color: '#15171A' }]}>›</Text>}
          </Pressable>
        </View>
      </View>
      <View style={st.wkRow}>
        {['일', '월', '화', '수', '목', '금', '토'].map((d) => (
          <Text key={d} style={[st.cSub, st.wk]}>
            {d}
          </Text>
        ))}
      </View>
      <View style={{ gap: 8, width: '100%' }}>
        {weeks.map((wk, i) => (
          <View key={i} style={st.week}>
            {Array.from({ length: 7 }, (_, j) => wk[j] ?? null).map((d, j) => (
              <View key={j} style={[st.day, d === today ? { backgroundColor: '#111111' } : d && ev.has(d) ? { backgroundColor: '#F3F4F6' } : null]}>
                {d ? <Text style={[st.dayT, { color: d === today ? '#FFFFFF' : '#15171A' }]}>{d}</Text> : null}
                {d && ev.has(d) ? <Text style={[st.dot, { color: d === today ? '#FFFFFF' : '#E5484D' }]}>•</Text> : null}
              </View>
            ))}
          </View>
        ))}
      </View>
      <ScrollView style={st.flex} contentContainerStyle={{ gap: 8 }} showsVerticalScrollIndicator={false}>
        {evs.length === 0 ? <Text style={st.cSub}>이 달에 정리된 일정이 없어요</Text> : null}
        {evs.map((e) => (
          <View key={e.date + e.title} style={st.evRow}>
            <Text style={st.evT} numberOfLines={1}>
              ● {'  '}
              {mmdd(e.date)} {'  '}
              {e.title}
            </Text>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

function NewsW({ p }: { p: WebHomeProps }) {
  const head = p.news[0];
  const list = p.news.slice(1, 8);
  const day = p.news_day || (p.days[p.days.length - 1] ?? '');
  return (
    <View style={st.nw}>
      <View style={st.between}>
        <Text style={st.nwT}>뉴스</Text>
        <Text style={st.nwC}>
          {mmdd(day)} · {p.news_day_total}건
        </Text>
      </View>
      {head ? (
        <Pressable onPress={() => p.onOpenNews(head)} style={st.nwHead}>
          <View style={st.between}>
            <View style={st.nwSrc}>
              <Text style={st.nwSrcT}>{head.src}</Text>
            </View>
            <Text style={st.nwSrcT}>
              {hm(head.at)} · {ago(head.at, p.now)}
            </Text>
          </View>
          <Text style={st.nwHT}>{head.title}</Text>
          <Text style={st.nwO}>원문 읽기 ↗</Text>
        </Pressable>
      ) : null}
      <ScrollView style={st.flex} showsVerticalScrollIndicator={false}>
        {list.map((n) => (
          <Pressable key={n.id} onPress={() => p.onOpenNews(n)} style={st.nwRow}>
            <Text style={st.nwTm}>{n.at.slice(0, 10) === day ? hm(n.at) : mmdd(n.at)}</Text>
            <View style={{ flex: 1, minWidth: 0, gap: 1.55 }}>
              <Text style={st.nwRT}>{n.title}</Text>
              <Text style={st.nwC}>{n.src}</Text>
            </View>
            <Text style={st.nwAr}>↗</Text>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}

/** 위젯 고르기 (원본 WidgetPicker: 4. 종목 추가 팝업 모양) */
function WidgetPicker({ open, onClose, have, onAdd }: { open: boolean; onClose: () => void; have: CustomWidget[]; onAdd: (id: CustomWidget) => void }) {
  const [sel, setSel] = useState<CustomWidget | null>(null);
  const list = Object.entries(DEF) as [CustomWidget, (typeof DEF)[CustomWidget]][];
  return (
    <Sheet open={open} onClose={onClose} width={680} label="위젯 추가">
      <View style={st.pk}>
        <View style={st.between}>
          <Text style={st.pkT}>위젯 추가</Text>
          <Pressable onPress={onClose}>
            <Text style={st.pkClose}>닫기</Text>
          </Pressable>
        </View>
        <View>
          {list.map(([id, d]) => {
            const done = have.includes(id);
            const on = sel === id && !done;
            return (
              <Pressable key={id} disabled={done} onPress={() => setSel(id)} style={({ hovered }: Hover) => [st.pkRow, on ? { backgroundColor: '#EFEFEF' } : !done && hovered ? { backgroundColor: '#F9F9F9' } : null]}>
                <Text style={[st.pkN, { fontWeight: on ? '700' : '500', color: done ? '#8F8F8F' : '#191F28' }]}>{d.t}</Text>
                <Text style={st.pkS}>{done ? '추가됨' : d.w === BW ? '가로 전체' : `${d.w}×${d.h}`}</Text>
              </Pressable>
            );
          })}
        </View>
        <View style={st.pkBtns}>
          <Pressable onPress={onClose} style={[st.pkBtn, { backgroundColor: '#F7F8FA' }]}>
            <Text style={[st.pkBtnT, { color: '#8F8F8F' }]}>취소</Text>
          </Pressable>
          <Pressable
            disabled={!sel || have.includes(sel)}
            onPress={() => {
              if (sel) onAdd(sel);
              setSel(null);
            }}
            style={[st.pkBtn, { backgroundColor: !sel || have.includes(sel) ? '#E8ECF3' : '#000000' }]}
          >
            <Text style={[st.pkBtnT, { color: !sel || have.includes(sel) ? '#8F8F8F' : '#FFFFFF' }]}>추가</Text>
          </Pressable>
        </View>
      </View>
    </Sheet>
  );
}

const st = StyleSheet.create({
  flex: { flex: 1 },
  between: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', width: '100%' },
  page: { minHeight: '100%', width: '100%', gap: 32, padding: 40 },
  head: { height: 80, width: '100%', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#FFFFFF' },
  headL: { height: 80, width: 530, gap: 6, backgroundColor: '#FFFFFF' },
  title: { ...fpx(30, 40), fontWeight: '700', color: '#15171A' },
  sub: { ...fpx(15, 23), color: '#747D8D' },
  startB: { height: 44, width: 144, alignItems: 'center', justifyContent: 'center', borderRadius: 12, borderWidth: 1, borderColor: '#E8ECF3', backgroundColor: '#FFFFFF' },
  startBT: { ...fpx(14, 21), fontWeight: '500', color: '#15171A' },
  board: { position: 'relative', width: '100%', maxWidth: 674, overflow: 'hidden', borderRadius: 24, backgroundColor: '#F5F6F8' },
  addSlot: { position: 'absolute', alignItems: 'center', justifyContent: 'center', gap: 12, borderRadius: 20, borderWidth: 2, borderStyle: 'dashed', backgroundColor: '#FFFFFF' },
  addPlus: { ...fpx(36, 54), color: '#477BFF' },
  addB: { ...fpx(20, 29), fontWeight: '700', color: '#15171A' },
  addT: { ...fpx(13, 20), color: '#747D8D' },
  frame: { position: 'absolute', borderRadius: 16, borderWidth: 1.5, backgroundColor: '#FFFFFF' },
  hdT: { ...fpx(13, 20), color: '#747D8D' },
  body: { flex: 1, minHeight: 0, width: '100%', overflow: 'hidden' },
  foot: { ...fpx(13, 20), color: '#747D8D' },
  mk: { height: 245, width: '100%', flexDirection: 'row', alignItems: 'flex-start', gap: 16 },
  card: { flex: 1, width: '100%', overflow: 'hidden', borderRadius: 20, backgroundColor: '#FFFFFF', shadowColor: '#141A2E', shadowOpacity: 0.04, shadowRadius: 22, shadowOffset: { width: 0, height: 5 }, elevation: 2 },
  cTitle: { width: '100%', ...fpx(20, 29), fontWeight: '500', letterSpacing: -0.2, color: '#15171A' },
  cSub: { ...fpx(13, 20), color: '#747D8D' },
  uRow: { height: 78, width: '100%', gap: 8, borderRadius: 12, borderWidth: 1, borderColor: '#E8ECF3', backgroundColor: '#FFFFFF', padding: 12 },
  uTop: { height: 26, width: '100%', flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
  uN: { ...fpx(14, 21), fontWeight: '500', letterSpacing: -0.14, color: '#15171A' },
  uBadge: { height: 26, minWidth: 26, borderRadius: 13, backgroundColor: '#E45D6A', paddingHorizontal: 4, alignItems: 'center', justifyContent: 'center' },
  uBadgeT: { ...fpx(14, 21), fontWeight: '500', color: '#FFFFFF' },
  uAll: { ...fpx(13, 20), fontWeight: '500', letterSpacing: -0.13, color: '#111111' },
  calHead: { height: 24, width: '100%', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  calYm: { ...fpx(17, 26), fontWeight: '500', letterSpacing: -0.17, color: '#15171A' },
  calNav: { width: 96, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  wkRow: { height: 20, width: '100%', flexDirection: 'row', gap: 4 },
  wk: { flex: 1, minWidth: 0, textAlign: 'center' },
  week: { height: 36, width: '100%', flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', paddingHorizontal: 13.43 },
  day: { width: 36, height: 36, alignItems: 'center', borderRadius: 12, paddingVertical: 4 },
  dayT: { width: 26, textAlign: 'center', ...fpx(13, 20) },
  dot: { position: 'absolute', left: 13, top: 18, width: 10, textAlign: 'center', ...fpx(26, 35) },
  evRow: { height: 32, width: '100%', flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 12, backgroundColor: '#F3F4F6', paddingHorizontal: 12 },
  evT: { ...fpx(13, 20), fontWeight: '500', letterSpacing: -0.13, color: '#15171A' },
  nw: { height: '100%', width: '100%', gap: 9.31, overflow: 'hidden', borderRadius: 15.52, backgroundColor: '#FFFFFF', padding: 18.62 },
  nwT: { ...fpx(14, 21), fontWeight: '500', color: '#15171A' },
  nwC: { ...fpx(11, 16), color: '#747D8D' },
  nwHead: { width: '100%', gap: 6.21, borderRadius: 9.31, backgroundColor: '#F3F4F6', padding: 10.86 },
  nwSrc: { borderRadius: 7.76, backgroundColor: '#FFFFFF', paddingHorizontal: 6.21, paddingVertical: 1.55 },
  nwSrcT: { ...fpx(13, 20), fontWeight: '500', color: '#575B63' },
  nwHT: { width: '100%', ...fpx(14, 21), fontWeight: '700', color: '#15171A' },
  nwO: { ...fpx(13, 20), fontWeight: '500', color: '#15171A', textDecorationLine: 'underline' },
  nwRow: { width: '100%', flexDirection: 'row', alignItems: 'flex-start', gap: 7.76, borderTopWidth: 0.78, borderTopColor: '#EEF0F3', paddingHorizontal: 1.55, paddingVertical: 7.76 },
  nwTm: { width: 34, flexShrink: 0, ...fpx(13, 20), fontWeight: '500', color: '#747D8D' },
  nwRT: { width: '100%', ...fpx(13, 20), fontWeight: '500', color: '#15171A' },
  nwAr: { ...fpx(13, 20), fontWeight: '500', color: '#9AA3B2' },
  pk: { width: 680, maxWidth: '100%', gap: 16, borderRadius: 20, backgroundColor: '#FFFFFF', padding: 28 },
  pkT: { ...fpx(20, 29), fontWeight: '700', color: '#191F28' },
  pkClose: { ...fpx(13, 20), fontWeight: '500', color: '#6B7684' },
  pkRow: { height: 41, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderRadius: 10, paddingHorizontal: 14 },
  pkN: { ...fpx(14, 20) },
  pkS: { ...fpx(13, 20), color: '#8F8F8F' },
  pkBtns: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8 },
  pkBtn: { height: 41, width: 82, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  pkBtnT: { ...fpx(14, 20), fontWeight: '700' },
});
