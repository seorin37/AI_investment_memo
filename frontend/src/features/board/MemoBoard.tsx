/* eslint-disable react-hooks/refs, react-hooks/set-state-in-effect -- RN Animated 관용 패턴. React Compiler 켜면 이 파일부터 정리 필요 */
/**
 * 메모 보드 (종목별). 체험판 memo.html 의 보드 부분 — 움직임 포함.
 *  - 위: 종목 요약 카드 + [메모 보드 | 기업정보]
 *  - 내 메모 N · 필터 칩(전체 · AI 연결 · 새 소식 N, 알약이 미끄러짐 #039) · 2열/목록 전환(손잡이 #047)
 *  - 2열 ↔ 목록: 카드가 제자리로 날아가며 모양이 바뀜 (#308 · .56s) / 필터로 빠지는 카드는 흐려지며 비켜 남
 *  - 불러오는 동안 빛줄기 뼈대 → 걷히고 나서 내용 (#079)
 *  - 체크리스트 카드: 줄을 누르면 바로 체크(잉크 #014 + 점 8개 #093) · 다 끝내면 카드 위에서 색종이(#093)
 *  - 꾹 누르기 → 고르기: 위 막대가 내려오고 아래 막대가 올라옴(#178) · 색상은 아래 시트(#336)
 *  - + 버튼 → 부채꼴로 메모 / 체크리스트 (#011)
 *  - 목록 보기에서 메모 줄 밀기: 오른쪽 → 고정 · 왼쪽 → [AI 연결 · 휴지통] (11.18 스와이프 허용 결정)
 *  - 휴지통 · 복사 · 고정 뒤 알림 + 되돌리기 (#071) · 당겨서 새로고침 (#085)
 *  - 메모가 없으면 빈 보드 안내 + 예시 칩 (떠오르며 나타남)
 * 모션 참고: Lucian UX/UI Prompt · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, Pressable, RefreshControl, ScrollView, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import { Text } from '@/components/ui/AppText';
import Svg, { Polygon } from 'react-native-svg';
import { MobileIcon, type MobileIconName } from '@/components/icons/MobileIcons';
import { StockSummaryCard } from '@/components/mobile/StockSummaryCard';
import { Appear, PopWhen } from '@/components/motion/Appear';
import { BottomSheet } from '@/components/motion/BottomSheet';
import { Confetti } from '@/components/motion/Celebrate';
import { FabFan } from '@/components/motion/FabFan';
import { InkCheck } from '@/components/motion/InkCheck';
import { EASE, ND, SPRING, tween, useValue } from '@/components/motion/motion';
import { Shimmer, SkeletonSwap } from '@/components/motion/Skeleton';
import { SlidingPill } from '@/components/motion/SlidingPill';
import { SwipeRow } from '@/components/motion/SwipeRow';
import { Snackbar } from '@/components/motion/Snackbar';
import { useBackClose } from '@/hooks/useBackClose';
import { usePressScale } from '@/components/motion/StateMotion';
import type { MemoColor } from '@/types/models';
import { BOARD_C as C, CHECKLIST_C as CK, MEMO_PAPER } from '@/features/board/boardTokens';
import type { BoardChecklist, BoardEntry, BoardFilter, BoardMemo, BoardViewMode, MemoBoardProps } from '@/features/board/MemoBoard.types';

const PAD = 16;
const GAP = 12;
const R = { memo: 16, chip: 15, btn: 12 };
const CARD_H = 150;
const CARD_STEP = CARD_H + 16;
const ROW_H = 64;
const MORPH = 560;
const COLORS: MemoColor[] = ['yellow', 'green', 'blue', 'purple', 'pink'];

const mmdd = (iso: string) => {
  const d = new Date(iso);
  return `${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
};
const dateLabel = (it: BoardEntry) => (it.updated_at > it.created_at ? `${mmdd(it.updated_at)} 수정` : `${mmdd(it.created_at)} 작성`);
/** 고정 먼저 → 최근에 쓰거나 고친 순 (11.18 결정: 직접 순서 바꾸기는 넣지 않음) */
const sortItems = (a: BoardEntry, b: BoardEntry) => Number(b.pinned) - Number(a.pinned) || (a.updated_at < b.updated_at ? 1 : -1);
/** 체크리스트 카드에는 안 한 항목을 먼저 */
const ordered = (c: BoardChecklist) => [...c.items.filter((x) => !x.done), ...c.items.filter((x) => x.done)];
const allDone = (c: BoardChecklist) => c.items.length > 0 && c.items.every((x) => x.done);

