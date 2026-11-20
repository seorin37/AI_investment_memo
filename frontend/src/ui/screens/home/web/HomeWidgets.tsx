import React, { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Svg, { Circle, ClipPath, Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';
import { Text, TextInput } from '@/components/ui/AppText';
import type { Checklist } from '@/types/models';
import { WebIcon } from '@/ui/icons/Icon';
import { useMotionK } from '@/ui/motion/useMotion';
import { useProgress } from '@/ui/motion/useProgress';
import { StockLogo } from '@/ui/shared/StockLogo';
import { curve, fpx } from '@/ui/theme';
import type { HomeNewsItem, HomeStock, HomeUpdateRow, MarketIndex, MarketKey } from '../Home.types';
import { WEB_RANGES, ago, hm, mkData, mmdd, type WebRange } from '../homeFormat';
import { usePaper } from '@/ui/shared/Dark';

type Hover = { pressed: boolean; hovered?: boolean };
const C = { ink: '#16171A', ink15: '#15171A', ink2: '#575B63', sub: '#6B7078', mute: '#8B95A1', line: '#E5E7EB', bg3: '#F3F4F6' } as const;

/** 원본 Plug12 (12 viewBox · 선 1.1) */
export function Plug12({ size = 12, c = '#16161C' }: { size?: number; c?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 12 12" fill="none">
      <Path d="M4.5 1.5V3.5M7.5 1.5V3.5" stroke={c} strokeWidth={1.1} strokeLinecap="round" />
      <Path d="M3.25 3.5H8.75V5.5C8.75 7.02 7.52 8.25 6 8.25C4.48 8.25 3.25 7.02 3.25 5.5V3.5Z" fill={c} />
      <Path d="M6 8.25V10.5" stroke={c} strokeWidth={1.1} strokeLinecap="round" />
    </Svg>
  );
}

/* ───────── 시장 카드 (원본 home.tsx MarketCardBase: 테두리 #E5E7EB · 라운드 20 · 위 62 · 선 110 · 기간 48) ───────── */
const FLAG = { kospi: 'flagKr', kosdaq: 'flagKr2', usd: 'flagUs' } as const;
export function MarketCardBase({ q, h = 264, usdLabel, onMore, onPress }: { q: MarketIndex; h?: number; usdLabel?: string; onMore: (k: MarketKey) => void; onPress?: () => void }) {
  const [r, setR] = useState<WebRange>('1주');
  const [w, setW] = useState(244);
  const md = mkData(q, r);
  const col = md.up ? '#E5484D' : '#2F6BDB';
  const [ex, ey] = md.pts[md.pts.length - 1];
  const gid = `mg-${q.key}-${h}`;
  /* 원본 .m-line: 왼쪽부터 1s 동안 드러남 (기간을 바꾸면 다시) */
  const t = useProgress(true, 1000, r);
  const e = curve.ease(t);
  return (
    <Pressable onPress={onPress} disabled={!onPress} style={[st.mc, { height: h }]}>
      <View style={st.mcTop}>
        <Pressable onPress={() => onMore(q.key)} accessibilityRole="button" accessibilityLabel={`${q.name} 자세히`} style={({ hovered }: Hover) => [st.more, hovered && { backgroundColor: C.bg3 }]}>
          {({ hovered }: Hover) => (
            <>
              <Text style={[st.moreT, { color: hovered ? C.ink15 : C.mute }]}>자세히</Text>
              <View style={{ width: 12, height: 12 }}>
                <Svg width={12} height={12} viewBox="0 0 12 12" fill="none">
                  <Path d="M4.5 2.5L8 6L4.5 9.5" stroke={hovered ? C.ink15 : C.mute} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
                </Svg>
              </View>
            </>
          )}
        </Pressable>
        <View style={st.row5}>
          <WebIcon name={FLAG[q.key]} size={12} />
          <Text style={st.mcName}>{q.key === 'usd' && usdLabel ? usdLabel : q.name}</Text>
        </View>
        <Text style={st.mcV}>{md.v}</Text>
        <View style={st.row6}>
          <Text style={[st.mcL, { color: col }]}>{md.label}</Text>
          <Text style={st.mcW}>{md.when}</Text>
        </View>
      </View>
      <View style={st.mcChart} onLayout={(ev) => setW(ev.nativeEvent.layout.width)}>
        {/* 11.13: 그래프를 세로로 늘림 (66 → 110). 좌표는 그대로 두고 세로만 늘려 그림 */}
        <Svg width="100%" height={110} viewBox="0 0 218.67 66" preserveAspectRatio="none" style={st.abs}>
          <Defs>
            <LinearGradient id={gid} x1="0" y1="18" x2="0" y2="66" gradientUnits="userSpaceOnUse">
              <Stop offset="0" stopColor={col} stopOpacity={0.18} />
              <Stop offset="1" stopColor={col} stopOpacity={0} />
            </LinearGradient>
            <ClipPath id={`${gid}-c`}>
              <Rect x={-6} y={-6} width={(218.67 + 12) * e} height={80} />
            </ClipPath>
          </Defs>
          <Path d={`M0.35 ${md.base + 0.35}H219`} stroke="#747D8D" strokeWidth={0.7} strokeLinecap="round" strokeDasharray="2 4" opacity={0.25} vectorEffect="non-scaling-stroke" />
          <Path d={`${md.path}V48H0Z`} transform="translate(0 18)" fill={`url(#${gid})`} />
          <Path d={md.path} transform="translate(1 19)" stroke={col} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" fill="none" clipPath={`url(#${gid}-c)`} />
        </Svg>
        <View style={[st.dotO, { borderColor: col, left: (ex / 218.67) * w - 5.5, top: (ey + 18) * (110 / 66) - 5.5 }]} />
        <View style={[st.dotI, { backgroundColor: col, left: (ex / 218.67) * w - 3, top: (ey + 18) * (110 / 66) - 3 }]} />
      </View>
      <View style={st.rseg}>
        {WEB_RANGES.map((x) => (
          <Pressable key={x} onPress={() => setR(x)} accessibilityRole="tab" accessibilityState={{ selected: r === x }} style={[st.rsegB, r === x && st.rsegOn]}>
            {({ hovered }: Hover) => <Text style={[st.rsegT, r === x ? st.rsegTOn : { color: hovered ? C.ink : C.ink2 }]}>{x}</Text>}
          </Pressable>
        ))}
      </View>
    </Pressable>
  );
}

/** 위젯 불러오기 실패 (원본 x.tsx WidgetFail: #F7F8FA · 라운드 16 · 5초 뒤 자동) */
export function WidgetFail({ what, h, onRetry }: { what: string; h: number; onRetry: () => void }) {
  const k = useMotionK();
  const [n, setN] = useState(5);
  useEffect(() => {
    const id = setInterval(() => setN((v) => Math.max(0, v - 1)), 1000 * k);
    return () => clearInterval(id);
  }, [k]);
  useEffect(() => {
    if (n === 0) onRetry();
  }, [n, onRetry]);
  return (
    <View style={[st.fail, { height: h }]}>
      <Svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke="#9AA0AA" strokeWidth={1.8} strokeLinecap="round">
        <Circle cx={12} cy={12} r={9} />
        <Path d="M12 7.5v5.5M12 16.2v.3" />
      </Svg>
      <Text style={st.failT}>{what}를 불러오지 못했어요</Text>
      <Pressable onPress={onRetry} accessibilityRole="button" style={({ hovered }: Hover) => [st.failB, hovered && { backgroundColor: '#F9F9F9' }]}>
        <Text style={st.failBT}>다시 시도 · {n}초 뒤 자동</Text>
      </Pressable>
    </View>
  );
}

export function MarketWidget({ indices, onMore, onUsd, onRetry }: { indices: MarketIndex[] | null; onMore: (k: MarketKey) => void; onUsd: () => void; onRetry: () => void }) {
  return (
    <View style={st.mw}>
      <View style={st.mwHead}>
        <Text style={st.h17}>시장 한눈에 보기</Text>
      </View>
      {indices ? (
        <View style={st.mwRow}>
          {indices.map((q) => (
            <MarketCardBase key={q.key} q={q} onMore={onMore} onPress={q.key === 'usd' ? onUsd : undefined} />
          ))}
        </View>
      ) : (
        <WidgetFail what="시장 정보" h={264} onRetry={onRetry} />
      )}
    </View>
  );
}

/* ───────── 업데이트 (원본 UpdatesWidget: 320×472 · 안쪽 20 · 줄 14 · 고른 줄 #F8F8F8 + 1.5 #111) ───────── */
export function UpdatesWidget({ rows, w = 320, h = 472, onAll, onRow }: { rows: HomeUpdateRow[]; w?: number | `${number}%`; h?: number; onAll: () => void; onRow: (code: string) => void }) {
  const paper = usePaper();
  const total = rows.reduce((a, u) => a + u.new_count, 0);
  const [sel, setSel] = useState(rows[0]?.stock_code ?? '');
  return (
    <View style={[st.uw, { width: w, height: h }]}>
      <View style={st.uwHead}>
        <View style={st.between}>
          <Text style={st.h17}>업데이트</Text>
          <Text style={st.t13s}>새 소식 {total}건</Text>
        </View>
        <Text style={st.t13i}>내가 남긴 메모와 이어진 소식이에요</Text>
      </View>
      <View style={st.uwBody}>
        {rows.length === 0 ? <Text style={st.uwEmpty}>내 종목을 추가하면 여기에 소식이 모여요</Text> : null}
        <ScrollView style={st.flex} contentContainerStyle={st.g10} showsVerticalScrollIndicator={false}>
          {rows.map((u) => {
            const on = sel === u.stock_code;
            return (
              <Pressable key={u.stock_code} onHoverIn={() => setSel(u.stock_code)} onFocus={() => setSel(u.stock_code)} onPress={() => onRow(u.stock_code)} accessibilityRole="button" style={[st.ur, on ? st.urOn : st.urOff]}>
                {/* 11.18: 이름·보유/관심은 늘 한 줄. 자리가 모자라면 오른쪽 상태 글자가 다음 줄로 내려가요 */}
                <View style={st.urTop}>
                  <View style={st.urName}>
                    <StockLogo logo={u.logo} bg={u.logo_bg} ink={u.logo_ink} size={28} variant="webSide" radius={8.4} />
                    <Text style={st.urN} numberOfLines={1}>
                      {u.name}
                    </Text>
                    <View style={st.hold}>
                      <Text style={st.holdT}>{u.status === 'holding' ? '보유' : '관심'}</Text>
                    </View>
                  </View>
                  {u.new_count ? (
                    <View style={st.badge}>
                      <Text style={st.badgeT}>{u.new_count}</Text>
                    </View>
                  ) : (
                    <Text style={[st.t13s, st.ml]}>{u.latest ? '모두 확인했어요' : '연결된 소식 없음'}</Text>
                  )}
                </View>
                {u.latest ? (
                  <View style={[st.urBox, { backgroundColor: on ? '#E7E7E7' : C.bg3 }]}>
                    <View style={st.row6c}>
                      <View style={[st.kind, { borderColor: on ? C.line : '#FFFFFF' }]}>
                        <Text style={st.kindT}>{u.latest.kind}</Text>
                      </View>
                      <Text style={st.urT} numberOfLines={1}>
                        {u.latest.title}
                      </Text>
                    </View>
                    <View style={st.row6c}>
                      <WebIcon name="arrowCorner" size={12} />
                      <View style={[st.mcol, { backgroundColor: paper[u.latest.memo_color].bg }]} />
                      <Text style={st.urM} numberOfLines={1}>
                        {u.latest.memo_title}
                      </Text>
                    </View>
                  </View>
                ) : null}
              </Pressable>
            );
          })}
        </ScrollView>
      </View>
      <Pressable onPress={onAll} accessibilityRole="link" style={{ width: 200 }}>
        <Text style={st.allLink}>전체 업데이트 보기 {'  '}→</Text>
      </Pressable>
    </View>
  );
}

/* ───────── 뉴스 (원본 NewsWidget: 높이 472 · 좌우 24 · 머리 기사 #F3F4F6 · 줄 8개) ───────── */
export function NewsWidget({ items, day, total, now, h = 472, onOpen, style }: { items: HomeNewsItem[]; day: string; total: number; now: string; h?: number; onOpen: (n: HomeNewsItem) => void; style?: StyleProp<ViewStyle> }) {
  const head = items[0];
  const list = items.slice(1, 9);
  return (
    <View style={[st.nw, { height: h }, style]}>
      <View style={st.between}>
        <Text style={[st.h17, { color: C.ink15 }]}>뉴스</Text>
        <Text style={st.t13s}>
          {mmdd(day)} · {total}건
        </Text>
      </View>
      {head ? (
        <Pressable onPress={() => onOpen(head)} accessibilityRole="link" style={({ hovered }: Hover) => [st.nh, { backgroundColor: hovered ? '#ECEEF1' : C.bg3 }]}>
          <View style={st.between}>
            <View style={st.src}>
              <Text style={st.srcT}>{head.src}</Text>
            </View>
            <Text style={st.t13s}>
              {hm(head.at)} · {ago(head.at, now)}
            </Text>
          </View>
          <Text style={st.nhT}>{head.title}</Text>
          <Text style={st.nhO}>원문 읽기 ↗</Text>
        </Pressable>
      ) : null}
      <ScrollView style={st.flex} showsVerticalScrollIndicator={false}>
        {list.map((n) => (
          <Pressable key={n.id} onPress={() => onOpen(n)} accessibilityRole="link" style={({ hovered }: Hover) => [st.nr, hovered && { backgroundColor: '#FAFAFA' }]}>
            <Text style={st.nrT}>{n.at.slice(0, 10) === day ? hm(n.at) : mmdd(n.at)}</Text>
            <View style={st.nrMid}>
              <Text style={st.nrB}>{n.title}</Text>
              <Text style={st.nrS}>{n.src}</Text>
            </View>
            <Text style={st.nrAr}>↗</Text>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}

/* ───────── 체크리스트 (원본 homex.tsx CheckWidget: 종목 칩 · 다 끝내면 '모두 확인했어요!') ───────── */
export function CheckWidget({ stocks, checklists, h = 472, onToggle, onAdd, onEdit }: { stocks: HomeStock[]; checklists: Record<string, Checklist>; h?: number; onToggle: (code: string, id: string) => void; onAdd: (code: string, text: string) => void; onEdit: (code: string) => void }) {
  const [add, setAdd] = useState('');
  const withCl = stocks.filter((s) => checklists[s.stock_code]);
  const [pick, setPick] = useState<string | null>(null);
  const code = pick && stocks.some((s) => s.stock_code === pick) ? pick : (withCl[0] ?? stocks[0])?.stock_code;
  const cl = code ? checklists[code] : undefined;
  const items = cl?.items ?? [];
  const done = items.length > 0 && items.every((c) => c.done);
  return (
    <View style={[st.cw, { height: h }]}>
      <View style={st.between}>
        <Text style={[st.h17, { color: C.ink15 }]}>{cl?.title ?? '체크리스트'}</Text>
        <Text style={st.cwN}>
          {items.filter((c) => c.done).length}/{items.length}
        </Text>
      </View>
      {stocks.length > 0 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={st.chipsWrap} contentContainerStyle={st.chips}>
          {stocks.map((s) => {
            const on = s.stock_code === code;
            const left = checklists[s.stock_code] ? ` ${checklists[s.stock_code].items.filter((c) => !c.done).length}` : '';
            return (
              <Pressable key={s.stock_code} onPress={() => setPick(s.stock_code)} style={({ hovered }: Hover) => [st.chip, { backgroundColor: on ? C.ink15 : hovered ? '#E9EAEC' : C.bg3 }]}>
                <Text style={[st.chipT, { color: on ? '#FFFFFF' : C.ink2 }]}>
                  {s.name}
                  {left}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}
      {done ? (
        <View style={st.yay}>
          <Svg width={16} height={16} viewBox="0 0 16 16" fill="none">
            <Circle cx={8} cy={8} r={7} fill="#1E8E4E" />
            <Path d="M4.8 8.2L7 10.3L11.2 5.9" stroke="white" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" />
          </Svg>
          <Text style={st.yayT}>모두 확인했어요!</Text>
        </View>
      ) : null}
      <ScrollView style={st.flex} showsVerticalScrollIndicator={false}>
        {!stocks.length ? <Text style={st.cwEmpty}>종목을 추가하면 종목별 체크리스트를 쓸 수 있어요</Text> : null}
        {code && !items.length ? <Text style={st.cwEmpty}>{'아직 체크리스트가 없어요\n아래에 확인할 일을 적고 Enter'}</Text> : null}
        {code
          ? items.map((c, i) => (
              <Pressable key={c.id} onPress={() => onToggle(code, c.id)} accessibilityRole="checkbox" accessibilityState={{ checked: c.done }} style={[st.ci, i > 0 && st.ciLine]}>
                <View style={[st.cc, c.done ? { backgroundColor: C.ink15, borderWidth: 0 } : null]}>
                  {c.done ? (
                    <Svg width={11} height={11} viewBox="0 0 12 12" fill="none">
                      <Path d="M2.5 6L4.8 8.3L9.5 3.5" stroke="white" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
                    </Svg>
                  ) : null}
                </View>
                <Text style={[st.ciT, c.done ? st.ciDone : null]} numberOfLines={1}>
                  {c.text}
                </Text>
              </Pressable>
            ))
          : null}
      </ScrollView>
      <View style={st.cwAdd}>
        <TextInput
          editable={!!code}
          value={add}
          onChangeText={setAdd}
          onSubmitEditing={() => {
            if (add.trim() && code) {
              onAdd(code, add.trim());
              setAdd('');
            }
          }}
          submitBehavior="submit"
          placeholder="할 일을 적고 Enter"
          placeholderTextColor={C.mute}
          style={[st.cwIn, !code && { opacity: 0.5 }]}
        />
        {code ? (
          <Pressable onPress={() => onEdit(code)} style={({ hovered }: Hover) => [st.cwEdit, hovered && { backgroundColor: C.bg3 }]}>
            <Text style={st.cwEditT}>편집</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  flex: { flex: 1 },
  abs: { position: 'absolute', left: 0, top: 0, overflow: 'visible' },
  between: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', width: '100%' },
  g10: { gap: 10 },
  ml: { marginLeft: 'auto' },
  h17: { ...fpx(17, 26), fontWeight: '700', letterSpacing: -0.17, color: C.ink },
  t13s: { ...fpx(13, 20), color: C.sub },
  t13i: { ...fpx(13, 20), color: C.ink2 },
  /* 시장 */
  mw: { width: '100%', height: 308, gap: 16 },
  mwHead: { height: 24, flexDirection: 'row', alignItems: 'center', gap: 8 },
  mwRow: { height: 264, flexDirection: 'row', alignItems: 'flex-start', gap: 16 },
  mc: { flex: 1, minWidth: 0, justifyContent: 'space-between', overflow: 'hidden', borderRadius: 20, borderWidth: 1, borderColor: C.line, backgroundColor: '#FFFFFF', paddingHorizontal: 16, paddingVertical: 12 },
  mcTop: { height: 62, width: '100%', gap: 3 },
  more: { position: 'absolute', right: -6, top: -2, height: 28, flexDirection: 'row', alignItems: 'center', gap: 2, borderRadius: 8, paddingHorizontal: 6, zIndex: 2 },
  moreT: { ...fpx(13, 20), fontWeight: '500' },
  row5: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  row6: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  row6c: { flexDirection: 'row', alignItems: 'center', gap: 6, width: '100%' },
  mcName: { ...fpx(13, 20), fontWeight: '500', color: C.ink2 },
  mcV: { ...fpx(26, 35), fontWeight: '700', color: C.ink },
  mcL: { ...fpx(13, 20), fontWeight: '700' },
  mcW: { ...fpx(13, 20), color: C.sub },
  mcChart: { height: 110, width: '100%' },
  dotO: { position: 'absolute', width: 11, height: 11, borderRadius: 6, borderWidth: 1, backgroundColor: '#FFFFFF' },
  dotI: { position: 'absolute', width: 6, height: 6, borderRadius: 3, borderWidth: 1.5, borderColor: '#FFFFFF' },
  rseg: { height: 48, width: '100%', flexDirection: 'row', alignItems: 'flex-start', borderRadius: 14, backgroundColor: C.bg3, padding: 4 },
  rsegB: { height: 40, flex: 1, minWidth: 0, alignItems: 'center', justifyContent: 'center', borderRadius: 12 },
  rsegOn: { backgroundColor: '#FFFFFF' },
  rsegT: { ...fpx(15, 23), fontWeight: '500' },
  rsegTOn: { fontWeight: '700', color: C.ink },
  fail: { width: '100%', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: 16, backgroundColor: '#F7F8FA', paddingHorizontal: 16 },
  failT: { ...fpx(15, 23), fontWeight: '700', color: '#333D4B', textAlign: 'center' },
  failB: { minHeight: 36, borderRadius: 10, backgroundColor: '#FFFFFF', paddingHorizontal: 12, justifyContent: 'center', borderWidth: 1, borderColor: C.line },
  failBT: { ...fpx(14, 20), fontWeight: '700', color: C.ink15 },
  /* 업데이트 */
  uw: { flexShrink: 0, gap: 12, overflow: 'hidden', borderRadius: 20, borderWidth: 1, borderColor: C.line, backgroundColor: '#FFFFFF', padding: 20 },
  uwHead: { width: '100%', gap: 2 },
  uwBody: { flex: 1, minHeight: 0, width: '100%', gap: 10 },
  uwEmpty: { width: '100%', paddingVertical: 24, textAlign: 'center', ...fpx(14, 21), color: C.mute },
  ur: { width: '100%', gap: 10, borderRadius: 14, padding: 14 },
  urOn: { backgroundColor: '#F8F8F8', borderWidth: 1.5, borderColor: '#111111', padding: 12.5 },
  urOff: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: C.line, padding: 13 },
  urTop: { width: '100%', flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', columnGap: 8, rowGap: 4 },
  urName: { flexDirection: 'row', alignItems: 'center', gap: 8, minWidth: 0, maxWidth: '100%', flexShrink: 1 },
  urN: { flexShrink: 1, minWidth: 0, ...fpx(15, 23), fontWeight: '700', color: C.ink },
  hold: { flexShrink: 0, borderRadius: 6, backgroundColor: C.bg3, paddingHorizontal: 6, paddingVertical: 2 },
  holdT: { ...fpx(13, 20), fontWeight: '500', color: C.ink2 },
  badge: { marginLeft: 'auto', minWidth: 22, height: 22, borderRadius: 11, backgroundColor: '#E45D6A', paddingHorizontal: 4, alignItems: 'center', justifyContent: 'center' },
  badgeT: { fontSize: 13, lineHeight: 13, fontWeight: '700', color: '#FFFFFF' },
  urBox: { width: '100%', gap: 6, borderRadius: 10, padding: 10 },
  kind: { borderRadius: 6, borderWidth: 1, backgroundColor: '#FFFFFF', paddingHorizontal: 6, paddingVertical: 1 },
  kindT: { ...fpx(13, 20), fontWeight: '700', color: C.ink2 },
  urT: { flex: 1, minWidth: 0, ...fpx(13, 20), fontWeight: '500', color: C.ink },
  mcol: { width: 10, height: 10, borderRadius: 3, borderWidth: 1, borderColor: 'rgba(22,23,26,0.12)' },
  urM: { flex: 1, minWidth: 0, ...fpx(13, 20), fontWeight: '500', color: '#111111' },
  allLink: { ...fpx(13, 20), fontWeight: '700', letterSpacing: -0.13, color: '#111111', textDecorationLine: 'underline' },
  /* 뉴스 */
  nw: { width: '100%', minWidth: 0, gap: 8, overflow: 'hidden', borderRadius: 20, borderWidth: 1, borderColor: C.line, backgroundColor: '#FFFFFF', paddingHorizontal: 24, paddingBottom: 14, paddingTop: 18 },
  nh: { width: '100%', gap: 8, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12 },
  src: { borderRadius: 10, borderWidth: 1, borderColor: C.line, backgroundColor: '#FFFFFF', paddingHorizontal: 8, paddingVertical: 2 },
  srcT: { ...fpx(13, 20), fontWeight: '500', color: C.ink2 },
  nhT: { width: '100%', ...fpx(17, 26), fontWeight: '700', color: C.ink15 },
  nhO: { ...fpx(13, 20), fontWeight: '700', color: '#111111', textDecorationLine: 'underline' },
  nr: { width: '100%', flexDirection: 'row', alignItems: 'flex-start', gap: 10, borderTopWidth: 1, borderTopColor: C.line, paddingHorizontal: 2, paddingVertical: 9 },
  nrT: { width: 38, flexShrink: 0, ...fpx(13, 20), color: C.sub },
  nrMid: { flex: 1, minWidth: 0, gap: 2 },
  nrB: { width: '100%', ...fpx(14, 21), fontWeight: '500', color: C.ink15 },
  nrS: { ...fpx(13, 20), fontWeight: '500', color: C.ink2 },
  nrAr: { ...fpx(14, 21), fontWeight: '500', color: C.sub },
  /* 체크리스트 */
  cw: { width: '100%', gap: 8, overflow: 'hidden', borderRadius: 20, borderWidth: 1, borderColor: C.line, backgroundColor: '#FFFFFF', paddingHorizontal: 24, paddingBottom: 16, paddingTop: 18 },
  cwN: { ...fpx(13, 20), color: C.sub },
  chipsWrap: { flexGrow: 0, marginHorizontal: -4 },
  chips: { gap: 4, paddingHorizontal: 4, paddingBottom: 4 },
  chip: { height: 32, borderRadius: 999, paddingHorizontal: 12, justifyContent: 'center' },
  chipT: { ...fpx(13, 20), fontWeight: '700' },
  yay: { flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 12, backgroundColor: '#F2F9F4', paddingHorizontal: 12, paddingVertical: 8 },
  yayT: { ...fpx(14, 20), fontWeight: '700', color: '#1E8E4E' },
  cwEmpty: { paddingVertical: 24, textAlign: 'center', ...fpx(14, 21), color: C.mute },
  ci: { height: 44, width: '100%', flexDirection: 'row', alignItems: 'center', gap: 12 },
  ciLine: { borderTopWidth: 1, borderTopColor: '#F0F1F3' },
  cc: { width: 20, height: 20, borderRadius: 10, borderWidth: 1.6, borderColor: '#C9CCD2', alignItems: 'center', justifyContent: 'center' },
  ciT: { flexShrink: 1, ...fpx(15, 23), color: C.ink15 },
  ciDone: { color: '#A0A5AD', textDecorationLine: 'line-through' },
  cwAdd: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cwIn: { height: 44, flex: 1, minWidth: 0, borderRadius: 12, backgroundColor: C.bg3, paddingHorizontal: 16, ...fpx(15, 20), color: C.ink15 },
  cwEdit: { height: 44, borderRadius: 12, paddingHorizontal: 12, justifyContent: 'center' },
  cwEditT: { ...fpx(13, 20), fontWeight: '700', color: C.ink2 },
});
