import React, { useEffect, useRef, useState } from 'react';
import { Animated, BackHandler, Keyboard, Pressable, ScrollView, StyleSheet, View, type TextInputInstance } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text, TextInput } from '@/components/ui/AppText';
import { Reveal } from '@/ui/motion/Reveal';
import { Skeleton } from '@/ui/motion/Skeleton';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { Sheet } from '@/ui/shared/Sheet';
import { AppSnackbar } from '@/ui/shared/Snackbar';
import { SwipeRow } from '@/ui/shared/SwipeRow';
import { Toggle } from '@/ui/shared/Toggle';
import { appColor, curve, ft } from '@/ui/theme';
import { mockJournalLoadMs, mockJournalRecentCount } from '../Journal.mock';
import type { JournalFlash } from '@/store/journal';
import type { JournalEntry, JournalProps } from '../Journal.types';
import { appTitle, groupJournal, preview, searchJournal, splitHit } from '../journalParts';
import { JBarIcon, JCheck, JChevron, JClose, JCompose, JEmptyDoc, JMic, JNoHit, JPlus, JSearch } from './journalGlyphs';

const A2 = appColor.tabPurple;
const SEP = '#ECEDF1';
const NOT_YET = '아직 연결되지 않았어요 · 데이터는 그대로예요';
type Snack = { id: number; msg: string; undo?: JournalEntry[] };
export type Toast = { id: number; msg: string };

export interface AppJournalProps extends JournalProps {
  /** 평소 상단 바 (라우트가 줌 · TopBar journal) — 검색 중엔 위로 접히고, 고르는 동안은 'N개 선택' 머리로 바뀜 */
  header: React.ReactNode;
  /** 보기 시트를 여는 신호 (머리 ⋯ 버튼이 라우트에 있어서 숫자를 올려 알림) */
  viewSheetSignal: number;
  /** 고르는 수 (탭바 숨김) */
  onSelectionChange: (n: number) => void;
  /** 라우트가 띄우는 알림 (머리 알림 버튼 등) — key 가 바뀌면 알약으로 */
  notice?: { key: number; message: string };
  /** 기록 화면에서 돌아올 때 (저장 알림 · 반짝임 · 휴지통) — 처리하면 onFlashDone */
  flash?: JournalFlash | null;
  onFlashDone?: () => void;
}

/**
 * 앱 투자 기록 목록 (원본 journal.html 14 목록)
 * 머리 60 · 검색 줄(위 2 · 좌우 16 · 아래 6 · 칸 40 라운드 12 #E6E8EC · 새 기록 42×40 #EDE8FB)
 * 묶음 머리 19px 800 (위 16 · 좌우 18 · 아래 8) · 흰 카드 라운드 14 (좌우 16) · 줄 (위아래 12 · 좌우 16 · 제목 16 800 · 둘째 줄 13.5)
 * 밀기: 오른쪽 고정 · 왼쪽 휴지통 88 / 꾹 480ms 고르기 → 머리·아래 막대 바뀜 / 아래 'N개의 기록' 46 (흐림 띠)
 * 검색칸을 누르면 머리가 위로 접히고 [취소] — 빈칸이면 최근 기록 3개, 글자를 넣으면 찾은 말 보라 굵게
 */
