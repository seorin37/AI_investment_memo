import React, { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import type { Memo } from '@/types/models';
import { Grip6, PlusGlyph } from '@/ui/icons/BoardGlyphs';
import { FixedFrame } from '@/ui/layout/web/FixedFrame';
import { FadeIn } from '@/ui/motion/Reveal';
import { WebChecklistCard } from '@/ui/shared/ChecklistCard';
import { WebChips } from '@/ui/shared/Chips';
import { ContextMenu, type MenuItem } from '@/ui/shared/ContextMenu';
import { WebMemoCard } from '@/ui/shared/MemoCard';
import { WebMemoRow } from '@/ui/shared/MemoRow';
import { WebSelectBar } from '@/ui/shared/SelectBar';
import { WebSnackbar } from '@/ui/shared/Snackbar';
import { SpentBox } from '@/ui/shared/SpentBox';
import { WebStockHead } from '@/ui/shared/StockHead';
import { PriceNoteHead } from '../PriceNoteHead';
import { WebViewToggle, type BoardView } from '@/ui/shared/ViewToggle';
import { fpx, webColor } from '@/ui/theme';
import type { BoardFilter, MemoBoardProps } from '../MemoBoard.types';
import { useBoardDragWeb, useContextMenuWeb, useEscapeWeb } from './boardDom.web';
import { useCoachRef } from '@/ui/shared/Coach';

const CL = 'cl';
const HOLE = '__hole';
type Snack = { id: number; msg: string; undo?: string[]; check?: boolean };
type HoverState = { pressed: boolean; hovered?: boolean };
const EXAMPLES = ['실적 나오면 다시 보기', '많이 빠지면 다시 생각해 보기', '요즘 분위기 좋아 보여'];
/* RN 타입에 없는 웹 속성 (data-*) */
const data = (o: Record<string, string>) => ({ dataSet: o }) as object;

/**
 * 웹 메모 보드 (원본 web/src/screens/stock.tsx StockPage + board.tsx Board + memox.tsx)
 * 860 고정 틀 (가운데 폭에 맞춰 줄임) · 위 56 · 아래 24 · 사이 20: 종목 머리 · [보드 | 기업 정보] · 보드
 * 보드 (사이 16): (사용량 소진) · 머리 40 ('내 메모 N' 17/26 bold · 칩 · 끌기 안내 · 격자/목록) · 3칸 격자 (276 · 사이 16 / 24 · 위 14 · 아래 40)
 * 카드를 끌어 순서 바꾸기 · hover · ⋯ 메뉴 · 우클릭 메뉴 · Esc. + 버튼 (56 #111 · 가운데 칸 오른쪽 아래 32) · 고르기 막대 (아래 28)
 */
export function WebMemoBoard(p: MemoBoardProps) {
  /* 사용법 안내 ① 대상 (원본 board.tsx data-coach="fab") */
  const fabRef = useCoachRef('fab');
  const [k, setK] = useState(1);
  const [filter, setFilter] = useState<BoardFilter>('all');
  const [view, setView] = useState<BoardView>('grid');
  const [sel, setSel] = useState<string[] | null>(null);
  const [menu, setMenu] = useState<{ id: string; at: { x: number; y: number } } | null>(null);
  const [snack, setSnack] = useState<Snack | null>(null);
  const grid = useRef<React.ComponentRef<typeof View>>(null);

  const byId = (id: string) => p.memos.find((m) => m.id === id);
  const memoKeys = p.memos.map((m) => m.id);
  const allKeys = [...(p.checklist ? [CL] : []), ...memoKeys];
  /* 순서: 받은 순서 중 지금 있는 것 + 순서에 없는 새 것은 맨 앞 (원본 arrange) */
  const order = (() => {
    const has = new Set(allKeys);
    const base = p.order ?? [...(p.checklist ? [CL] : []), ...[...p.memos].sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.created_at.localeCompare(a.created_at)).map((m) => m.id)];
    const placed = base.filter((x) => has.has(x));
    const inLay = new Set(placed);
    return [...allKeys.filter((x) => !inLay.has(x)), ...placed];
  })();

  const shownMemo = (m: Memo) => filter === 'all' || (filter === 'ai' ? m.ai_linked : m.unread_updates > 0);
  const empty = p.memos.length === 0 && !p.checklist;
  const canDrag = filter === 'all' && !sel && view === 'grid';
  const { drag, justDropped } = useBoardDragWeb(grid, !empty && view === 'grid', order, canDrag, k, p.onReorder);
  useContextMenuWeb(grid, !empty && view === 'grid', (key, at) => {
    if (key !== CL && !sel) setMenu({ id: key, at });
  });
  /* Esc: 메뉴 → 고르기 순으로 닫기 (원본 CtxMenu · SelectBar) */
  useEscapeWeb(!!sel || !!menu, () => {
    if (menu) setMenu(null);
    else setSel(null);
  });

  useEffect(() => {
    if (!snack) return;
    const t = setTimeout(() => setSnack((s) => (s && s.id === snack.id ? null : s)), snack.undo ? 5000 : 2600);
    return () => clearTimeout(t);
  }, [snack]);
  const toast = (msg: string, o: { undo?: string[]; check?: boolean } = {}) => setSnack((s) => ({ id: (s?.id ?? 0) + 1, msg, ...o }));

  /* 끄는 동안: 집은 카드는 빼고 놓일 자리에 빈칸 */
  const viewKeys = (() => {
    const ks = order.filter((x) => (x === CL ? filter === 'all' : shownMemo(byId(x)!)));
    if (!drag) return ks;
    const others = ks.filter((x) => x !== drag.key);
    others.splice(Math.min(drag.to, others.length), 0, HOLE);
    return others;
  })();

  const shown = p.memos.filter(shownMemo);
  const toggleSel = (id: string) =>
    setSel((s) => {
      const cur = s ?? [];
      return cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id];
    });
  const trash = (ids: string[]) => {
    p.onDelete(ids);
    toast(ids.length > 1 ? `메모 ${ids.length}개를 휴지통으로 옮겼어요` : '메모를 휴지통으로 옮겼어요', { undo: ids });
  };
  const pin = (ids: string[], on: boolean) => {
    p.onPin(ids, on);
    toast(on ? (ids.length > 1 ? `${ids.length}개를 고정했어요` : '메모를 고정했어요') : '고정을 풀었어요', { check: true });
  };
  const copy = (ids: string[]) => {
    p.onCopy(ids);
    toast('내용을 복사했어요', { check: true });
  };
  const open = (m: Memo) => {
    if (justDropped()) return;
    p.onOpenMemo(m.id, m.unread_updates > 0 && m.ai_linked ? 'ai' : 'memo');
  };
  const menuItems = (m: Memo): MenuItem[] => [
    { label: '열기', icon: 'find', run: () => open(m) },
    { label: m.pinned ? '테이프 떼기' : '테이프 붙여 맨 위로', icon: 'pin', run: () => pin([m.id], !m.pinned) },
    { label: '내용 복사', icon: 'copy', run: () => copy([m.id]) },
    { label: '여러 개 선택', icon: 'select', run: () => setSel([m.id]) },
    '-',
    { label: '휴지통으로 이동', icon: 'trash', danger: true, run: () => trash([m.id]) },
  ];
  const lifted = drag ? (drag.key === CL ? null : byId(drag.key)) : null;

  return (
    <View style={st.root}>
      <ScrollView style={st.flex} showsVerticalScrollIndicator={false}>
        <FixedFrame onScale={setK}>
          <View style={st.page}>
            {p.priceNote ? <PriceNoteHead stock={p.stock} note={p.priceNote} variant="web" /> : <WebStockHead {...p.stock} />}
            <View style={st.tabs}>
              {(['board', 'company'] as const).map((t) => (
                <Pressable key={t} onPress={() => t === 'company' && p.onChangeTab('company')} accessibilityRole="tab" accessibilityState={{ selected: t === 'board' }} style={[st.tab, t === 'board' ? st.tabOn : st.tabOff]}>
                  {({ hovered }: HoverState) => <Text style={[st.tabT, { color: t === 'board' ? '#FFFFFF' : hovered ? webColor.strong : webColor.mute }]}>{t === 'board' ? '보드' : '기업 정보'}</Text>}
                </Pressable>
              ))}
            </View>
            <View style={st.board}>
              {p.aiSpent ? <SpentBox variant="web" title="AI 사용량을 다 썼어요" body={p.aiCount ? `충전하거나 플랜을 업그레이드하지 않으면 AI 연결 메모 ${p.aiCount}개가 모두 꺼져요.\n메모는 계속 쓸 수 있어요.` : `${p.aiRefill && p.aiRefill !== '—' ? p.aiRefill : '다음 갱신일'}에 새로 채워져요.\n그때까지 새 메모는 일반 메모로 저장돼요.`} onCredit={() => p.onSpentAction?.('credit')} onPlan={() => p.onSpentAction?.('plan')} onOff={p.aiCount ? () => p.onSpentAction?.('choice') : undefined} /> : null}
              {!empty ? (
                <View style={st.head}>
                  <Text style={st.headT}>내 메모 {p.memos.length}</Text>
                  <WebChips
                    value={filter}
                    onChange={setFilter}
                    options={[
                      { key: 'all', label: '전체' },
                      { key: 'ai', label: 'AI 연결', count: p.memos.filter((m) => m.ai_linked).length },
                      { key: 'new', label: '새 소식', count: p.memos.filter((m) => m.unread_updates > 0).length, dot: p.memos.some((m) => m.unread_updates > 0) },
                    ]}
                  />
                  {canDrag && !p.orderCustomized && p.memos.length > 1 ? (
                    <View style={st.hint}>
                      <Grip6 color={webColor.sub2} />
                      <Text style={st.hintT}>꾹 눌러 끌면 위치를 바꿀 수 있어요</Text>
                    </View>
                  ) : null}
                  <View style={[st.vt, canDrag && !p.orderCustomized && p.memos.length > 1 && { marginLeft: 8 }]}>
                    <WebViewToggle value={view} onChange={setView} />
                  </View>
                </View>
              ) : null}
              {empty ? (
                <EmptyBoard name={p.stock.name} onExample={(t) => p.onNewMemo(t)} onFirst={() => p.onNewMemo()} onChecklist={p.onNewChecklist} />
              ) : view === 'list' ? (
                <FadeIn style={st.list}>
                  {[...shown]
                    .sort((a, b) => Number(b.pinned) - Number(a.pinned))
                    .map((m, i) => (
                      <WebMemoRow key={m.id} memo={m} first={i === 0} selecting={!!sel} selected={!!sel?.includes(m.id)} onOpen={() => open(m)} onPick={() => toggleSel(m.id)} onMenu={(at) => setMenu({ id: m.id, at })} />
                    ))}
                  {shown.length === 0 ? <Text style={st.none}>조건에 맞는 메모가 없어요</Text> : null}
                </FadeIn>
              ) : (
                <View style={st.gridWrap}>
                  <View ref={grid} style={st.grid}>
                    {viewKeys.map((key) => {
                      if (key === HOLE) return <View key={HOLE} style={st.hole} />;
                      if (key === CL)
                        return (
                          <View key={CL} {...data({ bkey: CL })} style={st.slot}>
                            <WebChecklistCard checklist={p.checklist!} onOpen={() => !justDropped() && p.onOpenChecklist()} onToggleItem={p.onToggleChecklistItem} />
                          </View>
                        );
                      const m = byId(key)!;
                      return (
                        <View key={key} {...data({ bkey: key })} style={st.slot}>
                          <WebMemoCard memo={m} selecting={!!sel} selected={!!sel?.includes(key)} onOpen={() => open(m)} onPick={() => toggleSel(key)} onPin={() => pin([key], !m.pinned)} onToggleAi={() => p.onToggleAi(key)} onMenu={(at) => setMenu({ id: key, at })} aiSpent={p.aiSpent} />
                        </View>
                      );
                    })}
                    {filter === 'all' && !p.checklist && !sel ? (
                      <Pressable onPress={p.onNewChecklist} accessibilityRole="button" style={({ hovered }: HoverState) => [st.newCl, hovered && { backgroundColor: '#FFFFFF' }]}>
                        <Svg width={16} height={16} viewBox="0 0 16 16" fill="none">
                          <Path d="M8 3V13M3 8H13" stroke="#6B7684" strokeWidth={1.6} strokeLinecap="round" />
                        </Svg>
                        <Text style={st.newClT}>체크리스트 만들기</Text>
                      </Pressable>
                    ) : null}
                    {drag ? (
                      /* 집은 카드: 손을 따라옴 · 1.03배 · -1° · 그림자 (원본 .b-lifted) */
                      <View pointerEvents="none" style={[st.lifted, { left: drag.left, top: drag.top }]}>
                        {lifted ? (
                          <WebMemoCard memo={lifted} selecting={false} selected={false} onOpen={() => {}} onPick={() => {}} onPin={() => {}} onToggleAi={() => {}} onMenu={() => {}} />
                        ) : p.checklist ? (
                          <WebChecklistCard checklist={p.checklist} onOpen={() => {}} onToggleItem={() => {}} />
                        ) : null}
                      </View>
                    ) : null}
                  </View>
                </View>
              )}
            </View>
          </View>
        </FixedFrame>
      </ScrollView>
      {/* + 버튼 (원본 NewMemoFab: 56 · #111 · 오른쪽 아래 32 · 그림자) */}
      {!sel ? (
        <Pressable ref={fabRef} onPress={() => p.onNewMemo()} accessibilityRole="button" accessibilityLabel="새 메모" style={({ hovered, pressed }: HoverState) => [st.fab, { transform: [{ scale: pressed ? 0.95 : hovered ? 1.05 : 1 }] }]}>
          <PlusGlyph size={24} stroke={2.2} />
        </Pressable>
      ) : null}
      {sel ? (
        <View style={st.selAt} pointerEvents="box-none">
          <WebSelectBar
            n={sel.length}
            total={shown.length}
            all={sel.length === shown.length && shown.length > 0}
            onAll={() => setSel(sel.length === shown.length ? [] : shown.map((m) => m.id))}
            onPin={() => {
              pin(sel, true);
              setSel(null);
            }}
            onCopy={() => {
              copy(sel);
              setSel(null);
            }}
            onTrash={() => {
              trash(sel);
              setSel(null);
            }}
            onEnd={() => setSel(null)}
          />
        </View>
      ) : null}
      <View style={st.snackAt} pointerEvents="box-none">
        <WebSnackbar
          visible={!!snack}
          message={snack?.msg ?? ''}
          check={snack?.check}
          onUndo={
            snack?.undo
              ? () => {
                  p.onUndoDelete(snack.undo!);
                  setSnack(null);
                }
              : undefined
          }
        />
      </View>
      <ContextMenu at={menu?.at ?? null} items={menu && byId(menu.id) ? menuItems(byId(menu.id)!) : []} onClose={() => setMenu(null)} />
    </View>
  );
}

