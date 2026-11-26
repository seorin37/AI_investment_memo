import React, { useEffect, useMemo, useRef, useState } from 'react';
import { BackHandler, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { MiniSpace, useMiniSpace } from '@/ui/screens/studio/app/MiniBar';
import { useBottomBarTop } from '@/ui/shared/app/BottomBar';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import type { Checklist, Memo, MemoColor } from '@/types/models';
import { Confetti } from '@/components/motion/Celebrate';
import { FadeIn } from '@/ui/motion/Reveal';
import { AppChecklistCard, AppChecklistRow } from '@/ui/shared/ChecklistCard';
import { AppChips } from '@/ui/shared/Chips';
import { FabFan } from '@/ui/shared/FabFan';
import { AppMemoCard } from './MemoCard';
import { AppMemoRow } from '@/ui/shared/MemoRow';
import { StockTabs } from './StockTabs';
import { AppSelectBar, AppSelectHeader, type AppSelAction } from '@/ui/shared/SelectBar';
import { Sheet } from '@/ui/shared/Sheet';
import { AppSnackbar } from '@/ui/shared/Snackbar';
import { SpentBox } from '@/ui/shared/SpentBox';
import { SwipeRow } from '@/ui/shared/SwipeRow';
import { AppViewToggle, type BoardView } from '@/ui/shared/ViewToggle';
import { nf } from '@/ui/shared/app/nf';
import { appColor, ft } from '@/ui/theme';
import { arrange } from '../boardCards';
import { SortCards } from './SortCards';
import type { BoardFilter, AppMemoBoardProps } from '../MemoBoard.types';
import { usePaper } from '@/ui/shared/Dark';

type Item = { key: string; memo?: Memo; checklist?: Checklist; pinned: boolean };
type Snack = { id: number; msg: string; undo?: string[] };

/* 원본 C 순서: 노랑 · 초록 · 파랑 · 보라 · 분홍 */
const COLORS: MemoColor[] = ['yellow', 'green', 'blue', 'purple', 'pink'];
/* 원본 빈 보드 예시 칩 */
const EXAMPLES = ['실적 나오면 다시 보기', '많이 빠지면 다시 생각해 보기', '요즘 분위기 좋아 보여'];

/**
 * 앱 메모 보드 (원본 memo.html 의 보드 부분)
 * 위에서부터: 종목 카드 (위 6 · 좌우 16) · [메모 보드 | 기업정보] (위 16) · '내 메모 N' 19px 800 (위 20 · 아래 10)
 * · (사용량 소진 안내) · 칩 줄 + 2열/목록 전환 (좌우 16 · 아래 14 · 사이 6) · 카드 (아래 120)
 * 2열: 왼쪽 16 · 칸 사이 12 · 줄 166 (카드 150 + 16) · 카드 폭 (화면폭 - 44) / 2 → 412 에서 184
 * 목록: 줄 64 · 줄 밀기 (메모만) · 꾹 눌러 고르기 → 머리·막대 바뀜 (탭바는 부모가 숨김)
 * 순서: 고정 먼저(맨 위 고정 구역) → 저장된 순서. 일반 카드는 꾹 눌러 끌어서 바꿈 (전체 보기에서, SortCards). 웹과 같은 순서.
 * header: 평소 상단 바 (라우트가 줌). 고르는 동안은 'N개 선택' 머리로 바꿔 끼움.
 */
export function AppMemoBoard(p: AppMemoBoardProps & { header: React.ReactNode; topCard: React.ReactNode; startY?: number; onScrollY?: (y: number) => void }) {
  const paper = usePaper();
  const { width: W } = useWindowDimensions();
  const cw = (W - 44) / 2;
  const [filter, setFilter] = useState<BoardFilter>('all');
  const [view, setView] = useState<BoardView>('grid');
  const [sel, setSel] = useState<string[] | null>(null);
  const [openRow, setOpenRow] = useState<string | null>(null);
  const [fan, setFan] = useState(false);
  const [colorFor, setColorFor] = useState<string[] | null>(null);
  const [snack, setSnack] = useState<Snack | null>(null);

  const items: Item[] = useMemo(() => {
    const ms: Item[] = p.memos
      .filter((m) => filter === 'all' || (filter === 'ai' ? m.ai_linked : m.unread_updates > 0))
      .map((m) => ({ key: m.id, memo: m, pinned: m.pinned }));
    const cl: Item[] = filter === 'all' ? p.checklists.map((c) => ({ key: c.id, checklist: c, pinned: !!c.pinned })) : [];
    const rank = new Map(arrange({ memos: p.memos, checklists: p.checklists, order: p.order }).map((id, i) => [id, i]));
    return [...ms, ...cl].sort((a, b) => (rank.get(a.key) ?? 0) - (rank.get(b.key) ?? 0));
  }, [p.memos, p.checklists, p.order, filter]);
  /* 끌어 옮기기: 스크롤 잠금 · 위치 */
  const [locked, setLocked] = useState(false);
  const scroll = useRef<React.ComponentRef<typeof ScrollView>>(null);
  const viewport = useRef<React.ComponentRef<typeof View>>(null);
  const scrollY = useRef(0);
  const placed = useRef(false);

  const memoCount = p.memos.length;
  const newTotal = p.memos.reduce((n, m) => n + m.unread_updates, 0);
  const empty = memoCount === 0 && p.checklists.length === 0;
  const selecting = sel !== null;

  /* 탭바 숨김을 부모에 알림 */
  const onSel = p.onSelectionChange;
  useEffect(() => {
    onSel?.(sel ? sel.length : 0);
  }, [sel, onSel]);

  /* 스낵바: 되돌리기는 5초, 그 밖에는 2.4초 */
  useEffect(() => {
    if (!snack) return;
    const t = setTimeout(() => setSnack((s) => (s && s.id === snack.id ? null : s)), snack.undo ? 5000 : 2400);
    return () => clearTimeout(t);
  }, [snack]);
  const toast = (msg: string, undo?: string[]) => setSnack((s) => ({ id: (s?.id ?? 0) + 1, msg, undo }));
  /* 축하: 화면 안 자리로 바꿔 색종이 · 스낵바 */
  const rootRef = useRef<React.ComponentRef<typeof View>>(null);
  const [cf, setCf] = useState<{ x: number; y: number; id: number } | null>(null);
  const celebrate = (c: { x: number; y: number }) =>
    rootRef.current?.measureInWindow((rx, ry) => {
      setCf((o) => ({ x: c.x - rx, y: c.y - ry, id: (o?.id ?? 0) + 1 }));
      toast('체크리스트를 모두 끝냈어요');
    });
  /* 돌아올 때 받은 알림 (새 메모 저장 · 빈 메모) */
  const [noticeKey, setNoticeKey] = useState(p.notice?.key);
  if (p.notice && p.notice.key !== noticeKey) {
    setNoticeKey(p.notice.key);
    toast(p.notice.message, p.notice.undo);
  }

  /* 안드로이드 뒤로: 시트(모달이 먼저 받음) → 열린 줄 → 부채꼴 → 고르기 → 화면 */
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (openRow) {
        setOpenRow(null);
        return true;
      }
      if (fan) {
        setFan(false);
        return true;
      }
      if (sel) {
        setSel(null);
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [openRow, fan, sel]);

  const byId = (id: string) => p.memos.find((m) => m.id === id);
  const isCk = (id: string) => p.checklists.some((c) => c.id === id);
  const enterSel = (key: string) => {
    setOpenRow(null);
    setSel([key]);
  };
  const toggleSel = (key: string) =>
    setSel((s) => {
      const cur = s ?? [];
      const next = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key];
      return next.length ? next : null;
    });
  const tap = (it: Item) => {
    if (sel) return toggleSel(it.key);
    if (openRow) return setOpenRow(null);
    if (it.checklist) return p.onOpenChecklist(it.key);
    const m = it.memo!;
    p.onOpenMemo(m.id, m.unread_updates > 0 && m.ai_linked ? 'ai' : 'memo');
  };

  /* 고르기 막대 */
  const one = sel?.length === 1;
  const hasCk = (sel ?? []).some(isCk);
  /* 원본 togglePin: 체크리스트도 메모처럼 고정 (③ 결정) */
  const allPinned = (sel ?? []).length > 0 && (sel ?? []).every((k) => (byId(k) ?? p.checklists.find((c) => c.id === k))?.pinned);
  const onAction = (a: AppSelAction) => {
    const ids = sel ?? [];
    if (a === 'pin') {
      p.onPin(ids, !allPinned);
      const n = ids.length;
      setSel(null);
      if (n === 1 && hasCk) toast(allPinned ? '고정을 풀었어요' : '체크리스트를 고정했어요');
      else toast(allPinned ? `${n}개 고정을 풀었어요` : `${n}개를 고정했어요`);
    } else if (a === 'color') setColorFor(ids);
    else if (a === 'ai') {
      setSel(null);
      p.onToggleAi(ids[0]);
    } else if (a === 'copy') {
      setSel(null);
      p.onCopy(ids);
      toast('내용을 복사했어요');
    } else {
      setSel(null);
      p.onDelete(ids);
      const what = ids.every(isCk) ? '체크리스트' : hasCk ? '' : '메모';
      toast(ids.length > 1 ? `${what ? `${what} ` : ''}${ids.length}개를 휴지통으로 옮겼어요` : `${what || '메모'}를 휴지통으로 옮겼어요`, ids);
    }
  };
  const pickColor = (c: MemoColor) => {
    if (!colorFor) return;
    p.onChangeColor(colorFor, c);
    setTimeout(() => {
      setColorFor(null);
      setSel(null);
    }, 260);
  };
  const colorNow = colorFor && colorFor.every((id) => byId(id)?.color === byId(colorFor[0])?.color) ? byId(colorFor[0])?.color : null;

  const miniSpace = useMiniSpace();
  const { bottom: insetB } = useSafeAreaInsets();
  useBottomBarTop(selecting ? 66 + Math.max(14, insetB) : 0);
  return (
    <View ref={rootRef} collapsable={false} style={st.root}>
      {sel ? <AppSelectHeader count={sel.length} allSelected={sel.length === items.length} onClose={() => setSel(null)} onToggleAll={() => setSel(sel.length === items.length ? null : items.map((i) => i.key))} /> : p.header}
      <View ref={viewport} collapsable={false} style={st.flex}>
      <ScrollView ref={scroll} style={st.flex} scrollEnabled={!locked} onScroll={(e) => { scrollY.current = e.nativeEvent.contentOffset.y; p.onScrollY?.(scrollY.current); }} onContentSizeChange={() => { if (!placed.current && p.startY) scroll.current?.scrollTo({ y: p.startY, animated: false }); placed.current = true; }} scrollEventThrottle={16} contentContainerStyle={st.content} showsVerticalScrollIndicator={false} onScrollBeginDrag={() => openRow && setOpenRow(null)}>
        {p.topCard}
        <View style={st.seg}>
          {/* 기업정보 탭과 같은 탭 버튼 */}
          <StockTabs value="board" onChange={p.onChangeTab} />
        </View>
        <Text style={st.mh}>내 메모 {memoCount}</Text>
        {p.aiSpent ? (
          <View style={st.spb}>
            <SpentBox variant="app" title="AI 사용량을 다 썼어요" body={p.aiCount ? `충전하거나 플랜을 업그레이드하지 않으면 AI 연결 메모 ${p.aiCount}개가 모두 꺼져요.\n메모는 계속 쓸 수 있어요.` : `${p.aiRefill && p.aiRefill !== '—' ? p.aiRefill : '다음 갱신일'}에 새로 채워져요.\n그때까지 새 메모는 일반 메모로 저장돼요.`} onCredit={() => p.onSpentAction?.('credit')} onPlan={() => p.onSpentAction?.('plan')} onOff={p.aiCount ? () => p.onSpentAction?.('choice') : undefined} />
          </View>
        ) : null}
        <View style={st.frow}>
          <AppChips
            value={filter}
            onChange={(f) => {
              setSel(null);
              setOpenRow(null);
              setFilter(f);
            }}
            options={[{ key: 'all', label: '전체' }, { key: 'ai', label: 'AI 연결' }, ...(newTotal ? [{ key: 'new' as const, label: '새 소식', count: newTotal, dot: true }] : [])]}
          />
          <View style={st.vt}>
            <AppViewToggle
              value={view}
              onChange={(v) => {
                setOpenRow(null);
                setView(v);
              }}
            />
          </View>
        </View>
        {empty ? (
          <EmptyBoard onExample={(t) => p.onNewMemo(t)} onFirst={() => p.onNewMemo()} onChecklist={p.onNewChecklist} />
        ) : (
          <FadeIn key={`${view}-${filter}`}>
            <View style={view === 'grid' ? st.grid : st.list}>
              <SortCards
                keys={items.map((it) => it.key)}
                pinCount={items.filter((it) => it.pinned).length}
                layout={view === 'grid' ? { cols: 2, w: cw, h: 150, gx: 12, gy: 16, radius: 16 } : { cols: 1, w: W, h: 64, gx: 0, gy: 0, radius: 0 }}
                enabled={filter === 'all' && !selecting && !openRow}
                scroll={scroll}
                viewport={viewport}
                scrollY={scrollY}
                onLock={setLocked}
                onHold={enterSel}
                onDrop={p.onReorder}
                renderCard={(key, hold) => {
                  const it = items.find((x) => x.key === key)!;
                  const own = { selecting, selected: !!sel?.includes(key), onPress: () => tap(it), ...hold };
                  if (view === 'grid')
                    return it.checklist ? (
                      <AppChecklistCard checklist={it.checklist} onAllDone={celebrate} width={cw} height={150} {...own} onToggleItem={(iid) => p.onToggleChecklistItem(key, iid)} />
                    ) : (
                      <AppMemoCard memo={it.memo!} width={cw} height={150} aiSpent={p.aiSpent} {...own} />
                    );
                  if (it.checklist) return <AppChecklistRow checklist={it.checklist} width={W} {...own} />;
                  const m = it.memo!;
                  return (
                    <SwipeRow
                      enabled={!selecting && !locked}
                      open={openRow === key}
                      onOpenChange={(o) => setOpenRow(o ? key : openRow === key ? null : openRow)}
                      pinLabel={m.pinned ? '고정 해제' : '고정'}
                      onPin={() => {
                        p.onPin([key], !m.pinned);
                        toast(m.pinned ? '고정을 풀었어요' : '메모를 고정했어요');
                      }}
                      aiLabel={m.ai_linked ? 'AI 끄기' : 'AI 연결'}
                      onAi={() => {
                        setOpenRow(null);
                        p.onToggleAi(key);
                      }}
                      onDelete={() => {
                        setOpenRow(null);
                        p.onDelete([key]);
                        toast('메모를 휴지통으로 옮겼어요', [key]);
                      }}
                    >
                      <AppMemoRow memo={m} width={W} {...own} />
                    </SwipeRow>
                  );
                }}
              />
              {view === 'grid' && filter === 'all' && !p.checklists.length && !selecting ? (
                <Pressable onPress={p.onNewChecklist} accessibilityRole="button" style={({ pressed }) => [st.newCl, { width: cw }, pressed && { backgroundColor: '#E9EAEE' }]}>
                  <Svg width={16} height={16} viewBox="0 0 16 16" fill="none">
                    <Path d="M8 3V13M3 8H13" stroke="#6B7684" strokeWidth={1.6} strokeLinecap="round" />
                  </Svg>
                  <Text style={st.newClT}>체크리스트 만들기</Text>
                </Pressable>
              ) : null}
            </View>
          </FadeIn>
        )}
        <View style={st.bottom} />
        <MiniSpace />
      </ScrollView>
      </View>
      {!selecting ? (
        <View pointerEvents="box-none" style={[StyleSheet.absoluteFill, { bottom: miniSpace }]}>
        <FabFan
          open={fan}
          onToggle={setFan}
          up={!!snack}
          onPick={(k) => (k === 'check' ? p.onNewChecklist() : p.onNewMemo())}
        />
        </View>
      ) : null}
      {/* 체크리스트를 모두 끝내면 카드 가운데서 색종이 (원본 memo.html confetti · Lucian #093) */}
      <Confetti fire={cf} />
      <AppSnackbar
        visible={!!snack}
        message={snack?.msg ?? ''}
        onUndo={
          snack?.undo
            ? () => {
                p.onUndoDelete(snack.undo!);
                setSnack(null);
              }
            : undefined
        }
        style={[st.snack, { bottom: 14 + miniSpace }]}
      />
      <AppSelectBar
        visible={selecting}
        pinLabel={allPinned ? '고정 해제' : '고정'}
        aiLabel={one && !hasCk && byId(sel![0])?.ai_linked ? 'AI 끄기' : 'AI 연결'}
        disabled={{ pin: false, ai: !one || hasCk, color: hasCk, copy: !one || hasCk }}
        onAction={onAction}
      />
      <Sheet open={!!colorFor} onClose={() => setColorFor(null)} title={colorFor && colorFor.length > 1 ? `${colorFor.length}개 메모 색상` : '메모 색상'} label="메모 색상">
        <View style={st.colors}>
          {COLORS.map((c) => (
            <Pressable key={c} onPress={() => pickColor(c)} accessibilityRole="button" accessibilityLabel={paper[c].label} style={[st.cdotRing, colorNow === c && { borderColor: paper[c].accent }]}>
              <View style={[st.cdot, { backgroundColor: paper[c].bg }]} />
            </Pressable>
          ))}
        </View>
      </Sheet>
    </View>
  );
}