export function AppJournal(p: AppJournalProps) {
  const k = useMotionK();
  const insets = useSafeAreaInsets();
  const [loading, setLoading] = useState(true);
  const [grouping, setGrouping] = useState(true);
  const [sort, setSort] = useState<'edit' | 'make'>('edit');
  const [foldPin, setFoldPin] = useState(false);
  const [sel, setSel] = useState<string[] | null>(null);
  const [openRow, setOpenRow] = useState<string | null>(null);
  const [gone, setGone] = useState<string[]>([]);
  const [hl, setHl] = useState<{ id: string; n: number } | null>(null);
  const [srch, setSrch] = useState(false);
  const [q, setQ] = useState('');
  const [sheet, setSheet] = useState(false);
  const [snack, setSnack] = useState<Snack | null>(null);
  const [toastV, setToastV] = useState<Toast | null>(null);
  const [headH, setHeadH] = useState(0);
  const input = useRef<TextInputInstance>(null);
  const L = p.entries;

  /* 처음 들어올 때 뼈대 (원본 loadList 900ms) */
  useEffect(() => {
    const t = setTimeout(() => setLoading(false), mockJournalLoadMs * k);
    return () => clearTimeout(t);
  }, [k]);
  /* 머리 ⋯ → 보기 시트 */
  const [sig, setSig] = useState(p.viewSheetSignal);
  if (sig !== p.viewSheetSignal) {
    setSig(p.viewSheetSignal);
    setSheet(true);
  }
  const onSel = p.onSelectionChange;
  useEffect(() => {
    onSel(sel ? sel.length : 0);
  }, [sel, onSel]);
  useEffect(() => {
    if (!snack) return;
    const t = setTimeout(() => setSnack((s) => (s && s.id === snack.id ? null : s)), 5000);
    return () => clearTimeout(t);
  }, [snack]);
  useEffect(() => {
    if (!toastV) return;
    const t = setTimeout(() => setToastV((s) => (s && s.id === toastV.id ? null : s)), 2300 * k);
    return () => clearTimeout(t);
  }, [toastV, k]);
  const toast = (msg: string) => setToastV((s) => ({ id: (s?.id ?? 0) + 1, msg }));
  const notYet = () => toast(NOT_YET);
  const [noticeKey, setNoticeKey] = useState(p.notice?.key);
  if (p.notice && p.notice.key !== noticeKey) {
    setNoticeKey(p.notice.key);
    toast(p.notice.message);
  }

  /* 검색 접기 (원본 .srch: 머리 위로 60 · 투명 · 새 기록 버튼 접힘 · [취소] 나옴 .3s) */
  const [sv] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(sv, { toValue: srch ? 1 : 0, duration: 300 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [srch, sv, k]);
  const openSearch = () => {
    if (srch) return;
    setOpenRow(null);
    setSrch(true);
  };
  const closeSearch = () => {
    setSrch(false);
    setQ('');
    input.current?.blur();
    Keyboard.dismiss();
  };

  /* 안드로이드 뒤로: 시트(모달이 먼저) → 열린 줄 → 검색 → 고르기 → 화면 */
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (openRow) return setOpenRow(null), true;
      if (srch) return closeSearch(), true;
      if (sel) return setSel(null), true;
      return false;
    });
    return () => sub.remove();
  });

  const enterSel = (id: string) => {
    setOpenRow(null);
    setSel([id]);
  };
  const toggleSel = (id: string) =>
    setSel((s) => {
      const c = s ?? [];
      const n = c.includes(id) ? c.filter((x) => x !== id) : [...c, id];
      return n.length ? n : null;
    });
  const tap = (j: JournalEntry) => {
    if (openRow) return setOpenRow(null);
    if (sel) return toggleSel(j.id);
    p.onOpen(j.id);
  };
  const doPin = (ids: string[]) => {
    const all = ids.every((i) => L.find((j) => j.id === i)?.pinned);
    p.onPin(ids, !all);
    if (!all) setFoldPin(false);
    if (ids.length === 1) setHl((h) => ({ id: ids[0], n: (h?.n ?? 0) + 1 }));
    toast(all ? '고정을 풀었어요' : ids.length > 1 ? `${ids.length}개를 고정했어요` : '고정했어요');
  };
  /* 휴지통: 줄이 접히고(.26s) 목록에서 빠짐 → 되돌리기 5초 (영구 삭제 없음) */
  const trash = (ids: string[]) => {
    setOpenRow(null);
    setGone(ids);
    setTimeout(() => {
      const before = L;
      p.onTrash(ids);
      setGone([]);
      setSnack((s) => ({ id: (s?.id ?? 0) + 1, msg: `기록 ${ids.length}개를 휴지통으로 옮겼어요`, undo: before }));
    }, 260 * k);
  };
  /* 기록 화면에서 돌아옴 (원본 back: .3초 뒤 목록이 반짝 + '새 기록을 저장했어요' / 빈 새 기록 / 휴지통 + 되돌리기) */
  const fk = p.flash?.key;
  useEffect(() => {
    const f = p.flash;
    if (!f) return;
    const t = setTimeout(() => {
      if (f.kind === 'saved') {
        setHl((h) => ({ id: f.id, n: (h?.n ?? 0) + 1 }));
        if (f.isNew) toast('새 기록을 저장했어요');
      } else if (f.kind === 'empty') toast('빈 기록은 저장하지 않았어요');
      else trash([f.id]);
      p.onFlashDone?.();
    }, 320 * k);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fk]);
  const undo = () => {
    if (!snack?.undo) return;
    const ids = new Set(L.map((j) => j.id));
    const back = snack.undo.filter((j) => !ids.has(j.id));
    p.onRestore(snack.undo);
    setSnack(null);
    if (back.length === 1) setHl((h) => ({ id: back[0].id, n: (h?.n ?? 0) + 1 }));
  };

  const { pins, groups } = groupJournal(L, grouping, '모든 기록');
  const selecting = sel !== null;
  const allSel = !!sel && sel.length === L.length;
  const [selV] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(selV, { toValue: selecting ? 1 : 0, duration: 300 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [selecting, selV, k]);

  const row = (j: JournalEntry, i: number, swipe: boolean) => {
    const inner = <JRow j={j} first={i === 0} selV={selV} selecting={selecting} selected={!!sel?.includes(j.id)} hl={hl?.id === j.id ? hl.n : 0} onPress={() => tap(j)} onLongPress={swipe ? () => enterSel(j.id) : undefined} />;
    return (
      <Collapse key={j.id} gone={gone.includes(j.id)}>
        {swipe ? (
          <SwipeRow
            kind="journal"
            enabled={!selecting}
            open={openRow === j.id}
            onOpenChange={(o) => setOpenRow(o ? j.id : openRow === j.id ? null : openRow)}
            pinLabel={j.pinned ? '고정 해제' : '고정'}
            onPin={() => doPin([j.id])}
            onDelete={() => trash([j.id])}
          >
            {inner}
          </SwipeRow>
        ) : (
          inner
        )}
      </Collapse>
    );
  };

  const results = searchJournal(L, q);
  const sbW = sv.interpolate({ inputRange: [0, 1], outputRange: [42, 0] });

  return (
    <View style={st.root}>
      {/* 머리: 검색 중엔 위로 접힘 · 고르는 동안은 'N개 선택' */}
      {sel ? (
        <View style={{ paddingTop: insets.top, backgroundColor: appColor.bg }}>
          <View style={st.selh}>
            <Pressable onPress={() => setSel(null)} accessibilityRole="button" accessibilityLabel="선택 끝내기" style={({ pressed }) => [st.ib, pressed && { backgroundColor: '#E9EAEE' }]}>
              <JClose />
            </Pressable>
            <Text style={st.selhT}>{sel.length}개 선택</Text>
            <Pressable onPress={() => (allSel ? setSel(null) : setSel(L.map((j) => j.id)))} accessibilityRole="button" style={st.all}>
              <Text style={st.allT}>{allSel ? '전체 해제' : '전체 선택'}</Text>
            </Pressable>
          </View>
        </View>
      ) : (
        <Animated.View style={[st.headWrap, headH ? { height: sv.interpolate({ inputRange: [0, 1], outputRange: [headH, insets.top] }) } : null]}>
          <Animated.View onLayout={(e) => !headH && setHeadH(e.nativeEvent.layout.height)} style={{ opacity: sv.interpolate({ inputRange: [0, 0.6], outputRange: [1, 0], extrapolate: 'clamp' }) }} pointerEvents={srch ? 'none' : 'auto'}>
            {p.header}
          </Animated.View>
        </Animated.View>
      )}
      <ScrollView style={st.flex} contentContainerStyle={st.content} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false} onScrollBeginDrag={() => openRow && setOpenRow(null)}>
        {!srch && !selecting ? <Text style={[st.lead, loading && { opacity: 0 }]}>{L.length}개의 기록 · AI 연결 없이 나만 보는 투자 일지예요</Text> : null}
        {/* 검색 줄 */}
        <View style={st.srow}>
          <Pressable onPress={() => input.current?.focus()} style={st.sbx}>
            <JSearch color={appColor.ink3} />
            <TextInput ref={input} value={q} onChangeText={setQ} onFocus={openSearch} placeholder="검색" placeholderTextColor="#8E939C" style={st.sin} accessibilityLabel="기록 검색" />
            <Pressable onPress={notYet} accessibilityRole="button" accessibilityLabel="받아쓰기" hitSlop={8}>
              <JMic color={appColor.ink3} />
            </Pressable>
          </Pressable>
          <Animated.View style={{ width: sbW, opacity: sv.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }), marginLeft: sv.interpolate({ inputRange: [0, 1], outputRange: [0, -8] }), overflow: 'hidden' }}>
            <Pressable onPress={p.onNew} accessibilityRole="button" accessibilityLabel="새 기록" style={({ pressed }) => [st.cmp, pressed && { transform: [{ scale: 0.9 }] }]}>
              <JCompose color={A2} />
            </Pressable>
          </Animated.View>
          <Animated.View style={{ maxWidth: sv.interpolate({ inputRange: [0, 1], outputRange: [0, 60] }), opacity: sv, overflow: 'hidden' }}>
            <Pressable onPress={closeSearch} accessibilityRole="button" hitSlop={6}>
              <Text style={st.scn} numberOfLines={1}>
                취소
              </Text>
            </Pressable>
          </Animated.View>
        </View>

        {srch ? (
          /* 검색 결과 */
          !q.trim() ? (
            <View>
              <Text style={st.rh}>최근 기록</Text>
              <View style={st.card}>{L.slice(0, mockJournalRecentCount).map((j, i) => <JRow key={j.id} j={j} first={i === 0} selV={selV} selecting={false} selected={false} hl={0} onPress={() => (closeSearch(), p.onOpen(j.id))} />)}</View>
            </View>
          ) : results.length ? (
            <View>
              <Text style={st.rh}>기록 {results.length}개</Text>
              <View style={st.card}>
                {results.map((j, i) => (
                  <Reveal key={`${q}-${j.id}`} i={i}>
                    <JRow j={j} q={q} first={i === 0} selV={selV} selecting={false} selected={false} hl={0} onPress={() => (closeSearch(), p.onOpen(j.id))} />
                  </Reveal>
                ))}
              </View>
            </View>
          ) : (
            <View style={[st.empty, { paddingTop: 50 }]}>
              <View style={[st.ill, st.illS]}>
                <JNoHit />
              </View>
              <Text style={st.eT}>‘{q.trim()}’가 들어간 기록이 없어요</Text>
              <Text style={st.eP}>다른 말로 찾아보세요</Text>
            </View>
          )
        ) : loading ? (
          /* 뼈대 (원본: 묶음 3개 · 줄 3/1/2 · 머리 64/40/74) */
          [3, 1, 2].map((n, gi) => (
            <View key={gi}>
              <View style={st.gh}>
                <Skeleton style={{ width: [64, 40, 74][gi], height: 20 }} radius={8} />
              </View>
              <View style={st.card}>
                {Array.from({ length: n }, (_, i) => (
                  <View key={i} style={{ paddingVertical: 13, paddingHorizontal: 16 }}>
                    <Skeleton style={{ width: '58%', height: 16, marginBottom: 8 }} radius={8} />
                    <Skeleton style={{ width: '84%', height: 13 }} radius={8} />
                  </View>
                ))}
              </View>
            </View>
          ))
        ) : !L.length ? (
          <View style={st.empty}>
            <PopIn>
              <View style={st.ill}>
                <JEmptyDoc />
              </View>
            </PopIn>
            <Text style={st.eT}>아직 기록이 없어요</Text>
            <Text style={st.eP}>{'오늘 본 것, 다음에 확인할 것을\n나만의 투자 기록으로 남겨 보세요'}</Text>
            <Pressable onPress={p.onNew} accessibilityRole="button" style={({ pressed }) => [st.btn, pressed && { transform: [{ scale: 0.95 }] }]}>
              <JPlus />
              <Text style={st.btnT}>첫 기록 쓰기</Text>
            </Pressable>
          </View>
        ) : (
          <>
            {pins.length ? (
              <Reveal i={0}>
                <Pressable onPress={() => setFoldPin((f) => !f)} accessibilityRole="button" accessibilityState={{ expanded: !foldPin }} style={st.gh}>
                  <Text style={st.ghT}>고정됨</Text>
                  <Rot fold={foldPin}>
                    <JChevron color={A2} />
                  </Rot>
                </Pressable>
                <Fold open={!foldPin}>
                  <View style={st.card}>{pins.map((j, i) => row(j, i, true))}</View>
                </Fold>
              </Reveal>
            ) : null}
            {groups.map((g, gi) => (
              <Reveal key={g.key} i={gi + (pins.length ? 1 : 0)}>
                <View style={st.gh}>
                  <Text style={st.ghT}>{g.key}</Text>
                </View>
                <View style={st.card}>{g.items.map((j, i) => row(j, i, true))}</View>
              </Reveal>
            ))}
          </>
        )}
      </ScrollView>

      <AppSnackbar visible={!!snack} message={snack?.msg ?? ''} onUndo={snack?.undo ? undo : undefined} style={[st.snack, { bottom: selecting ? 96 + insets.bottom : 16 }]} />
      <Pill toast={toastV} bottom={selecting ? 100 + insets.bottom : 20} />
      <SelBar
        visible={selecting}
        onAction={(a) => {
          const ids = sel ?? [];
          if (a === 'pin') {
            setSel(null);
            doPin(ids);
          } else if (a === 'share') notYet();
          else {
            setSel(null);
            trash(ids);
          }
        }}
      />

      {/* 보기 시트 (원본 #lmore: 기록 선택하기 · 날짜별로 묶기 · 정렬 — 원본 '제안' 표시는 뺌) */}
      <Sheet open={sheet} onClose={() => setSheet(false)} title="보기" label="보기 옵션">
        <View style={{ paddingTop: 4 }}>
          <SRow
            label="기록 선택하기"
            onPress={() => {
              setSheet(false);
              if (L.length) setTimeout(() => enterSel(L[0].id), 250 * k);
            }}
          />
          <SRow
            label="날짜별로 묶기"
            onPress={() => {
              setGrouping((g) => !g);
              setTimeout(() => setSheet(false), 300 * k);
            }}
            right={
              <Toggle
                variant="app"
                on={grouping}
                label="날짜별로 묶기"
                onChange={(v) => {
                  setGrouping(v);
                  setTimeout(() => setSheet(false), 300 * k);
                }}
              />
            }
          />
          <Text style={st.sl}>정렬</Text>
          {(
            [
              ['edit', '수정한 날짜'],
              ['make', '만든 날짜'],
            ] as const
          ).map(([key, label]) => (
            <SRow
              key={key}
              label={label}
              onPress={() => {
                setSort(key);
                setTimeout(() => setSheet(false), 350 * k);
              }}
              right={<Radio on={sort === key} />}
            />
          ))}
        </View>
      </Sheet>
    </View>
  );
}

