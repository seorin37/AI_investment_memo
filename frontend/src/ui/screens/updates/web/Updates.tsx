import React, { useEffect, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Line, Path } from 'react-native-svg';
import { Text, TextInput } from '@/components/ui/AppText';
import { FixedFrame } from '@/ui/layout/web/FixedFrame';
import { Collapse } from '@/ui/motion/Collapse';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { NudgePill } from '@/ui/shared/NudgePill';
import { StockLogo } from '@/ui/shared/StockLogo';
import { curve, fpx } from '@/ui/theme';
import type { KindFilter, UpdateItem, WebUpdatesProps } from '../Updates.types';
import { KINDS, WEB_TAG, ago, byStock, josa, unreadOf } from '../updatesFormat';
import { versionsOf } from '../Updates.mock';
import { useNudge } from '@/store/nudge';

type Hover = { pressed: boolean; hovered?: boolean };
const mmdd = (iso: string) => `${iso.slice(5, 7)}.${iso.slice(8, 10)}`;
const CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';
const cho = (t: string) =>
  [...t]
    .map((c) => {
      const n = c.charCodeAt(0) - 44032;
      return n >= 0 && n < 11172 ? CHO[Math.floor(n / 588)] : c;
    })
    .join('');

/**
 * 웹 최신 업데이트 · 종목 업데이트 (원본 web/src/screens/updates.tsx · Figma 3.1 · 3.2)
 * 860 틀 · 제목 줄(읽지 않은 소식 · 모두 읽음) · 종목 칩(검은 알약) + 내 종목에서 찾기 · 종류 알약
 * 전체 = 종목 카드 2열(최근 3건 · +N건 더 보기) / 종목 = 한 카드 목록. 줄을 누르면 AI 요약 · 원문 근거 · 연결된 내 메모가 펼쳐짐.
 */