type Box = { x: number; y: number; w: number; h: number };
/** 체험판 pos(): 2열은 낮은 쪽 칸부터, 목록은 한 줄씩 */
function place(list: BoardEntry[], mode: BoardViewMode, W: number): { boxes: Record<string, Box>; height: number } {
  const boxes: Record<string, Box> = {};
  if (mode === 'grid') {
    const colW = (W - PAD * 2 - GAP) / 2;
    const h = [4, 4];
    list.forEach((it) => { const c = h[0] <= h[1] ? 0 : 1; boxes[it.id] = { x: PAD + c * (colW + GAP), y: h[c], w: colW, h: CARD_H }; h[c] += CARD_STEP; });
    return { boxes, height: Math.max(h[0], h[1]) };
  }
  list.forEach((it, i) => { boxes[it.id] = { x: 0, y: 4 + i * ROW_H, w: W, h: ROW_H }; });
  return { boxes, height: list.length * ROW_H + 12 };
}

type Snack = { message: string; undo?: string[]; n: number } | null;

export function MemoBoard(props: MemoBoardProps) {
  const { stock, items, loading, examples, onChangeTab, onOpenMemo, onOpenChecklist, onToggleChecklistItem, onCreate, onPin, onDelete, onCopy, onChangeColor, onToggleAi, onSelectionChange, onUndoDelete, refreshing, onRefresh, flash_id } = props;
  const [filter, setFilter] = useState<BoardFilter>('all');
  const [view, setView] = useState<BoardViewMode>('grid');
  const [sel, setSel] = useState<string[]>([]);
  const [fanOpen, setFanOpen] = useState(false);
  const [colorOpen, setColorOpen] = useState(false);
  const [W, setW] = useState(0);
  const [confetti, setConfetti] = useState<{ x: number; y: number; id: number } | null>(null);
  const [snack, setSnack] = useState<Snack>(null);
  const [openRow, setOpenRow] = useState<string | null>(null);
  /* 안드로이드 뒤로가기: 메뉴 닫기 → 밀린 줄 닫기 → 고르기 해제 순서로 먼저 처리 (색 시트는 BottomSheet Modal 이 닫음) */
  useBackClose(() => {
    if (fanOpen) { setFanOpen(false); return true; }
    if (openRow) { setOpenRow(null); return true; }
    if (sel.length) { setSel([]); return true; }
    return false;
  });

  const live = useMemo(() => [...items].sort(sortItems), [items]);
  const newCount = live.reduce((a, it) => a + (it.kind === 'memo' ? it.unread_updates : 0), 0);
  const shown = useMemo(() => live.filter((it) => filter === 'all' || (filter === 'ai' && it.kind === 'memo' && it.ai_linked) || (filter === 'new' && it.kind === 'memo' && it.unread_updates > 0)), [live, filter]);
  const memoCount = live.filter((it) => it.kind === 'memo').length;
  const selecting = sel.length > 0;
  const lastSel = useRef(1);
  if (selecting) lastSel.current = sel.length;

  const { boxes, height } = useMemo(() => place(shown, view, W), [shown, view, W]);
  const lastBox = useRef<Record<string, Box>>({});
  Object.assign(lastBox.current, boxes);

  /** 보드 높이 · 2열/목록 섞이는 정도 (#308) */
  const boardH = useValue(0);
  const modeV = useValue(0);
  const firstH = useRef(true);
  useEffect(() => {
    if (!W) return;
    if (firstH.current) { boardH.setValue(height); firstH.current = false; return; }
    tween(boardH, height, MORPH, EASE, false).start();
  }, [height, W, boardH]);
  useEffect(() => { tween(modeV, view === 'list' ? 1 : 0, MORPH, EASE, false).start(); }, [view, modeV]);

  /** 고르기 막대 (#178): 위는 8px 위에서 내려오고, 아래는 밑에서 올라옴 (.38s spring) */
  const selV = useValue(0);
  useEffect(() => { tween(selV, selecting ? 1 : 0, selecting ? 380 : 300, selecting ? SPRING : EASE, ND).start(); }, [selecting, selV]);

  useEffect(() => { onSelectionChange?.(sel.length); }, [sel.length, onSelectionChange]);
  useEffect(() => { setOpenRow(null); }, [view, selecting, filter]);
  useEffect(() => { if (filter === 'new' && newCount === 0) setFilter('all'); }, [filter, newCount]);

  /** 체크리스트를 다 끝낸 순간 → 카드 위에서 색종이 (체험판: 320ms 뒤) */
  const prevDone = useRef<Record<string, boolean>>({});
  useEffect(() => {
    live.forEach((it) => {
      if (it.kind !== 'checklist') return;
      const done = allDone(it);
      if (done && prevDone.current[it.id] === false) {
        const b = lastBox.current[it.id];
        if (b) setTimeout(() => { setConfetti({ x: b.x + b.w / 2, y: b.y + 30, id: Date.now() }); setSnack((s) => ({ message: '체크리스트를 모두 끝냈어요', n: (s?.n ?? 0) + 1 })); }, 320);
      }
      prevDone.current[it.id] = done;
    });
  }, [live]);

  const toggleSel = (id: string) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const startSel = (id: string) => { setFanOpen(false); setSel([id]); };
  const endSel = () => setSel([]);
  const pressItem = (it: BoardEntry) => {
    if (selecting) { toggleSel(it.id); return; }
    if (it.kind === 'checklist') onOpenChecklist(it.id);
    else onOpenMemo(it.id, it.unread_updates > 0 && it.ai_linked ? 'ai' : 'memo');
  };
  const say = (message: string, undo?: string[]) => setSnack((s) => ({ message, undo, n: (s?.n ?? 0) + 1 }));

  const selItems = live.filter((it) => sel.includes(it.id));
  const one = selItems.length === 1;
  const hasCk = selItems.some((it) => it.kind === 'checklist');
  const allPinned = selItems.length > 0 && selItems.every((it) => it.pinned);
  const oneMemo = one && selItems[0].kind === 'memo' ? (selItems[0] as BoardMemo) : null;

  const filters = [
    { key: 'all' as const, label: '전체' },
    { key: 'ai' as const, label: 'AI 연결' },
    ...(newCount > 0 ? [{ key: 'new' as const, label: `새 소식 ${newCount}`, render: (on: boolean) => (
      <><View style={[st.chipDot, on && st.chipDotOn]} /><Text style={[st.chipText, on && st.chipTextOn]}>새 소식 {newCount}</Text></>
    ) }] : []),
  ];

  return (
    <View style={st.root}>
      <ScrollView contentContainerStyle={st.scroll} showsVerticalScrollIndicator={false}
        refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={C.accent} colors={[C.accent]} /> : undefined}>
        <StockSummaryCard stock={stock} tab="board" onChangeTab={onChangeTab} />
        <Appear kind="tab">
          <Text style={st.mh}>내 메모 <Text style={st.mhNum}>{memoCount}</Text></Text>
          <View style={st.frow}>
            <SlidingPill items={filters} value={filter} onChange={setFilter} gap={6} hitSlop={6}
              itemStyle={st.chip} itemOnStyle={st.chipOn} pillStyle={st.chipPill} textStyle={st.chipText} textOnStyle={st.chipTextOn} />
            <View style={st.flex} />
            <SlidingPill items={[
              { key: 'grid' as const, accessibilityLabel: '2열 보기', render: (on: boolean) => <MobileIcon name="grid" size={16} color={on ? C.text : C.muted} /> },
              { key: 'list' as const, accessibilityLabel: '목록 보기', render: (on: boolean) => <MobileIcon name="list" size={16} color={on ? C.text : C.muted} /> },
            ]} value={view} onChange={setView} style={st.vt} itemStyle={st.vtBtn} pillStyle={st.vtKnob} hitSlop={7} />
          </View>

          <View onLayout={(e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width)}>
            <SkeletonSwap loading={!!loading} skeleton={<SkeletonGrid W={W} />}>
              {live.length === 0 ? (
                <EmptyBoard examples={examples} onExample={(t) => onCreate('memo', t)} onFirst={() => onCreate('memo')} />
              ) : W === 0 ? null : (
                <Animated.View style={{ height: boardH }}>
                  {live.map((it) => (
                    <BoardItem key={it.id} it={it} box={boxes[it.id] ?? lastBox.current[it.id] ?? { x: PAD, y: 4, w: 1, h: 1 }} visible={!!boxes[it.id]}
                      view={view} modeV={modeV} selected={sel.includes(it.id)} selecting={selecting} flash={flash_id === it.id}
                      onPress={() => pressItem(it)} onLongPress={() => startSel(it.id)}
                      onToggleItem={(itemId) => (selecting ? toggleSel(it.id) : onToggleChecklistItem(it.id, itemId))}
                      swipe={{
                        open: openRow === it.id,
                        onOpenChange: (o) => setOpenRow(o ? it.id : null),
                        onPin: () => { onPin([it.id], !it.pinned); say(it.pinned ? '고정을 풀었어요' : '보드 맨 위에 고정했어요'); },
                        onAi: () => onToggleAi(it.id),
                        onDelete: () => { onDelete([it.id]); say('1개를 휴지통으로 옮겼어요', onUndoDelete ? [it.id] : undefined); },
                      }} />
                  ))}
                  <Confetti fire={confetti} />
                </Animated.View>
              )}
            </SkeletonSwap>
          </View>
        </Appear>
      </ScrollView>

      {/* 고르기 위 막대 (#178) */}
      <Animated.View pointerEvents={selecting ? 'auto' : 'none'} style={[st.selHead, { opacity: selV.interpolate({ inputRange: [0, 1], outputRange: [0, 1], extrapolate: 'clamp' }),
        transform: [{ translateY: selV.interpolate({ inputRange: [0, 1], outputRange: [-8, 0] }) }] }]}>
        <Pressable style={st.iconBtn} onPress={endSel} accessibilityLabel="선택 끝내기"><MobileIcon name="close" size={20} color={C.text} /></Pressable>
        <Text style={st.selCount}>{lastSel.current}개 선택</Text>
        <Pressable style={st.textBtn} onPress={() => (sel.length === shown.length ? endSel() : setSel(shown.map((x) => x.id)))}>
          <Text style={st.selAll}>{sel.length === shown.length ? '선택 해제' : '전체 선택'}</Text>
        </Pressable>
      </Animated.View>

      {/* + 버튼 부채꼴 (#011) */}
      {!selecting && (
        <FabFan open={fanOpen} onOpenChange={setFanOpen} onPick={(k) => onCreate(k)} color={C.accent} haloColor={C.accent} scrimColor={C.scrim} shadowColor={C.accentDeep}
          items={[
            { key: 'checklist', label: '체크리스트', icon: 'checklist', color: CK.tape, dx: -6, dy: -79 },
            { key: 'memo', label: '메모', icon: 'memo', color: C.accentDeep, dx: -88, dy: -15 },
          ]} />
      )}

      {/* 고르기 아래 막대 (#178 · 하단 탭바 자리, 호스트가 onSelectionChange 로 탭바를 숨김) */}
      <Animated.View pointerEvents={selecting ? 'auto' : 'none'} style={[st.selBar, { transform: [{ translateY: selV.interpolate({ inputRange: [0, 1], outputRange: [96, 0] }) }] }]}>
        <SelBtn icon="pin" label={allPinned ? '고정 해제' : '고정'} onPress={() => { onPin(sel, !allPinned); say(allPinned ? '고정을 풀었어요' : '보드 맨 위에 고정했어요'); endSel(); }} />
        <SelBtn icon="palette" label="색상" disabled={hasCk} onPress={() => setColorOpen(true)} />
        <SelBtn icon="plug" label={oneMemo?.ai_linked ? 'AI 끄기' : 'AI 연결'} disabled={!oneMemo} onPress={() => { if (oneMemo) onToggleAi(oneMemo.id); endSel(); }} />
        <SelBtn icon="copy" label="복사" disabled={!one} onPress={() => { onCopy(sel[0]); say('복사했어요'); endSel(); }} />
        <SelBtn icon="trash" label="휴지통" danger onPress={() => { const ids = [...sel]; onDelete(ids); say(`${ids.length}개를 휴지통으로 옮겼어요`, onUndoDelete ? ids : undefined); endSel(); }} />
      </Animated.View>

      <Snackbar message={snack?.message ?? null} count={snack?.n} bottom={selecting ? 92 : 86}
        actionLabel={snack?.undo ? '되돌리기' : undefined}
        onAction={() => { if (snack?.undo) onUndoDelete?.(snack.undo); setSnack(null); }}
        onTimeout={() => setSnack(null)} />

      <BottomSheet open={colorOpen} onClose={() => setColorOpen(false)} accessibilityLabel="메모지 색">
        <Text style={st.sheetTitle}>메모지 색</Text>
        <View style={st.swatches}>
          {COLORS.map((c) => <Swatch key={c} color={c} onPress={() => { onChangeColor(sel, c); setColorOpen(false); endSel(); }} />)}
        </View>
      </BottomSheet>
    </View>
  );
}