/** 목록 줄 (원본 .jr: 고르기 동그라미가 왼쪽에서 들어오고 글이 36 밀림 · 고른 줄 #F4F0FF · 나눔 선 왼쪽 16 → 52) */
function JRow({ j, q, first, selV, selecting, selected, hl, onPress, onLongPress }: { j: JournalEntry; q?: string; first: boolean; selV: Animated.Value; selecting: boolean; selected: boolean; hl: number; onPress: () => void; onLongPress?: () => void }) {
  const k = useMotionK();
  const pv = preview(j);
  /* 고정·되돌리기 뒤 잠깐 보라 바탕 (원본 .hl 1.4s) */
  const [hv] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!hl) return;
    hv.setValue(1);
    const a = Animated.sequence([Animated.delay(420 * k), Animated.timing(hv, { toValue: 0, duration: 980 * k, easing: curve.ease, useNativeDriver: false })]);
    a.start();
    return () => a.stop();
  }, [hl, hv, k]);
  const hit = (t: string, base: object) =>
    q
      ? splitHit(t, q).map((s, i) =>
          i % 2 ? (
            <Text key={i} style={[base, st.mark]}>
              {s}
            </Text>
          ) : (
            s
          ),
        )
      : t;
  return (
    <Pressable onPress={onPress} onLongPress={onLongPress} delayLongPress={480} accessibilityRole="button" accessibilityState={selecting ? { selected } : undefined}>
      <Animated.View style={[st.fg, { backgroundColor: selected ? '#F4F0FF' : hv.interpolate({ inputRange: [0, 1], outputRange: ['#FFFFFF', '#EFE8FF'] }) }]}>
        {!first ? <Animated.View style={[st.sep, { left: selV.interpolate({ inputRange: [0, 1], outputRange: [16, 52] }) }]} /> : null}
        <Animated.View pointerEvents="none" style={[st.ckWrap, { transform: [{ translateX: selV.interpolate({ inputRange: [0, 1], outputRange: [-46, 0] }) }] }]}>
          <View style={[st.ck, selected && st.ckOn]}>{selected ? <JCheck /> : null}</View>
        </Animated.View>
        <Animated.View style={[st.tx, { transform: [{ translateX: selV.interpolate({ inputRange: [0, 1], outputRange: [0, 36] }) }] }]}>
          <Text style={st.rT} numberOfLines={1}>
            {hit(appTitle(j), st.rT)}
          </Text>
          <View style={st.rSub}>
            <Text style={st.rS} numberOfLines={1}>
              {j.date}
            </Text>
            <Text style={[st.rP, st.rPv]} numberOfLines={1}>
              {pv ? hit(pv, st.rP) : '추가 텍스트 없음'}
            </Text>
          </View>
        </Animated.View>
      </Animated.View>
    </Pressable>
  );
}

