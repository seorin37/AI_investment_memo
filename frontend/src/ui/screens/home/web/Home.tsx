import React, { useEffect, useId, useRef, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Circle, ClipPath, Defs, Line, Path, Rect } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { FixedFrame } from '@/ui/layout/web/FixedFrame';
import { Skeleton } from '@/ui/motion/Skeleton';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { useProgress } from '@/ui/motion/useProgress';
import { ConfirmDialog } from '@/ui/shared/ConfirmDialog';
import { MouseArea } from '@/ui/shared/MouseArea';
import { NudgePill } from '@/ui/shared/NudgePill';
import { Sheet } from '@/ui/shared/Sheet';
import { WebSnackbar } from '@/ui/shared/Snackbar';
import { curve, fpx } from '@/ui/theme';
import type { HomeWidget, MarketIndex, MarketKey, WebHomeProps } from '../Home.types';
import { WEB_RANGES, basisText, mkData, pointText, rangeLabels, type WebRange } from '../homeFormat';
import { CustomHome } from './CustomHome';
import { HomeGrip } from './homeDom.web';
import { CheckWidget, MarketWidget, NewsWidget, Plug12, UpdatesWidget } from './HomeWidgets';
import { useNudge } from '@/store/nudge';

type Hover = { pressed: boolean; hovered?: boolean };
const data = (o: Record<string, string>) => ({ dataSet: o }) as object;
const HALF = new Set<HomeWidget>(['updates', 'news', 'check']);
const DEFAULT_W: HomeWidget[] = ['market', 'updates', 'news'];
/** 원본 homex.tsx CATALOG (웹 위젯 추가 창 이름) */
const CATALOG: [HomeWidget, string, string][] = [
  ['market', '시장 한눈에 보기', '코스피 · 코스닥 · 원/달러'],
  ['updates', '종목별 업데이트', '내 종목의 새 소식 수'],
  ['news', '오늘의 시장 뉴스', '4개 언론사 헤드라인'],
  ['check', '체크리스트', '자유롭게 적는 할 일 목록'],
];
/** 줄 나누기: 넓은 위젯은 한 줄, 반쪽 위젯은 둘씩 (원본 rows) */
function rows(list: HomeWidget[]) {
  const out: HomeWidget[][] = [];
  let half: HomeWidget[] = [];
  for (const id of list) {
    if (HALF.has(id)) {
      half.push(id);
      if (half.length === 2) {
        out.push(half);
        half = [];
      }
    } else {
      if (half.length) {
        out.push(half);
        half = [];
      }
      out.push([id]);
    }
  }
  if (half.length) out.push(half);
  return out;
}
type Snack = { msg: string; undo?: () => void; check?: boolean; key: number };
let seq = 0;
const nextKey = () => ++seq;

/**
 * 웹 홈 (원본 web/src/screens/home.tsx HomePage · homex.tsx · Figma 3792:67043)
 * 860 고정 틀 · 홈 제목 줄(내 종목 · AI 연결 메모 · 홈 편집) · 오늘 내 생각에 붙은 소식 · 시장 한눈에 보기 · 업데이트 + 뉴스 · (체크리스트)
 * 홈 편집: 검정 띠 · ⋮⋮ 끌어 순서 · − 빼기(되돌리기) · 위젯 추가 창 · 기본 구성 되돌리기. 크기 조절 없음.
 * mode 'custom' 이면 홈 직접 사용자화 (custom.tsx).
 */
export function WebHome(p: WebHomeProps) {
  if (p.mode === 'custom') return <CustomHome {...p} />;
  return <TemplateHome {...p} />;
}