/**
 * 웹 빈 보드 (원본 board.tsx: 점선 테두리 #CFD3D9 · 라운드 20 · 흰 · 32/48 · 사이 20
 * 메모지 그림 60×52 · '{종목}에 대한 첫 메모를 남겨 보세요' 22/31 bold · 설명 15/23 #6B7684
 * 예시 칩 40 (테두리 #E5E7EB · 15/23 500 #333D4B) · [첫 메모 쓰기] 48 #111 17/26 bold · [체크리스트 만들기] 48 #F2F3F4)
 */
function EmptyBoard({ name, onExample, onFirst, onChecklist }: { name: string; onExample: (t: string) => void; onFirst: () => void; onChecklist: () => void }) {
  return (
    <FadeIn style={st.empty}>
      <Svg width={60} height={52} viewBox="0 0 60 52">
        <Path d="M10 0H50A10 10 0 0 1 60 10V36L44 52H10A10 10 0 0 1 0 42V10A10 10 0 0 1 10 0Z" fill="#FCEAAA" />
        <Path d="M0 9C0 3 3 0 9 0H30L0 30V9Z" fill="#EFBF2A" transform="translate(44 36) scale(0.5333)" />
      </Svg>
      <View style={st.emptyText}>
        <Text style={st.emptyT}>{name}에 대한 첫 메모를 남겨 보세요</Text>
        <Text style={st.emptyB}>{'떠오른 생각 한 줄부터 적어 보세요.\nAI 연결을 켜 두면 관련 공시·뉴스를 대신 확인해 드려요.'}</Text>
      </View>
      <View style={st.exRow}>
        {EXAMPLES.map((t) => (
          <Pressable key={t} onPress={() => onExample(t)} accessibilityRole="button" style={({ hovered }: HoverState) => [st.ex, hovered && { backgroundColor: webColor.hover }]}>
            <Text style={st.exT}>{t}</Text>
          </Pressable>
        ))}
      </View>
      <View style={st.btns}>
        <Pressable onPress={onFirst} accessibilityRole="button" style={({ hovered }: HoverState) => [st.first, { backgroundColor: hovered ? '#2A2A2A' : '#111111' }]}>
          <Text style={[st.btnT, { color: '#FFFFFF' }]}>첫 메모 쓰기</Text>
        </Pressable>
        <Pressable onPress={onChecklist} accessibilityRole="button" style={({ hovered }: HoverState) => [st.first, { backgroundColor: hovered ? webColor.chipHover : webColor.chip, paddingHorizontal: 20 }]}>
          <Text style={[st.btnT, { color: webColor.ink }]}>체크리스트 만들기</Text>
        </Pressable>
      </View>
    </FadeIn>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: webColor.page },
  flex: { flex: 1 },
  page: { width: 860, gap: 20, paddingTop: 56, paddingBottom: 24 },
  tabs: { flexDirection: 'row', gap: 8 },
  tab: { minHeight: 40, borderRadius: 20, paddingHorizontal: 20, justifyContent: 'center' },
  tabOn: { backgroundColor: '#000000' },
  tabOff: { backgroundColor: '#FFFFFF' },
  tabT: { ...fpx(15, 23), fontWeight: '500' },
  board: { gap: 16 },
  head: { height: 40, flexDirection: 'row', alignItems: 'center', gap: 12 },
  headT: { ...fpx(17, 26), fontWeight: '700', color: webColor.ink },
  hint: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 4 },
  hintT: { ...fpx(13, 20), color: webColor.sub2 },
  vt: { marginLeft: 'auto' },
  list: { width: '100%', overflow: 'hidden', borderRadius: 20, borderWidth: 1, borderColor: webColor.line, backgroundColor: '#FFFFFF' },
  none: { paddingHorizontal: 20, paddingVertical: 40, textAlign: 'center', ...fpx(15, 23), fontWeight: '500', color: webColor.sub2 },
  gridWrap: { paddingTop: 14, paddingBottom: 40 },
  grid: { position: 'relative', width: 860, flexDirection: 'row', flexWrap: 'wrap', columnGap: 16, rowGap: 24, alignItems: 'flex-start' },
  slot: { width: 276 },
  hole: { width: 276, height: 200, borderRadius: 16, borderWidth: 2, borderStyle: 'dashed', borderColor: '#C9CCD2', backgroundColor: 'rgba(17,17,17,0.03)' },
  lifted: { position: 'absolute', zIndex: 50, width: 276, transform: [{ scale: 1.03 }, { rotate: '-1deg' }], shadowColor: '#000000', shadowOpacity: 0.22, shadowRadius: 28, shadowOffset: { width: 0, height: 18 } },
  newCl: { width: 276, height: 72, borderRadius: 16, borderWidth: 1, borderStyle: 'dashed', borderColor: '#D8DBE0', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  newClT: { ...fpx(15, 23), fontWeight: '500', color: '#6B7684' },
  fab: { position: 'absolute', right: 32, bottom: 32, width: 56, height: 56, borderRadius: 28, backgroundColor: '#111111', alignItems: 'center', justifyContent: 'center', zIndex: 40, shadowColor: '#000000', shadowOpacity: 0.45, shadowRadius: 14, shadowOffset: { width: 0, height: 8 }, elevation: 8 },
  selAt: { position: 'absolute', left: 0, right: 0, bottom: 28, alignItems: 'center', zIndex: 72 },
  snackAt: { position: 'absolute', left: 0, right: 0, bottom: 30, alignItems: 'center', zIndex: 90 },
  empty: { width: '100%', alignItems: 'center', gap: 20, borderRadius: 20, borderWidth: 1, borderStyle: 'dashed', borderColor: '#CFD3D9', backgroundColor: '#FFFFFF', paddingHorizontal: 32, paddingVertical: 48 },
  emptyText: { alignItems: 'center', gap: 8 },
  emptyT: { ...fpx(22, 31), fontWeight: '700', color: webColor.strong, textAlign: 'center' },
  emptyB: { ...fpx(15, 23), color: '#6B7684', textAlign: 'center' },
  exRow: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 8 },
  ex: { minHeight: 40, borderRadius: 999, borderWidth: 1, borderColor: webColor.line, backgroundColor: '#FFFFFF', paddingHorizontal: 16, justifyContent: 'center' },
  exT: { ...fpx(15, 23), fontWeight: '500', color: '#333D4B' },
  btns: { flexDirection: 'row', gap: 8 },
  first: { minHeight: 48, borderRadius: 14, paddingHorizontal: 24, justifyContent: 'center' },
  btnT: { ...fpx(17, 26), fontWeight: '700' },
});