/** 휴지통으로 갈 때 줄 높이가 0 으로 (원본 .jr.gone .26s) */
function Collapse({ gone, children }: { gone: boolean; children: React.ReactNode }) {
  const k = useMotionK();
  const [h, setH] = useState(0);
  const [v] = useState(() => new Animated.Value(1));
  useEffect(() => {
    if (!gone) return v.setValue(1);
    const a = Animated.timing(v, { toValue: 0, duration: 260 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [gone, v, k]);
  return (
    <Animated.View style={gone && h ? { height: v.interpolate({ inputRange: [0, 1], outputRange: [0, h] }), opacity: v, overflow: 'hidden' } : null} onLayout={(e) => !gone && setH(e.nativeEvent.layout.height)}>
      {children}
    </Animated.View>
  );
}

/** 고정됨 접기 (원본 #pinc 높이 .32s) */
function Fold({ open, children }: { open: boolean; children: React.ReactNode }) {
  const k = useMotionK();
  const [h, setH] = useState(0);
  const [v] = useState(() => new Animated.Value(open ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: open ? 1 : 0, duration: 320 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [open, v, k]);
  return (
    <Animated.View style={h ? { height: v.interpolate({ inputRange: [0, 1], outputRange: [0, h] }), overflow: 'hidden' } : null}>
      <View onLayout={(e) => setH(e.nativeEvent.layout.height)} style={h ? { position: 'absolute', left: 0, right: 0, top: 0 } : null}>
        {children}
      </View>
    </Animated.View>
  );
}

function Rot({ fold, children }: { fold: boolean; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(fold ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: fold ? 1 : 0, duration: 300 * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [fold, v, k]);
  return <Animated.View style={{ transform: [{ rotate: v.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '-90deg'] }) }] }}>{children}</Animated.View>;
}

/** 빈 화면 그림 톡 (원본 pop .6s spring) */
function PopIn({ children }: { children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: 1, duration: 600 * k, easing: curve.spring, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [v, k]);
  return <Animated.View style={{ opacity: v.interpolate({ inputRange: [0, 0.3], outputRange: [0, 1], extrapolate: 'clamp' }), transform: [{ scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.6, 1] }) }] }}>{children}</Animated.View>;
}

