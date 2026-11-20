import React, { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, View, type TextStyle } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text, TextInput } from '@/components/ui/AppText';
import { Dots } from '@/ui/icons/BoardGlyphs';
import { FixedFrame } from '@/ui/layout/web/FixedFrame';
import { FadeIn } from '@/ui/motion/Reveal';
import { useMotionK } from '@/ui/motion/useMotion';
import { useContextMenuWeb, useEscapeWeb } from '@/ui/screens/board/web/boardDom.web';
import { Pick } from '@/ui/shared/MemoCard';
import { ContextMenu, type MenuItem } from '@/ui/shared/ContextMenu';
import { WebSelectBar } from '@/ui/shared/SelectBar';
import { WebSnackbar } from '@/ui/shared/Snackbar';
import { curve, fpx } from '@/ui/theme';
import type { JournalEntry, JournalProps } from '../Journal.types';
import { firstSentence, groupJournal, searchJournal, splitHit } from '../journalParts';

type Hover = { pressed: boolean; hovered?: boolean };
type Snack = { key: number; msg: string; undo?: () => void; check?: boolean };
type Menu = { items: MenuItem[]; at: { x: number; y: number } };
const data = (o: Record<string, string>) => ({ dataSet: o }) as object;
let seq = 0;
const NOT_YET = '아직 연결되지 않았어요 · 데이터는 그대로예요';

export interface WebJournalProps extends JournalProps {
  /** 처음 고른 기록 (검색 등에서 ?id= 로 들어올 때) */
  initialId?: string;
}

/**
 * 웹 투자 기록 (원본 web/src/screens/journal.tsx · Figma 2.5 · 11.16 앱 통일)
 * 860 틀 · 높이 채움 · 위 32 · 제목 줄(26/35 · 'N개의 기록 · …' 14/21) 오른쪽 [⋯ 44] [검색 280×44] [새 기록 44]
 * 아래 흰 상자 (라운드 20 · 테두리) = 왼쪽 목록 280 (안쪽 12 · 줄 사이 4) + 오른쪽 기록
 * 목록: 묶음 머리 32 (13/20 bold #8B95A1 · 고정됨은 접기) · 줄 (라운드 12 · 위아래 12 좌우 16 · 제목 17/26 · 날짜 15/23 + 첫 문장)
 * 줄 우클릭·⋯ = 기록 메뉴 · 고르기 = 아래 검정 막대. 오른쪽 기록 쓰기·서식·도구 막대는 7b.
 */