export function WebUpdates(p: WebUpdatesProps) {
  const cur = p.code ? p.stocks.find((s) => s.stock_code === p.code) : undefined;
  const [topic, setTopic] = useState<KindFilter>('전체');
  const [lastCode, setLastCode] = useState(p.code);
  if (lastCode !== p.code) {
    setLastCode(p.code);
    if (topic !== '전체') setTopic('전체');
  }
  const [q, setQ] = useState('');
  const [qOpen, setQOpen] = useState(false);
  /* 넛지 닫은 상태는 한 곳(store/nudge)에 — 다시 들어와도 안 뜸 · 사용법 안내 중엔 숨김 */
  const nudgeS = useNudge('updates');
  const nudge = nudgeS.show;
  const setNudge = (v: boolean) => {
    if (!v) nudgeS.hide();
  };
  const CARD = (c: string) => byStock(p.items, c).slice(0, 3);
  const pool = cur ? byStock(p.items, cur.stock_code) : p.stocks.flatMap((s) => CARD(s.stock_code));
  const unread = pool.filter((u) => u.unread).map((u) => u.id);
  const pass = (u: UpdateItem) => topic === '전체' || u.kind === topic;
  const found = q.trim() ? p.stocks.filter((s) => s.name.includes(q.trim()) || cho(s.name).includes(q.trim()) || s.stock_code.includes(q.trim())) : p.stocks;
  const nN = unreadOf(pool);
  return (
    <View style={st.root}>
      <ScrollView style={st.flex} showsVerticalScrollIndicator={false}>
        <FixedFrame>
          <View style={st.page}>
            <View style={st.head}>
              <View style={st.headL}>
                <Text style={st.title}>{cur ? `${cur.name} 업데이트` : '최신 업데이트'}</Text>
                <Text style={st.sub}>{cur ? `${cur.name}의 공시·뉴스·주가 변동을 시간순으로 모았어요` : '내 종목의 공시·뉴스·주가 변동을 모아봤어요'}</Text>
              </View>
              <View style={st.headR}>
                {unread.length ? (
                  <View style={st.unr}>
                    <View style={st.unrDot} />
                    <Text style={st.unrT}>읽지 않은 소식 {unread.length}건</Text>
                  </View>
                ) : null}
                <Pressable disabled={!unread.length} onPress={() => p.onMarkRead(unread, true)} accessibilityRole="button" style={({ hovered }: Hover) => [st.readAll, hovered && unread.length ? { backgroundColor: '#DCDCDC' } : null, !unread.length && { opacity: 0.4 }]}>
                  <Svg width={14} height={14} viewBox="0 0 14 14" fill="none">
                    <Path d="M2.5 7.2L5.4 10L11.5 4" stroke="#111111" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
                  </Svg>
                  <Text style={st.readAllT}>모두 읽음</Text>
                </Pressable>
              </View>
            </View>
            <View style={st.body}>
              <View style={st.chipRow}>
                <PillChips
                  items={[{ key: '', label: '업데이트' }, ...p.stocks.map((s) => ({ key: s.stock_code, label: s.name }))]}
                  value={p.code ?? ''}
                  onChange={(c) => p.onChangeCode?.(c || undefined)}
                />
                <View style={st.searchWrap}>
                  <View style={[st.search, qOpen && st.searchOn]}>
                    <Svg width={16} height={16} viewBox="0 0 20 20" fill="none" stroke="#6B7078" strokeWidth={1.6} strokeLinecap="round">
                      <Path d="M9 3.5a5.5 5.5 0 1 1 0 11a5.5 5.5 0 0 1 0-11z" />
                      <Path d="M13 13l4 4" />
                    </Svg>
                    <TextInput value={q} onChangeText={setQ} onFocus={() => setQOpen(true)} onBlur={() => setTimeout(() => setQOpen(false), 150)} placeholder="내 종목에서 찾기 (초성도 돼요)" placeholderTextColor="#8B95A1" style={st.searchIn} />
                  </View>
                  {qOpen ? (
                    <View style={st.drop}>
                      {found.length === 0 ? (
                        <Text style={st.dropNone}>내 종목에 ‘{q}’이 없어요 · 종목은 사이드바 + 에서 추가해요</Text>
                      ) : (
                        found.map((s) => {
                          const n = unreadOf(byStock(p.items, s.stock_code));
                          return (
                            <Pressable
                              key={s.stock_code}
                              onPress={() => {
                                setQ('');
                                setQOpen(false);
                                p.onChangeCode?.(s.stock_code);
                              }}
                              style={({ hovered }: Hover) => [st.dropRow, hovered && { backgroundColor: '#F5F6F8' }]}
                            >
                              <Text style={st.dropN} numberOfLines={1}>
                                {s.name}
                              </Text>
                              <Text style={st.dropS}>{n ? `새 소식 ${n}` : '새 소식 없음'}</Text>
                            </Pressable>
                          );
                        })
                      )}
                    </View>
                  ) : null}
                </View>
              </View>
              <Topics pool={pool} topic={topic} setTopic={setTopic} />
              {!cur ? (
                <View style={st.grid}>
                  {p.stocks.map((s, ci) => {
                    const rows = CARD(s.stock_code);
                    const more = byStock(p.items, s.stock_code).length - rows.length;
                    return (
                      <Appear key={s.stock_code} i={ci} style={st.card}>
                        <Pressable onPress={() => p.onOpenBoard(s.stock_code)} accessibilityLabel={`${s.name} 화면으로`} style={({ hovered }: Hover) => [st.nameBtn, hovered && { backgroundColor: '#F3F4F6' }]}>
                          <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={28} variant="webSide" radius={8} />
                          <Text style={st.cardName}>{s.name}</Text>
                          <View style={st.hold}>
                            <Text style={st.holdT}>{s.status === 'holding' ? '보유' : '관심'}</Text>
                          </View>
                          <Svg width={16} height={16} viewBox="0 0 16 16" fill="none">
                            <Path d="M6 3.5L10.5 8L6 12.5" stroke="#8B95A1" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
                          </Svg>
                        </Pressable>
                        <Text style={st.code}>
                          {s.stock_code} · {s.market}
                        </Text>
                        <View style={st.div} />
                        {rows.length ? (
                          rows.some(pass) ? (
                            rows.map((r) => (pass(r) ? <Row key={r.id} u={r} p={p} name={s.name} /> : null))
                          ) : (
                            <Text style={st.empty}>{topic} 소식이 없어요</Text>
                          )
                        ) : (
                          <Text style={[st.empty, { color: '#6B7684' }]}>최근 30일 동안 새 소식이 없어요</Text>
                        )}
                        {more > 0 ? (
                          <Pressable onPress={() => p.onChangeCode?.(s.stock_code)}>
                            {({ hovered }: Hover) => <Text style={[st.more, hovered && { color: '#15171A' }]}>+{more}건 더 보기</Text>}
                          </Pressable>
                        ) : null}
                      </Appear>
                    );
                  })}
                </View>
              ) : (
                <Appear i={0} style={st.list}>
                  {pool.filter(pass).map((r, j) => (
                    <View key={r.id} style={[st.listRow, j > 0 && st.listLine]}>
                      <Row u={r} p={p} name={cur.name} logo />
                    </View>
                  ))}
                  {pool.length > 0 && !pool.some(pass) ? <Text style={[st.empty, st.listEmpty]}>{topic} 소식이 없어요</Text> : null}
                  {!pool.length ? <Text style={[st.empty, st.listEmpty, { color: '#6B7684' }]}>최근 30일 동안 새 소식이 없어요. AI가 매일 확인하고 있어요.</Text> : null}
                </Appear>
              )}
              <View style={st.end}>
                <Text style={st.endT}>최근 30일 업데이트를 모두 확인했어요</Text>
                <Text style={st.disc}>투자 권유가 아닌 참고 정보예요 · AI는 틀릴 수 있어 원문을 꼭 확인해 주세요</Text>
              </View>
            </View>
          </View>
        </FixedFrame>
        <View style={{ height: 96 }} />
      </ScrollView>
      {nudge && nN ? (
        <View style={st.nudge} pointerEvents="box-none">
          <NudgePill text={`오늘 소식 ${nN}건, 라디오로 들을까요?`} onGo={p.onNudge} onClose={() => setNudge(false)} />
        </View>
      ) : null}
    </View>
  );
}