function SkeletonGrid({ W }: { W: number }) {
  const colW = W ? (W - PAD * 2 - GAP) / 2 : 0;
  return (
    <View style={st.skGrid}>
      {[0, 1].map((c) => (
        <View key={c} style={st.skCol}>
          {[0, 1].map((r) => <Shimmer key={r} offset_x={PAD + c * (colW + GAP)} color={C.skeleton} style={st.skel} />)}
        </View>
      ))}
    </View>
  );
}

/** 카드 1장: 자리(box)로 .56s 날아가고, 2열 얼굴 ↔ 목록 얼굴이 엇갈려 바뀜 (#308) */
type RowSwipe = { open: boolean; onOpenChange: (open: boolean) => void; onPin: () => void; onAi: () => void; onDelete: () => void };

function BoardItem({ it, box, visible, view, modeV, selected, selecting, flash, onPress, onLongPress, onToggleItem, swipe }: {
  it: BoardEntry; box: Box; visible: boolean; view: BoardViewMode; modeV: Animated.Value; selected: boolean; selecting: boolean; flash: boolean;
  onPress: () => void; onLongPress: () => void; onToggleItem: (item_id: string) => void; swipe: RowSwipe;
}) {
  const x = useValue(box.x), y = useValue(box.y), w = useValue(box.w), h = useValue(box.h), o = useValue(visible ? 1 : 0);
  const ring = useValue(0);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    Animated.parallel([tween(x, box.x, MORPH, EASE, false), tween(y, box.y, MORPH, EASE, false), tween(w, box.w, MORPH, EASE, false), tween(h, box.h, MORPH, EASE, false)]).start();
  }, [box.x, box.y, box.w, box.h, x, y, w, h]);
  useEffect(() => { tween(o, visible ? 1 : 0, visible ? 320 : 200, EASE, false).start(); }, [visible, o]);
  useEffect(() => {
    if (!flash) return;
    ring.setValue(1);
    Animated.sequence([Animated.delay(490), tween(ring, 0, 910, EASE, false)]).start();
  }, [flash, ring]);
  const gridO = modeV.interpolate({ inputRange: [0, 0.35], outputRange: [1, 0], extrapolate: 'clamp' });
  const listO = modeV.interpolate({ inputRange: [0.4, 0.8], outputRange: [0, 1], extrapolate: 'clamp' });
  const label = it.kind === 'checklist' ? `${it.title}, ${it.items.filter((v) => v.done).length}/${it.items.length} 완료` : it.title;
  return (
    <Animated.View pointerEvents={visible ? 'auto' : 'none'} style={{ position: 'absolute', left: x, top: y, width: w, height: h, opacity: o }}>
      <Pressable style={StyleSheet.absoluteFill} onPress={onPress} onLongPress={onLongPress} delayLongPress={480} accessibilityLabel={label} accessibilityState={{ selected }}>
        <Animated.View pointerEvents={view === 'grid' ? 'box-none' : 'none'} style={[StyleSheet.absoluteFill, { opacity: gridO }]}>
          <GridFace it={it} selected={selected} selecting={selecting} onToggleItem={onToggleItem} />
        </Animated.View>
        <Animated.View pointerEvents={view === 'list' ? 'box-none' : 'none'} style={[StyleSheet.absoluteFill, { opacity: listO }]}>
          {it.kind === 'memo' ? (
            <SwipeRow fill enabled={view === 'list' && !selecting} open={swipe.open} onOpenChange={swipe.onOpenChange}
              left={{ label: it.pinned ? '고정 해제' : '고정', icon: 'pin', color: C.pinSwipe, onTrigger: swipe.onPin }}
              right={[
                { key: 'ai', label: it.ai_linked ? 'AI 끄기' : 'AI 연결', icon: 'plug', color: C.accent, onPress: swipe.onAi },
                { key: 'del', label: '휴지통', icon: 'trash', color: C.red, onPress: swipe.onDelete },
              ]}>
              <ListFace it={it} selected={selected} selecting={selecting} />
            </SwipeRow>
          ) : <ListFace it={it} selected={selected} selecting={selecting} />}
        </Animated.View>
      </Pressable>
      <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFill, st.flash, { opacity: ring, borderRadius: view === 'grid' ? R.memo : 0 }]} />
    </Animated.View>
  );
}