export function WebJournal(p: WebJournalProps) {
  const k = useMotionK();
  const L = p.entries;
  const [cur, setCur] = useState<string | null>(p.initialId ?? L[0]?.id ?? null);
  const [q, setQ] = useState('');
  const [grouped, setGrouped] = useState(true);
  const [pinOpen, setPinOpen] = useState(true);
  const [pick, setPick] = useState<Set<string> | null>(null);
  const [menu, setMenu] = useState<Menu | null>(null);
  const [snack, setSnack] = useState<Snack | null>(null);
  const box = useRef<React.ComponentRef<typeof View>>(null);

  useEffect(() => {
    if (!snack) return;
    const t = setTimeout(() => setSnack((s) => (s && s.key === snack.key ? null : s)), (snack.undo ? 5000 : 2400) * k);
    return () => clearTimeout(t);
  }, [snack, k]);
  /* 지금 기록이 빠지면 첫 기록으로 (원본 useEffect) */
  const curJ = L.find((j) => j.id === cur) ?? L[0] ?? null;
  const list = searchJournal(L, q);
  const { pins, groups } = groupJournal(list, grouped, '');
  const sections: { key: string; items: JournalEntry[] }[] = [...(pins.length && grouped ? [{ key: '고정됨', items: pins }] : []), ...(grouped ? groups : [{ key: '', items: [...pins, ...groups.flatMap((g) => g.items)] }])].filter((s) => s.items.length);

  const say = (msg: string, extra?: Partial<Snack>) => setSnack({ key: ++seq, msg, ...extra });
  /* 새 기록 쓰기는 7b 에서 연결 */
  const newJ = () => {
    p.onNew();
    say(NOT_YET);
  };
  const trashJ = (ls: JournalEntry[]) => {
    const before = L;
    p.onTrash(ls.map((j) => j.id));
    say(ls.length > 1 ? `기록 ${ls.length}개를 휴지통으로 옮겼어요` : '기록 1개를 휴지통으로 옮겼어요', { undo: () => (p.onRestore(before), setSnack(null)) });
  };
  const pinJ = (ls: JournalEntry[], on: boolean) => {
    p.onPin(
      ls.map((j) => j.id),
      on,
    );
    say(on ? (ls.length > 1 ? `${ls.length}개를 고정했어요` : '고정했어요') : '고정을 풀었어요', { check: true });
  };
  const copyJ = (j: JournalEntry, msg = '내용을 복사했어요') => {
    try {
      void (globalThis as { navigator?: { clipboard?: { writeText: (t: string) => Promise<void> } } }).navigator?.clipboard?.writeText(j.blocks.map((b) => b.text).join('\n')).catch(() => {});
    } catch {
      /* 무시 */
    }
    say(msg, { check: true });
  };
  const rowMenu = (j: JournalEntry): MenuItem[] => [
    { label: j.pinned ? '고정 풀기' : '맨 위에 고정', icon: 'pin', run: () => pinJ([j], !j.pinned) },
    { label: '공유', icon: 'share', run: () => copyJ(j, '공유할 내용을 복사했어요') },
    { label: '내용 복사', icon: 'copy', run: () => copyJ(j) },
    { label: '기록 선택하기', icon: 'select', run: () => setPick(new Set([j.id])) },
    '-',
    { label: '휴지통으로 이동', icon: 'trash', danger: true, run: () => trashJ([j]) },
  ];
  useContextMenuWeb(box, true, (id, at) => {
    const j = L.find((x) => x.id === id);
    if (j && !pick) setMenu({ items: rowMenu(j), at });
  });
  useEscapeWeb(!!pick && !menu, () => setPick(null));
  const togglePick = (id: string) =>
    setPick((s) => {
      const n = new Set(s ?? []);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  const picked = L.filter((j) => pick?.has(j.id));
  const at = (e: { nativeEvent: unknown }, dx = 0) => {
    const r = ((e.nativeEvent as { target?: { getBoundingClientRect?: () => DOMRect } }).target?.getBoundingClientRect?.() ?? { left: 0, right: 0, bottom: 0 }) as DOMRect;
    return { r, dx };
  };

  return (
    <View style={st.root}>
      <FixedFrame fill>
        <View style={st.page}>
          {/* 제목 줄 (원본 PageTitle) */}
          <View style={st.head}>
            <View style={st.headL}>
              <Text style={st.title}>투자 기록</Text>
              <Text style={st.sub}>{L.length}개의 기록 · AI 연결 없이 나만 보는 투자 일지예요</Text>
            </View>
            <View style={st.headR}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="보기 옵션"
                onPress={(e) => {
                  const { r } = at(e);
                  setMenu({
                    at: { x: r.right - 220, y: r.bottom + 6 },
                    items: [
                      { label: '기록 선택하기', icon: 'select', run: () => setPick(new Set()) },
                      { label: grouped ? '날짜별로 묶기 끄기' : '날짜별로 묶기', icon: 'info', run: () => setGrouped(!grouped) },
                    ],
                  });
                }}
                style={({ hovered }: Hover) => [st.circ, hovered && st.circH]}
              >
                <Dots color="#15171A" />
              </Pressable>
              <View style={st.search}>
                <Svg width={20} height={20} viewBox="0 0 16 16" fill="none">
                  <Path d="M7 11C9.20914 11 11 9.20914 11 7C11 4.79086 9.20914 3 7 3C4.79086 3 3 4.79086 3 7C3 9.20914 4.79086 11 7 11Z" stroke="#6B7078" strokeWidth={1.2} strokeLinecap="round" strokeLinejoin="round" />
                  <Path d="M13.3333 13.3333L10 10" stroke="#6B7078" strokeWidth={1.2} strokeLinecap="round" strokeLinejoin="round" />
                </Svg>
                <TextInput value={q} onChangeText={setQ} placeholder="검색" placeholderTextColor="#6B7078" accessibilityLabel="기록 검색" style={st.sin} />
              </View>
              <Pressable accessibilityRole="button" accessibilityLabel="새 기록" onPress={newJ} style={({ hovered }: Hover) => [st.circ, hovered && st.circH]}>
                <Svg width={22} height={22} viewBox="0 0 18 18" fill="none">
                  <Path d="M3 15.0002H6L13.875 7.12523C14.2728 6.7274 14.4963 6.18784 14.4963 5.62523C14.4963 5.06262 14.2728 4.52305 13.875 4.12523C13.4772 3.7274 12.9376 3.50391 12.375 3.50391C11.8124 3.50391 11.2728 3.7274 10.875 4.12523L3 12.0002V15.0002Z" stroke="#1C1C1C" strokeWidth={1.35} strokeLinecap="round" strokeLinejoin="round" />
                  <Path d="M10.125 4.875L13.125 7.875" stroke="#1C1C1C" strokeWidth={1.35} strokeLinecap="round" strokeLinejoin="round" />
                </Svg>
              </Pressable>
            </View>
          </View>

          <View style={st.boxO}>
            {/* 왼쪽 목록 280 */}
            <ScrollView style={st.list} contentContainerStyle={st.listC} showsVerticalScrollIndicator={false}>
              <View ref={box} style={{ gap: 4 }}>
                {!list.length && q.trim() ? (
                  <View style={st.none}>
                    <Text style={st.noneT}>‘{q}’가 들어간 기록이 없어요</Text>
                    <Text style={st.noneP}>다른 말로 찾아보세요</Text>
                  </View>
                ) : null}
                {sections.map((g) => (
                  <View key={g.key || 'all'} style={{ gap: 4 }}>
                    {g.key ? (
                      <Pressable disabled={g.key !== '고정됨'} onPress={() => setPinOpen(!pinOpen)} style={st.gh}>
                        <Text style={st.ghT}>{g.key}</Text>
                        {g.key === '고정됨' ? <Chev open={pinOpen} /> : null}
                      </Pressable>
                    ) : null}
                    {g.key !== '고정됨' || pinOpen ? (
                      <View style={{ gap: 4 }}>
                        {g.items.map((j) => {
                          const on = j.id === curJ?.id;
                          return (
                            <WRow
                              key={j.id}
                              j={j}
                              q={q}
                              on={on && !pick}
                              pick={pick ? pick.has(j.id) : null}
                              onPress={() => (pick ? togglePick(j.id) : (setCur(j.id), p.onOpen(j.id)))}
                              onMenu={(e) => {
                                const { r } = at(e);
                                setMenu({ items: rowMenu(j), at: { x: r.left, y: r.bottom + 4 } });
                              }}
                            />
                          );
                        })}
                      </View>
                    ) : null}
                  </View>
                ))}
              </View>
            </ScrollView>

            {/* 오른쪽: 기록 (쓰기·서식은 7b) / 빈 상태 */}
            {!curJ ? (
              <FadeIn style={st.empty}>
                <View style={st.eIll}>
                  <View style={st.eBar1} />
                  <View style={st.eBar2} />
                </View>
                <Text style={st.eT}>아직 기록이 없어요</Text>
                <Text style={st.eP}>{'오늘 본 것, 다음에 확인할 것을\n나만의 투자 기록으로 남겨 보세요'}</Text>
                <Pressable onPress={newJ} accessibilityRole="button" style={({ hovered }: Hover) => [st.eBtn, hovered && { backgroundColor: '#2A2A2A' }]}>
                  <Text style={st.eBtnT}>첫 기록 쓰기</Text>
                </Pressable>
              </FadeIn>
            ) : (
              <View style={st.ed}>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="이 기록 메뉴"
                  onPress={(e) => {
                    const { r } = at(e);
                    setMenu({
                      at: { x: r.right - 220, y: r.bottom + 6 },
                      items: [
                        { label: '공유', icon: 'share', run: () => copyJ(curJ, '공유할 내용을 복사했어요') },
                        { label: '내용 복사', icon: 'copy', run: () => copyJ(curJ) },
                        { label: curJ.pinned ? '고정 풀기' : '맨 위에 고정', icon: 'pin', run: () => pinJ([curJ], !curJ.pinned) },
                        '-',
                        { label: '휴지통으로 이동', icon: 'trash', danger: true, run: () => trashJ([curJ]) },
                      ],
                    });
                  }}
                  style={({ hovered }: Hover) => [st.curMenu, hovered && { backgroundColor: '#F3F4F6' }]}
                >
                  <Dots color="#575B63" />
                </Pressable>
                <FadeIn key={curJ.id} style={st.flex}>
                  <ScrollView style={st.flex} contentContainerStyle={st.edC}>
                    <Text style={st.full}>{curJ.full}</Text>
                    <View style={{ height: 18 }} />
                    <Text style={st.edTitle}>{curJ.title || '제목 없음'}</Text>
                    <View style={{ height: 12 }} />
                    {curJ.blocks.slice(1).map((b, i) =>
                      b.check !== undefined ? (
                        <View key={i} style={st.todo}>
                          <View style={[st.tdBox, b.check && st.tdOn]}>
                            {b.check ? (
                              <Svg width={10} height={10} viewBox="0 0 10 10" fill="none">
                                <Path d="M2 5.2 4.1 7.2 8 3" stroke="#FFFFFF" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
                              </Svg>
                            ) : null}
                          </View>
                          <Text style={[st.body, b.check ? st.tdDone : { color: '#1C1C1C' }]}>{b.text}</Text>
                        </View>
                      ) : (
                        <Text key={i} style={[b.s === 'head' ? st.edHead : b.s === 'sub' ? st.edSub : st.body, st.para]}>
                          {b.text.replace(/\n/g, ' ')}
                        </Text>
                      ),
                    )}
                  </ScrollView>
                </FadeIn>
              </View>
            )}
          </View>
        </View>
      </FixedFrame>
      {pick ? (
        <View style={st.selBar} pointerEvents="box-none">
          <WebSelectBar
            n={pick.size}
            total={list.length}
            all={pick.size === list.length && list.length > 0}
            onAll={() => setPick(pick.size === list.length ? new Set() : new Set(list.map((j) => j.id)))}
            onPin={() => {
              pinJ(picked, true);
              setPick(null);
            }}
            onTrash={() => {
              trashJ(picked);
              setPick(null);
            }}
            onEnd={() => setPick(null)}
          />
        </View>
      ) : null}
      <ContextMenu at={menu?.at ?? null} items={menu?.items ?? []} onClose={() => setMenu(null)} />
      <WebSnackbar visible={!!snack} message={snack?.msg ?? ''} onUndo={snack?.undo} check={snack?.check} style={st.snack} />
    </View>
  );
}

/** 목록 줄 (원본 data-jr-row · hover #F9F9F9 · 지금 기록 #F1EEFB · hover 하면 ⋯ 28) */
function WRow({ j, q, on, pick, onPress, onMenu }: { j: JournalEntry; q: string; on: boolean; pick: boolean | null; onPress: () => void; onMenu: (e: { nativeEvent: unknown }) => void }) {
  const [hov, setHov] = useState(false);
  const hl = (t: string, base: TextStyle) =>
    splitHit(t, q).map((s, i) =>
      i % 2 ? (
        <Text key={i} style={[base, st.hl]}>
          {s}
        </Text>
      ) : (
        s
      ),
    );
  return (
    <View {...data({ bkey: j.id })} onPointerEnter={() => setHov(true)} onPointerLeave={() => setHov(false)}>
      <Pressable onPress={onPress} accessibilityRole="button" style={({ hovered }: Hover) => [st.row, on ? st.rowOn : hovered && st.rowH]}>
        {pick !== null ? <Pick on={pick} /> : null}
        <View style={st.rowTx}>
          <Text style={st.rT} numberOfLines={1}>
            {hl(j.title || '제목 없음', st.rT)}
          </Text>
          <View style={st.rL}>
            <Text style={st.rD}>{j.web_date}</Text>
            <Text style={st.rP} numberOfLines={1}>
              {hl(firstSentence(j), st.rP)}
            </Text>
          </View>
        </View>
      </Pressable>
      {pick === null && hov ? (
        <Pressable accessibilityRole="button" accessibilityLabel="기록 메뉴" onPress={onMenu} style={({ hovered }: Hover) => [st.rowMenu, hovered && { backgroundColor: '#ECECEC' }]}>
          <Dots color="#8B95A1" />
        </Pressable>
      ) : null}
    </View>
  );
}

function Chev({ open }: { open: boolean }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(open ? 0 : 1));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: open ? 0 : 1, duration: 250 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [open, v, k]);
  return (
    <Animated.View style={{ transform: [{ rotate: v.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '-90deg'] }) }] }}>
      <Svg width={12} height={12} viewBox="0 0 12 12" fill="none">
        <Path d="M3 4.5L6 7.5L9 4.5" stroke="#8B95A1" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      </Svg>
    </Animated.View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1 },
  flex: { flex: 1 },
  page: { flex: 1, minHeight: 640, paddingTop: 32, paddingBottom: 32, gap: 32 },
  head: { flexDirection: 'row', alignItems: 'flex-start', paddingTop: 24 },
  headL: { height: 52, flex: 1, minWidth: 0, gap: 4 },
  title: { ...fpx(26, 35), fontWeight: '700', letterSpacing: -0.26, color: '#16171A' },
  sub: { ...fpx(14, 21), color: '#575B63' },
  headR: { position: 'absolute', right: 0, top: 25, flexDirection: 'row', alignItems: 'center', gap: 8 },
  circ: { width: 44, height: 44, borderRadius: 22, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  circH: { backgroundColor: '#F9F9F9' },
  search: { height: 44, width: 280, flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 22, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#FFFFFF', paddingHorizontal: 16 },
  sin: { flex: 1, minWidth: 0, height: 23, ...fpx(15, 23), color: '#16171A', ...({ outlineStyle: 'none' } as object) },
  boxO: { flex: 1, minHeight: 0, flexDirection: 'row', borderRadius: 20, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#FFFFFF', overflow: 'hidden' },
  list: { width: 280, flexGrow: 0, borderRightWidth: 1, borderRightColor: '#E5E7EB' },
  listC: { padding: 12 },
  none: { alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 40 },
  noneT: { ...fpx(15, 23), fontWeight: '700', color: '#333D4B', textAlign: 'center' },
  noneP: { ...fpx(14, 21), color: '#8B95A1', textAlign: 'center' },
  gh: { height: 32, flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8 },
  ghT: { ...fpx(13, 20), fontWeight: '700', color: '#8B95A1' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 12, paddingHorizontal: 16, paddingVertical: 12 },
  rowOn: { backgroundColor: '#F1EEFB' },
  rowH: { backgroundColor: '#F9F9F9' },
  rowTx: { flex: 1, minWidth: 0, gap: 4 },
  rT: { ...fpx(17, 26), fontWeight: '700', color: '#16171A' },
  rL: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  rD: { ...fpx(15, 23), fontWeight: '500', color: '#575B63', flexShrink: 0 },
  rP: { flex: 1, minWidth: 0, ...fpx(15, 23), color: '#6B7078' },
  hl: { backgroundColor: '#FFE58F', borderRadius: 3 },
  rowMenu: { position: 'absolute', right: 8, top: 12, width: 28, height: 28, borderRadius: 8, backgroundColor: 'rgba(255,255,255,0.8)', alignItems: 'center', justifyContent: 'center' },
  empty: { flex: 1, minWidth: 0, alignItems: 'center', justifyContent: 'center', gap: 12, paddingHorizontal: 32 },
  eIll: { width: 60, height: 52, borderRadius: 10, backgroundColor: '#ECEEF1' },
  eBar1: { position: 'absolute', left: 12, right: 12, top: 16, height: 3, borderRadius: 2, backgroundColor: '#C9CCD2' },
  eBar2: { position: 'absolute', left: 12, right: 24, top: 28, height: 3, borderRadius: 2, backgroundColor: '#C9CCD2' },
  eT: { ...fpx(20, 29), fontWeight: '700', color: '#191F28', textAlign: 'center' },
  eP: { ...fpx(15, 23), color: '#6B7684', textAlign: 'center' },
  eBtn: { marginTop: 8, height: 48, borderRadius: 14, backgroundColor: '#111111', paddingHorizontal: 24, justifyContent: 'center' },
  eBtnT: { fontSize: 17, fontWeight: '700', color: '#FFFFFF' },
  ed: { flex: 1, minWidth: 0 },
  curMenu: { position: 'absolute', right: 16, top: 16, zIndex: 10, width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  edC: { paddingHorizontal: 36, paddingTop: 24, paddingBottom: 88 },
  full: { ...fpx(14, 21), color: '#6B7078', textAlign: 'center' },
  edTitle: { ...fpx(30, 40), fontWeight: '700', color: '#16171A' },
  body: { ...fpx(17, 26), color: '#16171A' },
  para: { marginBottom: 10 },
  edHead: { ...fpx(20, 29), fontWeight: '700', color: '#16171A', marginTop: 8 },
  edSub: { ...fpx(17.5, 26), fontWeight: '700', color: '#16171A' },
  todo: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 3 },
  tdBox: { width: 18, height: 18, borderRadius: 9, borderWidth: 1.5, borderColor: '#C7C7CC', backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  tdOn: { borderColor: '#5E5668', backgroundColor: '#5E5668' },
  tdDone: { color: '#9A9EA7', textDecorationLine: 'line-through' },
  selBar: { position: 'absolute', left: 0, right: 0, bottom: 28, alignItems: 'center' },
  snack: { position: 'absolute', bottom: 30 },
});