/** 원본 SkelPage 처럼 차례로 나타남 (m-reveal) */
function Appear({ i, style, children }: { i: number; style?: object; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: 1, duration: 450 * k, delay: i * 70 * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [v, i, k]);
  return <Animated.View style={[style, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }) }] }]}>{children}</Animated.View>;
}

/* 종목 칩: 검은 알약 (원본 x-pill · .45s 반동) — 자리가 모자라면 다음 줄 */
function PillChips({ items, value, onChange }: { items: { key: string; label: string }[]; value: string; onChange: (k: string) => void }) {
  const k = useMotionK();
  const [lay, setLay] = useState<Record<string, { x: number; y: number; w: number; h: number }>>({});
  const [x] = useState(() => new Animated.Value(0));
  const [y] = useState(() => new Animated.Value(0));
  const [w] = useState(() => new Animated.Value(0));
  const cur = lay[value];
  useEffect(() => {
    if (!cur) return;
    const a = Animated.parallel([
      Animated.timing(x, { toValue: cur.x, duration: 450 * k, easing: curve.spring, useNativeDriver: false }),
      Animated.timing(w, { toValue: cur.w, duration: 450 * k, easing: curve.spring, useNativeDriver: false }),
      Animated.timing(y, { toValue: cur.y, duration: 450 * k, easing: curve.ease, useNativeDriver: false }),
    ]);
    a.start();
    return () => a.stop();
  }, [cur, x, y, w, k]);
  return (
    <View style={st.chips}>
      {cur ? <Animated.View style={[st.xpill, { left: x, top: y, width: w, height: cur.h }]} /> : null}
      {items.map((c) => {
        const on = c.key === value;
        return (
          <Pressable
            key={c.key || 'all'}
            onLayout={(e) => {
              const l = e.nativeEvent.layout;
              setLay((o) => (o[c.key]?.x === l.x && o[c.key]?.y === l.y && o[c.key]?.w === l.width ? o : { ...o, [c.key]: { x: l.x, y: l.y, w: l.width, h: l.height } }));
            }}
            onPress={() => onChange(c.key)}
            style={[st.chip, !on && { backgroundColor: '#FFFFFF' }]}
          >
            {({ hovered }: Hover) => <Text style={[st.chipT, { color: on ? '#FFFFFF' : hovered ? '#191F28' : '#8F8F8F' }]}>{c.label}</Text>}
          </Pressable>
        );
      })}
    </View>
  );
}