function TemplateHome(p: WebHomeProps) {
  const k = useMotionK();
  const [editing, setEditing] = useState(false);
  const [add, setAdd] = useState(false);
  const [reset, setReset] = useState(false);
  const [market, setMarket] = useState<MarketKey | null>(null);
  /* 넛지 (원본 nudge.tsx NudgeHost: 원/달러를 누르면 실험실 제안, 아니면 주간보고서 제안) — 닫은 상태는 store/nudge 한 곳 */
  const [ask, setAsk] = useState<'lab' | null>(null);
  const labN = useNudge('lab');
  const homeN = useNudge('home');
  const nudge: 'report' | 'lab' | null = ask === 'lab' && labN.show ? 'lab' : homeN.show ? 'report' : null;
  const setNudge = (v: 'lab' | null) => {
    if (v === 'lab') return setAsk('lab');
    if (nudge === 'lab') labN.hide();
    else homeN.hide();
  };
  const [snack, setSnack] = useState<Snack | null>(null);
  const [drag, setDrag] = useState<HomeWidget | null>(null);
  const [gone, setGone] = useState<HomeWidget | null>(null);
  const [ready, setReady] = useState(false);
  const list = p.widgets;
  const cur = useRef(list);
  useEffect(() => {
    cur.current = list;
  }, [list]);
  /* 원본 SkelPage: 뼈대 .52s → 차례로 (0.07s) */
  useEffect(() => {
    const t = setTimeout(() => setReady(true), 520 * k);
    return () => clearTimeout(t);
  }, [k]);
  useEffect(() => {
    if (!snack) return;
    const t = setTimeout(() => setSnack(null), 4000 * k);
    return () => clearTimeout(t);
  }, [snack, k]);
  const total = p.updates.reduce((a, u) => a + u.new_count, 0);
  const remove = (id: HomeWidget) => {
    setGone(id);
    setTimeout(() => {
      const before = cur.current;
      p.onChangeWidgets(before.filter((y) => y !== id));
      setGone(null);
      setSnack({ msg: '위젯을 뺐어요', undo: () => (p.onChangeWidgets(before), setSnack(null)), key: nextKey() });
    }, 320 * k);
  };
  const over = (id: HomeWidget, to: HomeWidget) => {
    const l = cur.current;
    const a = l.filter((y) => y !== id);
    const i = a.indexOf(to);
    const j = l.indexOf(to) > l.indexOf(id) ? i + 1 : i;
    a.splice(j, 0, id);
    cur.current = a;
    p.onChangeWidgets(a);
  };
  const day = p.days[p.days.length - 1] ?? '';
  const render = (id: HomeWidget, w: number | '100%' | undefined) =>
    id === 'market' ? (
      <MarketWidget indices={p.market} onMore={setMarket} onUsd={() => setNudge('lab')} onRetry={p.onRetryMarket} />
    ) : id === 'updates' ? (
      <UpdatesWidget rows={p.updates} w={w === undefined ? '100%' : w} onAll={p.onOpenUpdates} onRow={p.onOpenStockUpdates} />
    ) : id === 'news' ? (
      <NewsWidget items={p.news} day={p.news_day || day} total={p.news_day_total} now={p.now} onOpen={p.onOpenNews} />
    ) : (
      <CheckWidget stocks={p.stocks} checklists={p.checklists} onToggle={p.onToggleCheck} onAdd={p.onAddCheck} onEdit={p.onOpenStock} />
    );
  let blk = 0;
  return (
    <View style={st.root}>
      <ScrollView style={st.flex} showsVerticalScrollIndicator={false}>
        <FixedFrame>
          <View style={st.page}>
            {/* 홈 제목 줄 (원본 HomeHead · PageTitle) */}
            <View style={st.head}>
              <View style={st.headL}>
                <Text style={st.title}>홈</Text>
                <Text style={st.sub}>떠오른 생각을 적어 두면, AI가 관련 소식을 대신 확인해요.</Text>
              </View>
              <View style={st.headR}>
                <View style={st.pill}>
                  <Text style={st.pillT}>
                    내 종목 <Text style={st.pillB}>{p.stocks.length}</Text>
                  </Text>
                </View>
                <View style={[st.pill, st.pillAi]}>
                  <Plug12 c="#111111" />
                  <Text style={[st.pillT, { color: '#111111' }]}>
                    AI 연결 메모 <Text style={[st.pillB, { color: '#111111' }]}>{p.counts.ai_memos}</Text>
                  </Text>
                </View>
                {!editing ? (
                  <Pressable onPress={() => setEditing(true)} accessibilityRole="button" style={({ hovered }: Hover) => [st.pill, st.pillEdit, hovered && { backgroundColor: '#F9F9F9' }]}>
                    <Svg width={14} height={14} viewBox="0 0 16 16" fill="none" stroke="#15171A" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                      <Path d="M9.5 3.5l3 3M3 13l.6-3L10.8 2.8a1 1 0 0 1 1.4 0l1 1a1 1 0 0 1 0 1.4L6 12.4z" />
                    </Svg>
                    <Text style={st.pillEditT}>홈 편집</Text>
                  </Pressable>
                ) : null}
              </View>
            </View>
            {p.firstStart ? <View style={{ marginBottom: 20 }}>{p.firstStart}</View> : null}
            {editing ? (
              <EditBar onAdd={() => setAdd(true)} onReset={() => setReset(true)} onDone={() => setEditing(false)} />
            ) : (
              <SkBlock i={blk++} ready={ready} r={20}>
                <TodayStrip total={total} rows={p.updates.filter((u) => u.new_count > 0).map((u) => `${u.name} ${u.new_count}건`)} onGo={p.onOpenUpdates} />
              </SkBlock>
            )}
            {/* 위젯 칸 (원본 HomeGrid: 줄 사이 24 · 편집 중 2px 검정 테두리 + 오른쪽 위 ⋮⋮ − 막대) */}
            <View style={st.grid}>
              {list.length === 0 ? (
                <Pressable onPress={() => setAdd(true)} accessibilityRole="button" style={({ hovered }: Hover) => [st.empty, hovered && { borderColor: '#B9BEC6' }]}>
                  <Text style={st.emptyPlus}>＋</Text>
                  <Text style={st.emptyB}>위젯 추가</Text>
                  <Text style={st.emptyT}>눌러서 위젯을 골라 보세요</Text>
                </Pressable>
              ) : null}
              {rows(list).map((r) => (
                <View key={r.join('+')} style={st.gridRow}>
                  {(r.length === 1 ? [[r[0], '100%'] as const] : r.map((id) => [id, id === 'updates' ? 320 : undefined] as const)).map(([id, w]) => (
                    <SkBlock key={id} i={blk++} ready={ready} r={20} style={w === undefined ? st.flexMin : w === '100%' ? { width: '100%' } : { width: w, flexShrink: 0 }}>
                      <WidgetCell id={id} editing={editing} lifted={drag === id} gone={gone === id} onStart={() => setDrag(id)} onOver={(to) => over(id, to as HomeWidget)} onEnd={() => setDrag(null)} onRemove={() => remove(id)}>
                        {render(id, w)}
                      </WidgetCell>
                    </SkBlock>
                  ))}
                </View>
              ))}
            </View>
          </View>
        </FixedFrame>
        <View style={{ height: 96 }} />
      </ScrollView>
      {nudge ? (
        <View style={st.nudge} pointerEvents="box-none">
          <NudgePill text={nudge === 'lab' ? '환율이 바뀌면 내 종목은? 실험해 보기' : '이번 주 내 종목, 한 장으로 볼까요?'} onGo={() => p.onNudge(nudge)} onClose={() => setNudge(null)} />
        </View>
      ) : null}
      <WebSnackbar visible={!!snack} message={snack?.msg ?? ''} onUndo={snack?.undo} check={snack?.check} style={[st.snack, { bottom: nudge ? 92 : 30 }]} />
      <Sheet open={add} onClose={() => setAdd(false)} width={680} label="위젯 추가">
        <View style={st.addBox}>
          <View style={st.between}>
            <Text style={st.addTitle}>위젯 추가</Text>
            <Pressable onPress={() => setAdd(false)} accessibilityRole="button">
              {({ hovered }: Hover) => <Text style={[st.addClose, hovered && { color: '#191F28' }]}>닫기</Text>}
            </Pressable>
          </View>
          <View style={st.g8}>
            {CATALOG.map(([id, t, d]) => {
              const have = list.includes(id);
              return (
                <Pressable
                  key={id}
                  disabled={have}
                  onPress={() => {
                    p.onChangeWidgets([id, ...list]);
                    setAdd(false);
                    setSnack({ msg: '위젯을 맨 위에 넣었어요 · 끌어서 옮길 수 있어요', check: true, key: nextKey() });
                  }}
                  style={({ hovered }: Hover) => [st.addRow, have ? st.addHave : { backgroundColor: hovered ? '#EEF0F3' : '#F5F6F8' }]}
                >
                  <View style={st.flexMin}>
                    <Text style={st.addT}>{t}</Text>
                    <Text style={st.addD}>{d}</Text>
                  </View>
                  <Text style={st.addR}>{have ? '홈에 있어요' : '추가'}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      </Sheet>
      <ConfirmDialog
        variant="web"
        open={reset}
        title="기본 구성으로 되돌릴까요?"
        body="지금 순서와 고른 위젯이 처음 구성(시장 · 업데이트 · 뉴스)으로 바뀌어요."
        confirmLabel="되돌리기"
        onCancel={() => setReset(false)}
        onConfirm={() => {
          p.onChangeWidgets(DEFAULT_W);
          setReset(false);
          setSnack({ msg: '기본 구성으로 되돌렸어요', check: true, key: nextKey() });
        }}
      />
      <MarketDetailDialog q={p.market?.find((m) => m.key === market) ?? null} onClose={() => setMarket(null)} />
    </View>
  );
}

/** 원본 SkelPage 칸: .52s 뼈대(같은 모양 · 라운드) 뒤 i × 0.07s 차례로 나타남 */
function SkBlock({ i, ready, r, style, children }: { i: number; ready: boolean; r: number; style?: object; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!ready) return;
    const a = Animated.timing(v, { toValue: 1, duration: 450 * k, delay: i * 70 * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [ready, v, i, k]);
  return (
    <View style={style}>
      <Animated.View style={{ opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }) }] }}>{children}</Animated.View>
      <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFill, { opacity: v.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }) }]}>
        <Skeleton style={StyleSheet.absoluteFill} radius={r} />
      </Animated.View>
    </View>
  );
}