/** 접힌 모서리: 오른쪽 아래 삼각형은 바탕색(잘려 나간 부분), 왼쪽 위 삼각형은 접힌 종이 */
function Fold({ color, size = 24 }: { color: string; size?: number }) {
  return (
    <Svg width={size} height={size} style={st.fold}>
      <Polygon points={`${size},0 ${size},${size} 0,${size}`} fill={C.card} />
      <Polygon points={`0,0 ${size},0 0,${size}`} fill={color} />
    </Svg>
  );
}

function Tape({ color }: { color: string }) {
  return (
    <Svg width={57} height={19} style={st.tape}>
      <Polygon points="0,0 57,0 54.7,3.2 57,6.3 54.7,9.5 57,12.7 54.7,15.8 57,19 0,19 2.3,15.8 0,12.7 2.3,9.5 0,6.3 2.3,3.2" fill={color} fillOpacity={0.82} />
    </Svg>
  );
}

function GridFace({ it, selected, selecting, onToggleItem }: { it: BoardEntry; selected: boolean; selecting: boolean; onToggleItem: (item_id: string) => void }) {
  if (it.kind === 'checklist') {
    const L = it.items.length, d = it.items.filter((x) => x.done).length, rows = ordered(it);
    return (
      <View style={st.cardWrap} pointerEvents="box-none">
        <View style={[st.ckCard, selected && st.selRing]} pointerEvents="box-none">
          <View style={st.ckHead}>
            <View style={st.ckIcon}><MobileIcon name="check" size={13} color={CK.deep} strokeWidth={2.4} /></View>
            <Text style={st.ckTitle} numberOfLines={1}>{it.title}</Text>
            <Text style={st.ckNum}>{d}/{L}</Text>
          </View>
          {L === 0 ? <Text style={st.ckMore}>확인할 일을 추가해 보세요</Text> : (
            <View style={st.ckRows} pointerEvents="box-none">
              {rows.slice(0, 3).map((x) => (
                <Pressable key={x.id} style={st.ckRow} onPress={() => onToggleItem(x.id)} hitSlop={{ top: 3, bottom: 3 }} accessibilityRole="checkbox" accessibilityState={{ checked: x.done }}>
                  <InkCheck checked={x.done} color={CK.check} lineColor={CK.boxLine} size={17} radius={9} burst />
                  <Text style={[st.ckText, x.done && st.ckTextDone]} numberOfLines={1}>{x.text}</Text>
                </Pressable>
              ))}
              {L > 3 && <Text style={st.ckMore}>+{L - 3}개 더</Text>}
            </View>
          )}
        </View>
        {it.pinned && <Tape color={CK.tape} />}
        {selecting && <View style={st.selMark}><InkCheck checked={selected} color={C.accent} lineColor={C.white} bg={C.selMarkBg} size={24} radius={12} /></View>}
      </View>
    );
  }
  const p = MEMO_PAPER[it.color];
  return (
    <View style={st.cardWrap} pointerEvents="box-none">
      <View style={[st.memoCard, { backgroundColor: p.bg }, selected && st.selRing]}>
        <View style={st.dateRow}>
          <Text style={st.date}>{dateLabel(it)}</Text>
          <PopWhen show={it.ai_linked} style={st.plug}><MobileIcon name="plug" size={12} color={C.text} /></PopWhen>
        </View>
        <Text style={st.memoTitle} numberOfLines={2}>{it.title}</Text>
        <Text style={st.memoBody} numberOfLines={3}>{it.body.replace(/\n/g, ' ')}</Text>
        <Fold color={p.fold} />
      </View>
      {it.pinned && <Tape color={p.fold} />}
      <PopWhen show={it.unread_updates > 0} replay={it.unread_updates} style={st.badge}><Text style={st.badgeText}>{it.unread_updates}</Text></PopWhen>
      {selecting && <View style={st.selMark}><InkCheck checked={selected} color={C.accent} lineColor={C.white} bg={C.selMarkBg} size={24} radius={12} /></View>}
    </View>
  );
}