/* 종류 알약 (원본 data-topics: 흰 알약 · 고른 칸 #F2F3F4) */
function Topics({ pool, topic, setTopic }: { pool: UpdateItem[]; topic: KindFilter; setTopic: (t: KindFilter) => void }) {
  const k = useMotionK();
  const [lay, setLay] = useState<Partial<Record<KindFilter, { x: number; w: number }>>>({});
  const [x] = useState(() => new Animated.Value(0));
  const [w] = useState(() => new Animated.Value(0));
  const cur = lay[topic];
  useEffect(() => {
    if (!cur) return;
    const a = Animated.parallel([Animated.timing(x, { toValue: cur.x, duration: 450 * k, easing: curve.spring, useNativeDriver: false }), Animated.timing(w, { toValue: cur.w, duration: 450 * k, easing: curve.spring, useNativeDriver: false })]);
    a.start();
    return () => a.stop();
  }, [cur, x, w, k]);
  return (
    <View style={st.topics}>
      {cur ? <Animated.View style={[st.tpill, { left: x, width: w }]} /> : null}
      {KINDS.map((t) => (
        <Pressable
          key={t}
          onLayout={(e) => {
            const l = e.nativeEvent.layout;
            setLay((o) => (o[t]?.x === l.x && o[t]?.w === l.width ? o : { ...o, [t]: { x: l.x, w: l.width } }));
          }}
          onPress={() => setTopic(t)}
          accessibilityState={{ selected: topic === t }}
          style={st.topic}
        >
          {({ hovered }: Hover) => (
            <Text style={[st.topicT, { color: topic === t || hovered ? '#15171A' : '#8B95A1' }]}>
              {t}
              {t !== '전체' ? <Text style={{ fontWeight: '500' }}> {pool.filter((u) => u.kind === t).length}</Text> : null}
            </Text>
          )}
        </Pressable>
      ))}
    </View>
  );
}