/* ───────── 오늘 내 생각에 붙은 소식 (원본 TodayStrip: 76 · 라운드 20 · 검정 아이콘 44) ───────── */
function TodayStrip({ total, rows: r, onGo }: { total: number; rows: string[]; onGo: () => void }) {
  return (
    <View style={st.today}>
      <View style={st.todayIc}>
        <Plug12 size={20} c="#FFFFFF" />
      </View>
      <View style={st.flexMin}>
        <Text style={st.todayT} numberOfLines={1}>
          {total ? `오늘 내 생각에 붙은 소식 ${total}건` : '오늘은 내 생각에 붙은 새 소식이 없어요'}
        </Text>
        <Text style={st.todayS} numberOfLines={1}>
          {total ? r.join(' · ') : 'AI가 매일 확인하고 있어요. 새 소식이 오면 알려 드릴게요.'}
        </Text>
      </View>
      {total > 0 ? (
        <Pressable onPress={onGo} accessibilityRole="button" style={({ hovered }: Hover) => [st.todayB, { backgroundColor: hovered ? '#2A2A2A' : '#111111' }]}>
          <Text style={st.todayBT}>확인하기</Text>
          <Svg width={16} height={16} viewBox="0 0 14 14" fill="none">
            <Path d="M3 7h8M7.5 3.5 11 7l-3.5 3.5" stroke="white" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
          </Svg>
        </Pressable>
      ) : null}
    </View>
  );
}