function ListFace({ it, selected, selecting }: { it: BoardEntry; selected: boolean; selecting: boolean }) {
  const isCk = it.kind === 'checklist';
  const unread = it.kind === 'memo' ? it.unread_updates : 0;
  const sub = isCk
    ? (it.items.length ? `${it.items.filter((x) => x.done).length}/${it.items.length} 완료 · ${it.items.find((x) => !x.done)?.text ?? '모두 끝냈어요'}` : '확인할 일을 추가해 보세요')
    : `${dateLabel(it).slice(0, 5)}  ${it.body.replace(/\n/g, ' ')}`;
  return (
    <View style={[st.row, unread > 0 && st.rowNew, selected && st.rowSel]}>
      {unread > 0 && <View style={st.rowBar} />}
      {selecting && <Appear kind="pin" dx={-12}><InkCheck checked={selected} color={C.accent} lineColor={C.chipLine} bg={C.white} size={24} radius={12} /></Appear>}
      {isCk ? (
        <View style={st.ckIconBig}><MobileIcon name="check" size={18} color={CK.deep} strokeWidth={2.4} /></View>
      ) : (
        <View style={[st.mini, { backgroundColor: MEMO_PAPER[it.color].bg }]}><Fold color={MEMO_PAPER[it.color].fold} size={10} /></View>
      )}
      <View style={st.rowText}>
        <View style={st.rowTitleLine}>
          {it.pinned && <MobileIcon name="pin" size={14} color={C.sub} />}
          <Text style={st.rowTitle} numberOfLines={1}>{it.title}</Text>
        </View>
        <View style={st.rowTitleLine}>
          {it.kind === 'memo' && it.ai_linked && <MobileIcon name="plug" size={10} color={C.text} />}
          <Text style={st.rowSub} numberOfLines={1}>{sub}</Text>
        </View>
      </View>
      <PopWhen show={unread > 0} replay={unread} style={st.rowBadge}><Text style={st.badgeText}>{unread}</Text></PopWhen>
    </View>
  );
}