/** 알림 알약 (원본 .toast: 가운데 · #1F2024 · 13.5px 600 · 위아래 10 좌우 16 · 라운드 20 · .45s spring) */
export function Pill({ toast, bottom }: { toast: Toast | null; bottom: number }) {
  const k = useMotionK();
  const [msg, setMsg] = useState('');
  const [v] = useState(() => new Animated.Value(0));
  const [last, setLast] = useState<Toast | null>(null);
  if (toast !== last) {
    setLast(toast);
    if (toast) setMsg(toast.msg);
  }
  useEffect(() => {
    const a = Animated.timing(v, { toValue: toast ? 1 : 0, duration: (toast ? 450 : 200) * k, easing: toast ? curve.spring : curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [toast, v, k]);
  return (
    <View pointerEvents="none" style={[st.pillWrap, { bottom }]}>
      <Animated.View style={[st.pill, { opacity: v.interpolate({ inputRange: [0, 0.4, 1], outputRange: [0, 1, 1] }), transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [16, 0] }) }, { scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.9, 1] }) }] }]} accessibilityLiveRegion="polite">
        <Text style={st.pillT} numberOfLines={1}>
          {msg}
        </Text>
      </Animated.View>
    </View>
  );
}

/** 아래 고르기 막대 (원본 .abar: 탭바 자리 80 · 아래 14 · 고정 · 공유 · 휴지통(빨강) · 11.5px · 사이 4) */
function SelBar({ visible, onAction }: { visible: boolean; onAction: (a: 'pin' | 'share' | 'del') => void }) {
  const k = useMotionK();
  const insets = useSafeAreaInsets();
  const padB = Math.max(14, insets.bottom);
  const H = 66 + padB;
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: visible ? 1 : 0, duration: 320 * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [visible, v, k]);
  const items = [
    { a: 'pin', label: '고정' },
    { a: 'share', label: '공유' },
    { a: 'del', label: '휴지통' },
  ] as const;
  return (
    <Animated.View pointerEvents={visible ? 'auto' : 'none'} style={[st.abar, { height: H, paddingBottom: padB, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [H, 0] }) }] }]}>
      {items.map((it) => {
        const c = it.a === 'del' ? appColor.red : appColor.ink;
        return (
          <Pressable key={it.a} onPress={() => onAction(it.a)} accessibilityRole="button" accessibilityLabel={it.label} style={st.ab}>
            <JBarIcon k={it.a} color={c} />
            <Text style={[st.abT, { color: c }]}>{it.label}</Text>
          </Pressable>
        );
      })}
    </Animated.View>
  );
}