/* 소식 줄 — 누르면 AI 요약 · 원문 근거 · 연결된 내 메모 (원본 Row) */
function Row({ u, p, name, logo }: { u: UpdateItem; p: WebUpdatesProps; name: string; logo?: boolean }) {
  const [open, setOpen] = useState(false);
  const s = p.stocks.find((x) => x.stock_code === u.stock_code);
  const ver = versionsOf(u.memo_id).find((v) => v.version === u.memo_version);
  const mi = u.quote && u.quote_mark ? u.quote.indexOf(u.quote_mark) : -1;
  return (
    <View style={st.rowWrap}>
      <Pressable
        onPress={() => {
          setOpen((o) => !o);
          if (u.unread) p.onMarkRead([u.id], true);
        }}
        accessibilityState={{ expanded: open }}
        style={({ hovered }: Hover) => [st.row, hovered && { backgroundColor: '#F7F8FA' }]}
      >
        {logo && s ? <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={24} variant="webSide" radius={7} /> : null}
        <View style={[st.kind, { backgroundColor: WEB_TAG[u.kind].bg }]}>
          <Text style={[st.kindT, { color: WEB_TAG[u.kind].ink }]}>{u.kind}</Text>
        </View>
        <Text style={[st.rowT, { fontWeight: u.unread ? '700' : '500' }]} numberOfLines={1}>
          {u.headline}
        </Text>
        <Text style={st.ago}>{ago(u.at, p.now)}</Text>
        <View style={[st.dot, !u.unread && { opacity: 0 }]} accessibilityLabel={u.unread ? '안 읽음' : undefined} />
      </Pressable>
      <Collapse open={open} duration={450}>
        <View style={st.fold}>
          <Text style={st.sum}>{u.summary}</Text>
          {u.kind === '공시' && u.quote ? (
            <View style={st.quote}>
              <Text style={st.quoteT}>
                <Text style={st.quoteL}>요약 · 원문 근거 </Text>
                {mi >= 0 && u.quote_mark ? (
                  <>
                    {u.quote.slice(0, mi)}
                    <Text style={st.qMark}>{u.quote_mark}</Text>
                    {u.quote.slice(mi + u.quote_mark.length)}
                  </>
                ) : (
                  u.quote
                )}
              </Text>
            </View>
          ) : null}
          {u.kind === '주가' && u.price ? (
            <View style={st.priceBox}>
              <Spark closes={u.price.closes} up={u.price.closes[u.price.closes.length - 1] >= u.price.closes[0]} />
              <Text style={st.priceCap}>{name} 최근 10거래일 종가 · 전일 확정 종가로 코드가 계산했어요</Text>
            </View>
          ) : null}
          <View style={st.srcRow}>
            <Text style={st.src}>
              {u.source.split(' · ')[0]} · {mmdd(u.at)}
              {u.kind !== '주가' ? ' · AI가 원문에 있는 내용만 골라 적었어요' : ''}
            </Text>
            {u.kind !== '주가' && u.url ? (
              <Pressable onPress={() => p.onOpenSource(u)}>
                <Text style={st.srcLink}>{u.kind === '공시' ? '원문 보기 ↗' : '원문 기사 열기 ↗'}</Text>
              </Pressable>
            ) : null}
          </View>
          <View style={st.memoRow}>
            <View style={st.flexMin}>
              <Text style={st.memoL}>연결된 내 메모 · 작성 당시 {ver ? mmdd(ver.saved_at) : ''}</Text>
              <Text style={st.memoT} numberOfLines={1}>
                {u.memo_title}
              </Text>
            </View>
            <Pressable onPress={() => p.onOpenEvidence(u)} accessibilityRole="button" style={({ hovered }: Hover) => [st.memoBtn, hovered && { backgroundColor: '#F9F9F9' }]}>
              <Text style={st.memoBtnT}>근거 자세히 보기</Text>
            </Pressable>
          </View>
          {!u.memo_title ? <Text style={st.src}>이 소식과 연결된 메모가 없어요 · {name}{josa(name)} 지켜보는 메모에 AI 연결을 켜면 비슷한 소식을 모아 드려요</Text> : null}
        </View>
      </Collapse>
    </View>
  );
}

/** 최근 종가 작은 선 (원본 Spark 220×64 · 아래 44 점선) */
function Spark({ closes, up }: { closes: number[]; up: boolean }) {
  const cl = closes.slice(-10);
  const mn = Math.min(...cl);
  const mx = Math.max(...cl);
  const pts = cl.map((v) => 6 + ((mx - v) / (mx - mn || 1)) * 44);
  return (
    <Svg width="100%" height={64} viewBox="0 0 220 64" preserveAspectRatio="none" fill="none">
      <Line x1={0} y1={44} x2={220} y2={44} stroke="#9AA0AA" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
      <Path d={pts.map((y, i) => `${i ? 'L' : 'M'}${(i * 216) / Math.max(1, pts.length - 1) + 2} ${y.toFixed(1)}`).join('')} stroke={up ? '#E5484D' : '#2F6BDB'} strokeWidth={2} strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </Svg>
  );
}