function SelBtn({ icon, label, onPress, disabled, danger }: { icon: MobileIconName; label: string; onPress: () => void; disabled?: boolean; danger?: boolean }) {
  const col = disabled ? C.muted : danger ? C.red : C.text;
  const p = usePressScale(0.9);
  return (
    <Pressable style={st.selBtn} onPress={onPress} onPressIn={p.onPressIn} onPressOut={p.onPressOut} disabled={disabled} accessibilityRole="button" accessibilityState={{ disabled }}>
      <Animated.View style={{ alignItems: 'center', gap: 4, transform: [{ scale: p.scale }] }}>
        <MobileIcon name={icon} size={22} color={col} strokeWidth={1.8} />
        <Text style={[st.selBtnText, { color: col }]}>{label}</Text>
      </Animated.View>
    </Pressable>
  );
}

/** 색 동그라미: 누르면 .85배로 눌렸다 spring (체험판 .cdot .4s spring) */
function Swatch({ color, onPress }: { color: MemoColor; onPress: () => void }) {
  const p = usePressScale(0.85);
  return (
    <Pressable onPress={onPress} onPressIn={p.onPressIn} onPressOut={p.onPressOut} accessibilityRole="button" accessibilityLabel={color} hitSlop={4}>
      <Animated.View style={[st.swatch, { backgroundColor: MEMO_PAPER[color].bg, borderColor: MEMO_PAPER[color].fold, transform: [{ scale: p.scale }] }]} />
    </Pressable>
  );
}