/** 시트 줄 (원본 .sheet .sr: 52 · 좌우 20 · 15.5px) */
function SRow({ label, onPress, right }: { label: string; onPress: () => void; right?: React.ReactNode }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [st.sr, pressed && { backgroundColor: '#F5F5F8' }]}>
      <Text style={st.srT}>{label}</Text>
      {right ? <View style={{ marginLeft: 'auto' }}>{right}</View> : null}
    </Pressable>
  );
}

/** 정렬 동그라미 (원본 .rdo 22 · 테두리 2 · 안쪽 12 spring) */
function Radio({ on }: { on: boolean }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(on ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: on ? 1 : 0, duration: 350 * k, easing: curve.spring, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [on, v, k]);
  return (
    <View style={[st.rdo, on && { borderColor: appColor.accent }]}>
      <Animated.View style={[st.rdoI, { transform: [{ scale: v }] }]} />
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: appColor.bg },
  flex: { flex: 1 },
  content: { paddingBottom: 70 },
  headWrap: { overflow: 'hidden', backgroundColor: appColor.bg },
  selh: { height: 60, flexDirection: 'row', alignItems: 'center', paddingLeft: 8, paddingRight: 14, backgroundColor: appColor.bg },
  ib: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  selhT: { ...ft(18), fontWeight: '700', color: appColor.ink, marginLeft: 4 },
  all: { marginLeft: 'auto', padding: 8 },
  allT: { ...ft(14.5), fontWeight: '700', color: A2 },
  lead: { ...ft(13.5), color: appColor.ink2, paddingHorizontal: 18, paddingBottom: 8 },
  srow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingTop: 2, paddingHorizontal: 16, paddingBottom: 6 },
  sbx: { flex: 1, minWidth: 0, height: 40, borderRadius: 12, backgroundColor: appColor.searchBg2, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10 },
  sin: { flex: 1, minWidth: 0, fontSize: 15, color: appColor.ink, paddingVertical: 0 },
  cmp: { width: 42, height: 40, borderRadius: 12, backgroundColor: appColor.accentSoft3, alignItems: 'center', justifyContent: 'center' },
  scn: { ...ft(15), fontWeight: '700', color: A2 },
  rh: { ...ft(13), fontWeight: '700', color: appColor.ink3, paddingTop: 12, paddingHorizontal: 18, paddingBottom: 8 },
  gh: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingTop: 16, paddingHorizontal: 18, paddingBottom: 8 },
  ghT: { ...ft(19), fontWeight: '800', color: appColor.ink },
  card: { backgroundColor: appColor.surface, borderRadius: 14, marginHorizontal: 16, overflow: 'hidden' },
  fg: { paddingVertical: 12, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center' },
  sep: { position: 'absolute', top: 0, right: 0, height: 1, backgroundColor: SEP, zIndex: 3 },
  ckWrap: { position: 'absolute', left: 16, top: 0, bottom: 0, justifyContent: 'center' },
  ck: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: '#C5C8CF', alignItems: 'center', justifyContent: 'center' },
  ckOn: { backgroundColor: appColor.accent, borderColor: appColor.accent },
  tx: { flex: 1, minWidth: 0 },
  rT: { ...ft(16), fontWeight: '800', color: appColor.ink },
  rSub: { flexDirection: 'row', alignItems: 'center', marginTop: 3 },
  rS: { ...ft(13.5), color: appColor.ink, flexShrink: 0 },
  rPv: { flex: 1, minWidth: 0, marginLeft: 6 },
  rP: { ...ft(13.5), color: appColor.ink3 },
  mark: { color: A2, fontWeight: '800' },
  empty: { alignItems: 'center', paddingTop: 70, paddingHorizontal: 30 },
  ill: { width: 96, height: 96, borderRadius: 30, backgroundColor: appColor.accentSoft3, alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  illS: { width: 76, height: 76, borderRadius: 24 },
  eT: { ...ft(17), fontWeight: '700', color: appColor.ink, marginBottom: 6, textAlign: 'center' },
  eP: { ...ft(13.5, 1.6), color: appColor.ink2, textAlign: 'center', marginBottom: 18 },
  btn: { height: 46, paddingHorizontal: 20, borderRadius: 23, backgroundColor: appColor.accent, flexDirection: 'row', alignItems: 'center', gap: 6 },
  btnT: { ...ft(15), fontWeight: '700', color: '#FFFFFF' },
  snack: { position: 'absolute', left: 12, right: 12, zIndex: 65, elevation: 6 },
  pillWrap: { position: 'absolute', left: 16, right: 16, alignItems: 'center', zIndex: 80 },
  pill: { backgroundColor: '#1F2024', borderRadius: 20, paddingVertical: 10, paddingHorizontal: 16, maxWidth: 380 },
  pillT: { ...ft(13.5), fontWeight: '600', color: '#FFFFFF' },
  abar: { position: 'absolute', left: 0, right: 0, bottom: 0, flexDirection: 'row', backgroundColor: appColor.surface, borderTopWidth: 1, borderTopColor: appColor.line, zIndex: 46 },
  ab: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 4 },
  abT: { ...ft(11.5) },
  sr: { flexDirection: 'row', alignItems: 'center', gap: 12, height: 52, paddingHorizontal: 20 },
  srT: { ...ft(15.5), color: appColor.ink },
  sl: { ...ft(12.5), fontWeight: '700', color: appColor.ink3, paddingTop: 10, paddingHorizontal: 20, paddingBottom: 2 },
  rdo: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: '#C5C8CF', alignItems: 'center', justifyContent: 'center' },
  rdoI: { width: 12, height: 12, borderRadius: 6, backgroundColor: appColor.accent },
});