/* ───────── 편집 띠 (원본 EditBar: 76 · #15171A · 흰 글자) ───────── */
function EditBar({ onAdd, onReset, onDone }: { onAdd: () => void; onReset: () => void; onDone: () => void }) {
  return (
    <View style={st.ebar}>
      <View style={st.flexMin}>
        <Text style={st.ebarT}>홈 편집</Text>
        <Text style={st.ebarS}>⋮⋮를 끌어 순서를 바꾸고, 필요 없는 건 − 로 빼 보세요.</Text>
      </View>
      <Pressable onPress={onReset} accessibilityRole="button" style={({ hovered }: Hover) => [st.ebarBtn, hovered && { backgroundColor: 'rgba(255,255,255,0.1)' }]}>
        <Text style={[st.ebarBtnT, { color: 'rgba(255,255,255,0.8)' }]}>기본 구성으로 되돌리기</Text>
      </Pressable>
      <Pressable onPress={onAdd} accessibilityRole="button" style={({ hovered }: Hover) => [st.ebarBtn, { paddingHorizontal: 16, backgroundColor: hovered ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.1)' }]}>
        <Text style={st.ebarBtnT}>＋ 위젯 추가</Text>
      </Pressable>
      <Pressable onPress={onDone} accessibilityRole="button" style={({ hovered }: Hover) => [st.ebarDone, hovered && { backgroundColor: '#F2F3F4' }]}>
        <Text style={st.ebarDoneT}>완료</Text>
      </Pressable>
    </View>
  );
}

/* ───────── 위젯 칸 (편집: 2px 검정 테두리 · 오른쪽 위 ⋮⋮ · −) ───────── */
function WidgetCell({ id, editing, lifted, gone, onStart, onOver, onEnd, onRemove, children }: { id: HomeWidget; editing: boolean; lifted: boolean; gone: boolean; onStart: () => void; onOver: (to: string) => void; onEnd: () => void; onRemove: () => void; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(1));
  useEffect(() => {
    if (!gone) return;
    const a = Animated.timing(v, { toValue: 0, duration: 320 * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [gone, v, k]);
  return (
    <Animated.View {...data({ hw: id })} style={[st.cell, lifted && st.lift, { opacity: v, transform: [{ scale: lifted ? 1.015 : v.interpolate({ inputRange: [0, 1], outputRange: [0.94, 1] }) }] }]}>
      {children}
      {editing ? <View pointerEvents="none" style={st.ring} /> : null}
      {editing ? (
        <View style={st.tools}>
          <HomeGrip id={id} onStart={onStart} onOver={onOver} onEnd={onEnd}>
            <Svg width={16} height={16} viewBox="0 0 16 16" fill="#FFFFFF">
              {[4, 8, 12].map((y) => (
                <React.Fragment key={y}>
                  <Circle cx={5.5} cy={y} r={1.3} />
                  <Circle cx={10.5} cy={y} r={1.3} />
                </React.Fragment>
              ))}
            </Svg>
          </HomeGrip>
          <Pressable onPress={onRemove} accessibilityRole="button" accessibilityLabel="위젯 빼기" style={({ hovered }: Hover) => [st.tool, hovered && { backgroundColor: 'rgba(255,255,255,0.1)' }]}>
            <Svg width={16} height={16} viewBox="0 0 16 16" fill="none">
              <Path d="M3.5 8h9" stroke="#FFFFFF" strokeWidth={2} strokeLinecap="round" />
            </Svg>
          </Pressable>
        </View>
      ) : null}
    </Animated.View>
  );
}

/* ───────── 시장 상세 창 (원본 MarketDetail: 680 · 라운드 28 · 선 616×220 · 마우스로 훑으면 그때 값) ───────── */
function MarketDetailDialog({ q, onClose }: { q: MarketIndex | null; onClose: () => void }) {
  const [last, setLast] = useState(q);
  if (q && q !== last) setLast(q);
  const [r, setR] = useState<WebRange>('1달');
  const [hx, setHx] = useState<number | null>(null);
  const t = useProgress(!!q, 1000, `${q?.key}-${r}`);
  /* 2026-11-23: 홈이 다시 쌓여도 클립 id 가 겹치지 않게 (일찍 return 하기 전에 부름) */
  const clipId = `mdc${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  const shown = q ?? last;
  if (!shown) return <Sheet open={false} onClose={onClose} label="시장 상세" width={680}>{null}</Sheet>;
  const md = mkData(shown, r);
  const sr = md.sr;
  const W = 616;
  const H = 220;
  const mn = Math.min(...sr);
  const mx = Math.max(...sr);
  const X = (i: number) => (i / (sr.length - 1)) * W;
  const Y = (v: number) => 10 + ((mx - v) / (mx - mn || 1)) * (H - 40);
  const col = md.up ? '#E5484D' : '#2F6BDB';
  /* 축·짚은 점의 날짜 = 그 지표 자신의 dates (2026-11-21) */
  const labels = rangeLabels(r, shown.dates);
  const ds = shown.dates.slice(-sr.length);
  const idx = hx === null ? null : Math.max(0, Math.min(sr.length - 1, Math.round((hx / W) * (sr.length - 1))));
  const fmt = (n: number) => n.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const when = (i: number) => pointText(shown, ds[i]);
  const line = sr.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join('');
  const e = curve.ease(t);
  return (
    <Sheet open={!!q} onClose={onClose} width={680} label={`${shown.name} 상세`}>
      <View style={st.md}>
        <View style={st.mdHead}>
          <View>
            <Text style={st.mdName}>{shown.name}</Text>
            <Text style={st.mdV}>{idx === null ? md.v : fmt(sr[idx])}</Text>
            <Text style={[st.mdL, { color: col }]}>{idx === null ? `${md.label} · ${md.when}` : when(idx)}</Text>
          </View>
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="닫기" style={({ hovered }: Hover) => [st.mdX, hovered && { backgroundColor: '#F2F3F4' }]}>
            <Svg width={20} height={20} viewBox="0 0 20 20" fill="none">
              <Path d="M5 5L15 15M15 5L5 15" stroke="#333" strokeWidth={1.8} strokeLinecap="round" />
            </Svg>
          </Pressable>
        </View>
        <View style={{ width: W, height: H }}>
          <Svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} fill="none" style={StyleSheet.absoluteFill}>
            {[0, 1, 2, 3].map((i) => (
              <Line key={i} x1={0} x2={W} y1={10 + i * ((H - 40) / 3)} y2={10 + i * ((H - 40) / 3)} stroke="#EEF0F3" />
            ))}
            <Path d={line} stroke={idx === null ? col : '#C9CCD2'} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" strokeDasharray={idx === null ? `${W * 3} ${W * 3}` : undefined} strokeDashoffset={idx === null ? W * 3 * (1 - e) : undefined} />
            {idx !== null ? (
              <>
                <Defs>
                  <ClipPath id={clipId}>
                    <Rect x={0} y={0} width={X(idx)} height={H} />
                  </ClipPath>
                </Defs>
                <Path d={line} stroke={col} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" clipPath={`url(#${clipId})`} />
                <Line x1={X(idx)} x2={X(idx)} y1={0} y2={H - 24} stroke="#15171A" strokeDasharray="3 3" />
                <Circle cx={X(idx)} cy={Y(sr[idx])} r={5} fill="#FFFFFF" stroke={col} strokeWidth={2.4} />
              </>
            ) : null}
          </Svg>
          <View style={st.mdAxis} pointerEvents="none">
            {labels.map((l, i) => (
              <Text key={l + i} style={st.mdAxisT}>
                {l}
              </Text>
            ))}
          </View>
          <MouseArea width={W} height={H} onMove={(x) => setHx(x)} onLeave={() => setHx(null)} style={{ left: 0, top: 0 }} />
        </View>
        <View style={st.rseg}>
          {WEB_RANGES.map((x) => (
            <Pressable key={x} onPress={() => setR(x)} accessibilityRole="tab" accessibilityState={{ selected: r === x }} style={[st.rsegB, r === x && st.rsegOn]}>
              {({ hovered }: Hover) => <Text style={[st.rsegT, r === x ? st.rsegTOn : { color: hovered ? '#16171A' : '#8B95A1' }]}>{x}</Text>}
            </Pressable>
          ))}
        </View>
        <Text style={st.mdFoot}>
          {`선을 마우스로 훑으면 그때의 값이 보여요 · ${basisText(shown)}`}
        </Text>
      </View>
    </Sheet>
  );
}

const st = StyleSheet.create({
  root: { flex: 1 },
  flex: { flex: 1 },
  flexMin: { flex: 1, minWidth: 0 },
  between: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  g8: { gap: 8 },
  page: { width: 860, gap: 32, paddingTop: 32, paddingBottom: 32 },
  head: { width: '100%', paddingTop: 24, flexDirection: 'row', alignItems: 'flex-start', gap: 16 },
  headL: { height: 52, flex: 1, minWidth: 0, gap: 4 },
  title: { ...fpx(26, 35), fontWeight: '700', letterSpacing: -0.26, color: '#16171A' },
  sub: { ...fpx(14, 21), color: '#575B63' },
  headR: { position: 'absolute', right: 0, top: 25, flexDirection: 'row', alignItems: 'center', gap: 8 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 999, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#FFFFFF', paddingHorizontal: 12, paddingVertical: 6 },
  pillAi: { backgroundColor: '#E7E7E7', borderColor: '#E7E7E7' },
  pillT: { ...fpx(13, 20), fontWeight: '500', color: '#575B63' },
  pillB: { fontWeight: '700', color: '#16171A' },
  pillEdit: { gap: 4 },
  pillEditT: { ...fpx(13, 20), fontWeight: '700', color: '#15171A' },
  today: { height: 76, width: '100%', flexDirection: 'row', alignItems: 'center', gap: 16, borderRadius: 20, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#FFFFFF', paddingLeft: 20, paddingRight: 16 },
  todayIc: { width: 44, height: 44, borderRadius: 14, backgroundColor: '#111111', alignItems: 'center', justifyContent: 'center' },
  todayT: { ...fpx(17, 26), fontWeight: '700', letterSpacing: -0.17, color: '#16171A' },
  todayS: { ...fpx(14, 21), color: '#575B63' },
  todayB: { height: 44, flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 12, paddingHorizontal: 16 },
  todayBT: { ...fpx(15, 23), fontWeight: '700', color: '#FFFFFF' },
  ebar: { height: 76, width: '100%', flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 20, backgroundColor: '#15171A', paddingLeft: 24, paddingRight: 16 },
  ebarT: { ...fpx(17, 26), fontWeight: '700', color: '#FFFFFF' },
  ebarS: { ...fpx(14, 21), color: 'rgba(255,255,255,0.7)' },
  ebarBtn: { height: 40, borderRadius: 12, paddingHorizontal: 12, justifyContent: 'center' },
  ebarBtnT: { ...fpx(14, 20), fontWeight: '700', color: '#FFFFFF' },
  ebarDone: { height: 40, borderRadius: 12, backgroundColor: '#FFFFFF', paddingHorizontal: 20, justifyContent: 'center' },
  ebarDoneT: { ...fpx(15, 20), fontWeight: '700', color: '#15171A' },
  grid: { width: '100%', gap: 24 },
  gridRow: { width: '100%', flexDirection: 'row', alignItems: 'flex-start', gap: 24 },
  cell: { position: 'relative', minWidth: 0 },
  lift: { zIndex: 10, borderRadius: 20, shadowColor: '#111111', shadowOpacity: 0.35, shadowRadius: 40, shadowOffset: { width: 0, height: 18 }, elevation: 12 },
  ring: { position: 'absolute', top: -2, left: -2, right: -2, bottom: -2, zIndex: 10, borderRadius: 22, borderWidth: 2, borderColor: '#111111' },
  tools: { position: 'absolute', right: 12, top: 12, zIndex: 20, flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 12, backgroundColor: '#15171A', padding: 4, shadowColor: '#000000', shadowOpacity: 0.5, shadowRadius: 20, shadowOffset: { width: 0, height: 8 }, elevation: 8 },
  tool: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  empty: { height: 220, width: '100%', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: 20, borderWidth: 2, borderStyle: 'dashed', borderColor: '#D5D8DD', backgroundColor: '#FFFFFF' },
  emptyPlus: { fontSize: 32, lineHeight: 32, color: '#15171A' },
  emptyB: { ...fpx(17, 24), fontWeight: '700', color: '#15171A' },
  emptyT: { ...fpx(14, 20), color: '#8B95A1' },
  nudge: { position: 'absolute', left: 0, right: 0, bottom: 28, alignItems: 'center' },
  snack: { position: 'absolute' },
  addBox: { width: 680, maxWidth: '100%', gap: 16, borderRadius: 20, backgroundColor: '#FFFFFF', padding: 28 },
  addTitle: { ...fpx(22, 31), fontWeight: '700', color: '#15171A' },
  addClose: { ...fpx(14, 20), fontWeight: '500', color: '#6B7684' },
  addRow: { height: 68, width: '100%', flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 16, paddingHorizontal: 16 },
  addHave: { backgroundColor: '#F7F8FA', opacity: 0.6 },
  addT: { ...fpx(17, 26), fontWeight: '700', color: '#15171A' },
  addD: { ...fpx(14, 21), color: '#747D8D' },
  addR: { flexShrink: 0, ...fpx(14, 20), fontWeight: '700', color: '#575B63' },
  md: { width: 680, maxWidth: '100%', gap: 16, borderRadius: 28, backgroundColor: '#FFFFFF', paddingHorizontal: 32, paddingBottom: 28, paddingTop: 28 },
  mdHead: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
  mdName: { ...fpx(15, 23), fontWeight: '500', color: '#575B63' },
  mdV: { ...fpx(30, 40), fontWeight: '700', color: '#15171A' },
  mdL: { ...fpx(14, 21), fontWeight: '700' },
  mdX: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  mdAxis: { position: 'absolute', left: 0, right: 0, bottom: 0, flexDirection: 'row', justifyContent: 'space-between' },
  mdAxisT: { ...fpx(11, 16), color: '#8B95A1' },
  mdFoot: { ...fpx(13, 20), color: '#8B95A1' },
  rseg: { height: 48, width: '100%', flexDirection: 'row', alignItems: 'flex-start', borderRadius: 14, backgroundColor: '#F3F4F6', padding: 4 },
  rsegB: { height: 40, flex: 1, minWidth: 0, alignItems: 'center', justifyContent: 'center', borderRadius: 12 },
  rsegOn: { backgroundColor: '#FFFFFF' },
  rsegT: { ...fpx(15, 23), fontWeight: '500' },
  rsegTOn: { fontWeight: '700', color: '#16171A' },
});