function EmptyBoard({ examples, onExample, onFirst }: { examples: string[]; onExample: (t: string) => void; onFirst: () => void }) {
  return (
    <Appear kind="rise" style={st.empty}>
      <Appear kind="scale"><View style={st.emptyPaper}><Fold color={MEMO_PAPER.yellow.fold} size={20} /></View></Appear>
      <Text style={st.emptyTitle}>투자가 막연하세요?</Text>
      <Text style={st.emptyText}>떠오른 생각 한 줄부터 적어 보세요.{'\n'}AI 연결을 켜 두면 관련 공시·뉴스를 대신 확인해 드려요.</Text>
      <View style={st.exRow}>
        {examples.map((t, i) => (
          <Appear key={t} kind="pop" index={i + 1}>
            <Pressable style={st.exChip} onPress={() => onExample(t)} accessibilityRole="button"><Text style={st.exText}>{t}</Text></Pressable>
          </Appear>
        ))}
      </View>
      <Pressable style={st.firstBtn} onPress={onFirst} accessibilityRole="button"><Text style={st.firstText}>첫 메모 쓰기</Text></Pressable>
    </Appear>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.card },
  flex: { flex: 1 },
  scroll: { paddingTop: 8, paddingBottom: 140 },
  mh: { fontSize: 20, fontWeight: '800', color: C.text, paddingHorizontal: PAD, marginTop: 22 },
  mhNum: { color: C.text },
  frow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: PAD, marginTop: 6, marginBottom: 6, minHeight: 44 },
  chip: { height: 32, paddingHorizontal: 12, borderRadius: R.chip, borderWidth: 1, borderColor: C.chipLine, gap: 5 },
  chipOn: { borderColor: C.accent },
  chipPill: { backgroundColor: C.accent, borderRadius: R.chip },
  chipDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: C.red },
  chipDotOn: { backgroundColor: C.white },
  chipText: { fontSize: 13.5, color: C.sub },
  chipTextOn: { color: C.white, fontWeight: '700' },
  vt: { backgroundColor: C.appBg, borderRadius: 10, padding: 3 },
  vtBtn: { width: 34, height: 30 },
  vtKnob: { backgroundColor: C.vtKnob, borderRadius: 8, shadowColor: C.shadow, shadowOpacity: 0.1, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  skGrid: { flexDirection: 'row', paddingHorizontal: PAD, gap: GAP, marginTop: 4 },
  skCol: { flex: 1, gap: 16 },
  skel: { height: CARD_H, borderRadius: R.memo },
  cardWrap: { flex: 1 },
  memoCard: { flex: 1, borderRadius: R.memo, paddingHorizontal: 14, paddingTop: 12, overflow: 'hidden' },
  selRing: { borderWidth: 2, borderColor: C.accent },
  flash: { borderWidth: 2.5, borderColor: C.accent },
  dateRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 22 },
  date: { fontSize: 12, color: C.sub },
  plug: { width: 22, height: 22, borderRadius: 11, backgroundColor: C.card, alignItems: 'center', justifyContent: 'center' },
  memoTitle: { fontSize: 15, fontWeight: '800', color: C.text, lineHeight: 20, marginTop: 6, marginBottom: 6 },
  memoBody: { fontSize: 12.5, color: C.body, lineHeight: 18.5 },
  fold: { position: 'absolute', right: 0, bottom: 0 },
  tape: { position: 'absolute', top: -8, alignSelf: 'center', transform: [{ rotate: '-3deg' }] },
  badge: { position: 'absolute', top: -7, right: -7, minWidth: 22, height: 22, borderRadius: 11, backgroundColor: C.red, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: C.card, paddingHorizontal: 4 },
  badgeText: { color: C.white, fontSize: 12, fontWeight: '700' },
  ckCard: { flex: 1, borderRadius: R.memo, backgroundColor: CK.paper, paddingHorizontal: 14, paddingTop: 12 },
  ckHead: { flexDirection: 'row', alignItems: 'center', gap: 6, height: 22 },
  ckIcon: { width: 22, height: 22, borderRadius: 7, backgroundColor: CK.iconBg, alignItems: 'center', justifyContent: 'center' },
  ckIconBig: { width: 36, height: 36, borderRadius: 11, backgroundColor: CK.iconBg, alignItems: 'center', justifyContent: 'center' },
  ckTitle: { flex: 1, fontSize: 14, fontWeight: '800', color: C.text },
  ckNum: { fontSize: 12, fontWeight: '700', color: CK.deep },
  ckRows: { marginTop: 8, gap: 2 },
  ckRow: { flexDirection: 'row', alignItems: 'center', gap: 7, minHeight: 24 },
  ckText: { flex: 1, fontSize: 12.5, color: C.text },
  ckTextDone: { color: CK.doneText, textDecorationLine: 'line-through' },
  ckMore: { fontSize: 11.5, fontWeight: '600', color: CK.more, paddingLeft: 24, marginTop: 4 },
  row: { flex: 1, flexDirection: 'row', alignItems: 'center', paddingHorizontal: PAD + 4, gap: 12, borderBottomWidth: 1, borderBottomColor: C.line, backgroundColor: C.card },
  rowNew: { backgroundColor: C.redSoft },
  rowSel: { backgroundColor: C.accentSoft },
  rowBar: { position: 'absolute', left: 0, top: 0, bottom: 0, width: 4, backgroundColor: C.red },
  mini: { width: 30, height: 32, borderRadius: 5, overflow: 'hidden' },
  rowText: { flex: 1, minWidth: 0 },
  rowTitleLine: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  rowTitle: { flex: 1, fontSize: 15.5, fontWeight: '800', color: C.text },
  rowSub: { flex: 1, fontSize: 12.5, color: C.sub, marginTop: 2 },
  rowBadge: { minWidth: 24, height: 24, borderRadius: 12, backgroundColor: C.red, alignItems: 'center', justifyContent: 'center' },
  selMark: { position: 'absolute', top: 8, right: 8 },
  selHead: { position: 'absolute', top: 0, left: 0, right: 0, zIndex: 5, flexDirection: 'row', alignItems: 'center', height: 56, paddingHorizontal: 6, backgroundColor: C.card, borderBottomWidth: 1, borderBottomColor: C.line },
  selCount: { flex: 1, fontSize: 17, fontWeight: '800', color: C.text },
  selAll: { fontSize: 15, fontWeight: '700', color: C.accentDeep },
  iconBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  textBtn: { minHeight: 44, paddingHorizontal: 12, justifyContent: 'center' },
  selBar: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 80, flexDirection: 'row', backgroundColor: C.card, borderTopWidth: 1, borderTopColor: C.line, paddingTop: 8, zIndex: 6 },
  selBtn: { flex: 1, alignItems: 'center', minHeight: 44 },
  selBtnText: { fontSize: 12 },
  sheetTitle: { fontSize: 17, fontWeight: '800', color: C.text, marginBottom: 16 },
  swatches: { flexDirection: 'row', justifyContent: 'space-between', paddingBottom: 8 },
  swatch: { width: 48, height: 48, borderRadius: 24, borderWidth: 2 },
  empty: { alignItems: 'center', paddingHorizontal: 14, paddingTop: 36 },
  emptyPaper: { width: 56, height: 56, borderRadius: 14, backgroundColor: MEMO_PAPER.yellow.bg, marginBottom: 14, overflow: 'hidden' },
  emptyTitle: { fontSize: 20, fontWeight: '800', color: C.text },
  emptyText: { fontSize: 14, lineHeight: 23, color: C.sub, textAlign: 'center', marginTop: 8, marginBottom: 16 },
  exRow: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 6, marginBottom: 18 },
  exChip: { height: 38, paddingHorizontal: 13, borderRadius: 19, borderWidth: 1, borderColor: C.chipLine, justifyContent: 'center' },
  exText: { fontSize: 13.5, color: C.text },
  firstBtn: { height: 48, paddingHorizontal: 24, borderRadius: 14, backgroundColor: C.dark, justifyContent: 'center' },
  firstText: { fontSize: 15.5, fontWeight: '800', color: C.white },
});