/**
 * 빈 보드 (원본 .bempty: 좌우 14 · 메모지 그림 56 (라운드 14 14 4 14 · 접힌 24) · '투자가 막연하세요?' 20px 800
 * 설명 14px 줄 1.65 #6B7684 (위 8 · 아래 16) · 예시 칩 38 라운드 19 13.5px 500 (사이 6 · 아래 18) · [첫 메모 쓰기] 48 라운드 14 15.5px 800)
 */
function EmptyBoard({ onExample, onFirst, onChecklist }: { onExample: (t: string) => void; onFirst: () => void; onChecklist: () => void }) {
  return (
    <FadeIn style={st.empty}>
      <Svg width={56} height={56} viewBox="0 0 56 56" style={st.bic}>
        {/* 종이: 오른쪽 아래 62% 지점에서 잘림 */}
        <Path d="M14 0H42A14 14 0 0 1 56 14V34.72L34.72 56H14A14 14 0 0 1 0 42V14A14 14 0 0 1 14 0Z" fill="#FCEAAA" />
        <Path d="M32 38A6 6 0 0 1 38 32H56L32 56Z" fill="#EFBF2A" />
      </Svg>
      <Text style={st.eT}>투자가 막연하세요?</Text>
      <Text style={st.eP}>{'떠오른 생각 한 줄부터 적어 보세요.\nAI 연결을 켜 두면 관련 공시·뉴스를 대신 확인해 드려요.'}</Text>
      <View style={st.bch}>
        {EXAMPLES.map((t) => (
          <Pressable key={t} onPress={() => onExample(t)} accessibilityRole="button" style={({ pressed }) => [st.ex, pressed && { backgroundColor: '#F6F7F9' }]}>
            <Text style={st.exT}>{t}</Text>
          </Pressable>
        ))}
      </View>
      <Pressable onPress={onFirst} accessibilityRole="button" style={st.go}>
        <Text style={st.goT}>첫 메모 쓰기</Text>
      </Pressable>
      <Pressable onPress={onChecklist} accessibilityRole="button" style={[st.go, st.goCl]}>
        <Text style={[st.goT, { color: appColor.ink }]}>체크리스트 만들기</Text>
      </Pressable>
    </FadeIn>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: appColor.bg },
  flex: { flex: 1 },
  content: { paddingBottom: 0 },
  seg: { marginTop: 16, marginHorizontal: 16 },
  mh: { ...nf(19), fontWeight: '800', color: appColor.ink, marginTop: 20, marginHorizontal: 16, marginBottom: 10 },
  spb: { marginTop: 2, marginHorizontal: 16, marginBottom: 12 },
  frow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingBottom: 14 },
  vt: { marginLeft: 'auto' },
  grid: { paddingHorizontal: 16, paddingTop: 10 },
  list: {},
  bottom: { height: 120 },
  snack: { position: 'absolute', left: 14, right: 14, bottom: 14 },
  colors: { flexDirection: 'row', gap: 16, paddingTop: 16, paddingHorizontal: 22, paddingBottom: 10 },
  /* 원본 .cdot.on: 0 0 0 2px #fff, 0 0 0 4px 접힌 색 */
  cdotRing: { width: 42, height: 42, borderRadius: 21, borderWidth: 2, borderColor: 'transparent', alignItems: 'center', justifyContent: 'center', margin: -4 },
  cdot: { width: 34, height: 34, borderRadius: 17, borderWidth: 1, borderColor: 'rgba(0,0,0,0.07)' },
  empty: { alignItems: 'center', paddingHorizontal: 14, marginTop: 20 },
  bic: { marginBottom: 14 },
  eT: { ...ft(20), fontWeight: '800', color: appColor.ink, textAlign: 'center' },
  eP: { ...ft(14, 1.65), color: '#6B7684', textAlign: 'center', marginTop: 8, marginBottom: 16 },
  bch: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 6, marginBottom: 18 },
  ex: { minHeight: 38, borderRadius: 19, paddingHorizontal: 13, paddingVertical: 9, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E5E7EB', justifyContent: 'center' },
  exT: { ...ft(13.5), fontWeight: '500', color: appColor.ink },
  go: { minHeight: 48, borderRadius: 14, paddingHorizontal: 24, paddingVertical: 13, backgroundColor: appColor.ink, justifyContent: 'center' },
  goCl: { backgroundColor: '#E3E5EA', marginTop: 8 },
  newCl: { height: 72, marginTop: 16, borderRadius: 16, borderWidth: 1, borderStyle: 'dashed', borderColor: '#D8DBE0', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  newClT: { ...ft(14), fontWeight: '500', color: '#6B7684' },
  goT: { ...ft(15.5), fontWeight: '800', color: '#FFFFFF' },
});