const st = StyleSheet.create({
  root: { flex: 1 },
  flex: { flex: 1 },
  flexMin: { flex: 1, minWidth: 0 },
  page: { width: 860, gap: 32, paddingTop: 32, paddingBottom: 32 },
  head: { width: '100%', paddingTop: 24, flexDirection: 'row', gap: 16 },
  headL: { height: 52, flex: 1, minWidth: 0, gap: 4 },
  title: { ...fpx(26, 35), fontWeight: '700', letterSpacing: -0.26, color: '#16171A' },
  sub: { ...fpx(14, 21), color: '#575B63' },
  headR: { position: 'absolute', right: 0, top: 25, flexDirection: 'row', alignItems: 'center', gap: 8 },
  unr: { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 999, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E5E7EB', paddingHorizontal: 12, paddingVertical: 6 },
  unrDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#E5484D' },
  unrT: { ...fpx(13, 20), fontWeight: '700', color: '#15171A' },
  readAll: { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 999, backgroundColor: '#E7E7E7', paddingHorizontal: 12, paddingVertical: 6 },
  readAllT: { ...fpx(13, 20), fontWeight: '700', color: '#111111' },
  body: { width: '100%', gap: 24 },
  chipRow: { width: '100%', flexDirection: 'row', alignItems: 'flex-start', gap: 12, zIndex: 30 },
  chips: { flex: 1, minWidth: 0, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-start', gap: 8 },
  xpill: { position: 'absolute', borderRadius: 999, backgroundColor: '#111111' },
  chip: { borderRadius: 20, paddingHorizontal: 16, paddingVertical: 8 },
  chipT: { ...fpx(13, 20), fontWeight: '500' },
  searchWrap: { flexShrink: 0 },
  search: { height: 36, width: 200, flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 999, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E5E7EB', paddingHorizontal: 12 },
  searchOn: { borderWidth: 1.5, borderColor: '#111111', paddingHorizontal: 11.5 },
  searchIn: { flex: 1, minWidth: 0, ...fpx(13, 20), color: '#16171A', paddingVertical: 0, outlineWidth: 0 },
  drop: { position: 'absolute', right: 0, top: 44, zIndex: 30, width: 260, borderRadius: 14, borderWidth: 1, borderColor: '#E5E8EB', backgroundColor: '#FFFFFF', padding: 6, shadowColor: '#1F2E54', shadowOpacity: 0.18, shadowRadius: 28, shadowOffset: { width: 0, height: 12 }, elevation: 8 },
  dropNone: { paddingHorizontal: 12, paddingVertical: 12, ...fpx(13, 20), color: '#8B95A1' },
  dropRow: { height: 40, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderRadius: 10, paddingHorizontal: 12 },
  dropN: { flexShrink: 1, ...fpx(14, 20), fontWeight: '500', color: '#191F28' },
  dropS: { ...fpx(13, 20), color: '#8B95A1' },
  topics: { alignSelf: 'flex-start', marginTop: -8, flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 999, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E5E7EB', padding: 3 },
  tpill: { position: 'absolute', top: 3, bottom: 3, borderRadius: 999, backgroundColor: '#F2F3F4' },
  topic: { height: 32, borderRadius: 999, paddingHorizontal: 14, justifyContent: 'center' },
  topicT: { ...fpx(13, 20), fontWeight: '700' },
  grid: { width: '100%', flexDirection: 'row', flexWrap: 'wrap', gap: 16 },
  card: { width: 422, gap: 14, overflow: 'hidden', borderRadius: 16, borderWidth: 1, borderColor: '#E5E8EB', backgroundColor: '#FFFFFF', padding: 20 },
  nameBtn: { alignSelf: 'flex-start', marginHorizontal: -4, marginVertical: -2, flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 8, paddingHorizontal: 4, paddingVertical: 2 },
  cardName: { ...fpx(20, 29), fontWeight: '700', color: '#191F28' },
  hold: { borderRadius: 6, backgroundColor: '#E8EDF5', paddingHorizontal: 8, paddingVertical: 3 },
  holdT: { ...fpx(13, 20), fontWeight: '500', color: '#000000' },
  code: { ...fpx(13, 20), color: '#6B7684' },
  div: { height: 1, width: '100%', backgroundColor: '#E5E8EB' },
  empty: { ...fpx(14, 21), fontWeight: '500', color: '#8B95A1' },
  more: { ...fpx(13, 20), fontWeight: '700', color: '#575B63' },
  list: { width: '100%', overflow: 'hidden', borderRadius: 16, borderWidth: 1, borderColor: '#E5E8EB', backgroundColor: '#FFFFFF' },
  listRow: { width: '100%', paddingHorizontal: 20, paddingVertical: 14 },
  listLine: { borderTopWidth: 1, borderTopColor: '#E5E8EB' },
  listEmpty: { paddingHorizontal: 20, paddingVertical: 16 },
  rowWrap: { width: '100%' },
  row: { width: '100%', flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 10, paddingVertical: 2 },
  kind: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  kindT: { ...fpx(13, 20), fontWeight: '500' },
  rowT: { flex: 1, minWidth: 0, ...fpx(14, 21), color: '#191F28' },
  ago: { ...fpx(13, 20), color: '#6B7684' },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#E5484D' },
  fold: { marginTop: 8, gap: 12, borderRadius: 12, backgroundColor: '#F7F8FA', padding: 16 },
  sum: { ...fpx(14, 21), color: '#333D4B' },
  quote: { borderRadius: 10, backgroundColor: '#FFFFFF', paddingHorizontal: 12, paddingVertical: 10, borderLeftWidth: 3, borderLeftColor: '#15171A' },
  quoteT: { ...fpx(14, 21), color: '#575B63' },
  quoteL: { ...fpx(13, 21), fontWeight: '700', color: '#8B95A1' },
  qMark: { fontWeight: '700', color: '#15171A', textDecorationLine: 'underline', textDecorationColor: '#FFD34D' },
  priceBox: { gap: 4, borderRadius: 10, backgroundColor: '#FFFFFF', paddingHorizontal: 12, paddingVertical: 8 },
  priceCap: { ...fpx(13, 20), color: '#575B63' },
  srcRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  src: { flexShrink: 1, ...fpx(13, 20), color: '#8B95A1' },
  srcLink: { ...fpx(13, 20), fontWeight: '700', color: '#15171A', textDecorationLine: 'underline' },
  memoRow: { flexDirection: 'row', alignItems: 'center', gap: 12, borderTopWidth: 1, borderTopColor: '#E8ECF3', paddingTop: 12 },
  memoL: { ...fpx(13, 20), color: '#8B95A1' },
  memoT: { ...fpx(14, 21), fontWeight: '700', color: '#15171A' },
  memoBtn: { height: 36, borderRadius: 10, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E5E7EB', paddingHorizontal: 12, justifyContent: 'center' },
  memoBtnT: { ...fpx(13, 20), fontWeight: '700', color: '#15171A' },
  end: { width: '100%', alignItems: 'center', gap: 4, paddingTop: 8 },
  endT: { ...fpx(14, 21), fontWeight: '500', color: '#8B95A1' },
  disc: { width: '100%', textAlign: 'center', ...fpx(13, 20), color: '#9A9EA7' },
  nudge: { position: 'absolute', left: 0, right: 0, bottom: 28, alignItems: 'center' },
});
