import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View, type ViewStyle } from 'react-native';
import Svg, { Ellipse, G, Path, Polygon, Line, Rect, Circle } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { FixedFrame } from '@/ui/layout/web/FixedFrame';
import { seg, useProgress } from '@/ui/motion/useProgress';
import { MouseArea } from '@/ui/shared/MouseArea';
import { NudgePill } from '@/ui/shared/NudgePill';
import { WebStockHead } from '@/ui/shared/StockHead';
import { fpx, webColor } from '@/ui/theme';
import type { CompanyInfoProps, CompanyQuarter } from '../CompanyInfo.types';
import { HEALTH_KEYS, healthScore, healthVal, jo, mmddOf, won } from '../companyFormat';
import type { Candle } from '@/types/models';
import { useNudge } from '@/store/nudge';

type Hover = { pressed: boolean; hovered?: boolean };
type TipCtl = { open: string | null; set: (k: string | null) => void };

/* 원본 web company.tsx — 860 고정 틀 (Figma 7 의 690 을 가로만 넓힘). 아래 숫자는 원본 좌표 그대로 */
const CW = 860;
const IW = 810;
const FX = IW / 640;
const PX = 816 / 646;
const QX = CW / 690;

/**
 * 웹 기업정보 (원본 web/src/screens/company.tsx CompanyInfo · Figma 2.5 7 · 7.1 도움말 · 7.2 그래프 호버)
 * 종목 머리 · [보드 | 기업 정보] · 기업 개요 · 주가·거래량 (최대 캔들 42개 · 가까운 캔들 정보 상자) · 시세정보·투자정보 (52주 막대 · ? 도움말)
 * 실적 (매출·영업이익·당기순이익 · 막대 hover 말풍선) · 수익성 (영업이익률·순이익률·ROE) · 기업 건전성 (레이더 · 지표 고르기)
 */
export function WebCompanyInfo(p: CompanyInfoProps) {
  const [k, setK] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  /* 넛지 닫은 상태는 한 곳(store/nudge)에 — 다시 들어와도 안 뜸 · 사용법 안내 중엔 숨김 */
  const nudgeS = useNudge('info');
  const nudge = nudgeS.show;
  const setNudge = (v: boolean) => {
    if (!v) nudgeS.hide();
  };
  const ctl = { open, set: setOpen };
  return (
    <View style={st.root}>
      <ScrollView style={st.flex} showsVerticalScrollIndicator={false}>
        <FixedFrame onScale={setK}>
          <View style={st.page}>
            <WebStockHead {...p.stock} />
            <View style={st.tabs}>
              {(['board', 'company'] as const).map((t) => (
                <Pressable key={t} onPress={() => t === 'board' && p.onChangeTab('board')} accessibilityRole="tab" accessibilityState={{ selected: t === 'company' }} style={[st.tab, t === 'company' ? st.tabOn : st.tabOff]}>
                  {({ hovered }: Hover) => <Text style={[st.tabT, { color: t === 'company' ? '#FFFFFF' : hovered ? webColor.strong : webColor.mute }]}>{t === 'board' ? '보드' : '기업 정보'}</Text>}
                </Pressable>
              ))}
            </View>
            {/* 도움말이 열려 있으면 바깥을 눌러 닫음 (원본 document mousedown) */}
            {open ? <Pressable style={[StyleSheet.absoluteFill, { zIndex: 20 }]} onPress={() => setOpen(null)} accessibilityLabel="도움말 닫기" /> : null}
            {p.preparing ? (
              <View style={[st.card, { padding: 24 }]}>
                <Text style={st.h20}>{p.stock.name} 기업정보는 준비 중이에요</Text>
              </View>
            ) : (
              <View style={st.body}>
                <View style={[st.card, st.ovCard]}>
                  <Text style={st.h20}>기업 개요</Text>
                  <Text style={st.ovT}>{p.profile.overview}</Text>
                </View>
                {/* 도움말이 다음 카드에 가려지지 않게 감싼 줄째 위로 (2026-11-21) */}
                <View style={[st.g24, { zIndex: open && HELP_SMALL[open] ? 30 : 0 }]}>
                  <PriceChart p={p} k={k} />
                  <Quote p={p} ctl={ctl} />
                </View>
                <Financials all={p.quarters} ctl={ctl} k={k} />
                <View style={st.g24}>
                  <Profit all={p.quarters} ctl={ctl} />
                  <Health p={p} />
                </View>
              </View>
            )}
          </View>
        </FixedFrame>
      </ScrollView>
      {nudge && p.onNudge && !p.preparing ? (
        <View style={st.nudge} pointerEvents="box-none">
          <NudgePill text="공시·재무 읽기 어려우셨죠? 핵심만 정리해 드려요" onGo={() => { setNudge(false); p.onNudge?.(); }} onClose={() => setNudge(false)} />
        </View>
      ) : null}
    </View>
  );
}

/* ---------- 공통 ---------- */
const TIPBOX: ViewStyle = { position: 'absolute', zIndex: 30, borderRadius: 16, borderWidth: 1, borderColor: '#DEEAF5', backgroundColor: '#FFFFFF', shadowColor: '#1F2E54', shadowOpacity: 0.1, shadowRadius: 24, shadowOffset: { width: 0, height: 8 }, elevation: 6 };
/** 원본 HelpBtn: 14 · 16 · 18 동그라미 (테두리 #E8ECF3 · #EEF3F8 · ? 11·13 bold #747D8D) */
function HelpBtn({ id, ctl, size = 14, label }: { id: string; ctl: TipCtl; size?: 14 | 16 | 18; label: string }) {
  return (
    <Pressable onPress={() => ctl.set(ctl.open === id ? null : id)} accessibilityRole="button" accessibilityLabel={`${label} 설명`} accessibilityState={{ expanded: ctl.open === id }} style={({ hovered }: Hover) => [st.help, { width: size, height: size, borderRadius: size / 2, backgroundColor: hovered ? '#E3EAF2' : '#EEF3F8' }]}>
      <Text style={[st.helpT, { fontSize: size === 14 ? 11 : 13 }]}>?</Text>
    </Pressable>
  );
}
function X({ onPress }: { onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel="닫기">
      {({ hovered }: Hover) => <Text style={[st.x, hovered && { color: '#191F28' }]}>×</Text>}
    </Pressable>
  );
}

/* ---------- 주가 · 거래량 (원본 PriceChart: 카드 349 · 816×266 · 최대 캔들 42 · 안내선·정보 상자는 앱처럼 가까운 캔들에 붙음) ---------- */
const GRID_Y = [17.6, 57.1, 96.6, 136.2, 175.7];
const GRID_X = [4, 101, 199, 296, 393, 491, 588];
const NC = 42;
const PLOT_L = 4 * PX;
const PLOT_R = 588 * PX;
const MAX_CONTENT = { width: 'max-content' } as unknown as ViewStyle;
function PriceChart({ p, k }: { p: CompanyInfoProps; k: number }) {
  const all = p.candles['3M'];
  if (!all.length)
    return (
      <View style={[st.card, { height: 349 }]}>
        <View style={{ position: 'absolute', left: 22, top: 25, width: 816, height: 300 }}>
          <Text style={st.h20}>주가 · 거래량</Text>
          <View style={st.priceEmpty}>
            <Text style={st.priceEmptyT}>시세를 불러오지 못했어요</Text>
          </View>
        </View>
      </View>
    );
  return <PriceChartBody all={all} k={k} />;
}

function PriceChartBody({ all, k }: { all: Candle[]; k: number }) {
  const cs = all.slice(-NC);
  const first = all.length - cs.length;
  /* 42개보다 적으면 간격은 그대로, 최신 캔들을 오른쪽 끝에 */
  const slot = NC - cs.length;
  const lo0 = Math.min(...cs.map((c) => c.low));
  const hi0 = Math.max(...cs.map((c) => c.high));
  /* 고가 = 저가면(거래정지·캔들 1개) 위아래 여백을 따로 줌 */
  const padP = (hi0 - lo0) * 0.08 || Math.max(1, hi0 * 0.01);
  const lo = lo0 - padP;
  const hi = hi0 + padP;
  const vmax = Math.max(1, ...cs.map((c) => c.volume));
  const PY = (v: number) => GRID_Y[0] + ((hi - v) / (hi - lo)) * (GRID_Y[4] - GRID_Y[0]);
  const CXp = (i: number) => 11 + ((i + slot) * (581 - 11)) / (NC - 1);
  const t = useProgress(true, 900);
  const last = cs.length - 1;
  const [hov, setHov] = useState<number | null>(null);
  const [boxW, setBoxW] = useState(0);
  const at = hov == null ? null : Math.min(hov, last);
  const d = at == null ? null : cs[at];
  const hx = at == null ? 0 : CXp(at) * PX;
  const prev = at == null ? undefined : all[first + at - 1]?.close;
  const pct = d && prev ? ((d.close - prev) / prev) * 100 : null;
  /* 상자는 선 오른쪽, 넘치면 왼쪽으로 뒤집고 차트 안으로 제한 */
  const boxRight = hx + 10;
  const boxX = Math.max(PLOT_L, Math.min(PLOT_R - boxW, boxRight + boxW <= PLOT_R ? boxRight : hx - 10 - boxW));
  const labels = [0, 1, 2, 3, 4].map((j) => {
    const v = hi - ((hi - lo) * j) / 4;
    const u = v > 100000 ? 1000 : v > 10000 ? 100 : 10;
    return [Math.round(v / u) * u, GRID_Y[j] - 5.6] as const;
  });
  const dates = [...new Set([0, 1, 2, 3, 4, 5].map((j) => Math.round((j * last) / 5.3)))].map((i) => [mmddOf(cs[i].date), CXp(i) - 7] as const);
  return (
    <View style={[st.card, { height: 349 }]}>
      <View style={{ position: 'absolute', left: 22, top: 25, width: 816, height: 300 }}>
        <Text style={st.h20}>주가 · 거래량</Text>
        <View style={{ position: 'absolute', left: 0, top: 34, width: 816, height: 266 }}>
          <Svg width={816} height={266}>
            {GRID_Y.map((y) => (
              <Rect key={y} x={PLOT_L} y={y} width={584 * PX} height={1} fill="#E5EBF2" />
            ))}
            {GRID_X.map((x) => (
              <Rect key={x} x={x * PX} y={17.6} width={0.6} height={158.1} fill="#E5EBF2" />
            ))}
            <Rect x={PLOT_L} y={244} width={584 * PX} height={1} fill="#E5EBF2" />
            {cs.map((c, i) => {
              const up = c.close >= c.open;
              const col = up ? '#F04545' : '#3B82F5';
              const bt = PY(Math.max(c.open, c.close));
              const bb = PY(Math.min(c.open, c.close));
              const vh = Math.max(2, (c.volume / vmax) * 48);
              const s = seg(t * 900, i * 8, 500);
              return (
                <G key={c.date} opacity={s}>
                  <Rect x={CXp(i) * PX} y={PY(c.high)} width={0.6} height={Math.max(1, PY(c.low) - PY(c.high))} fill={col} />
                  <Rect x={CXp(i) * PX + 0.3 - 5} y={bt} width={10} height={Math.max(1.2, bb - bt)} rx={1} fill={col} />
                  <Rect x={CXp(i) * PX + 0.3 - 5} y={244 - vh * s} width={10} height={vh * s} rx={1} fill={up ? '#F3A9AC' : '#A8C1F3'} />
                </G>
              );
            })}
            {d ? (
              <G>
                <Rect x={hx - 0.3} y={15.2} width={0.6} height={228.8} fill="#7A8594" fillOpacity={0.55} />
                <Rect x={PLOT_L} y={PY(d.close) - 0.5} width={584 * PX} height={1} fill="#7A8594" fillOpacity={0.55} />
                <Circle cx={hx} cy={PY(d.close)} r={4.5} fill="#FFFFFF" stroke="#16171A" strokeWidth={2} />
              </G>
            ) : null}
          </Svg>
          <MouseArea
            width={816}
            height={266}
            scale={k}
            onMove={(x) => {
              const mx = x / PX;
              if (mx < 4 || mx > 588) return setHov(null);
              setHov(Math.max(0, Math.min(last, Math.round(((mx - 11) / (581 - 11)) * (NC - 1)) - slot)));
            }}
            onLeave={() => setHov(null)}
            style={{ left: 0, top: 0 }}
          />
          {labels.map(([v, y]) => (
            <Text key={v} pointerEvents="none" numberOfLines={1} style={[st.lbl11, { position: 'absolute', top: y, left: 596 * PX, width: 62 }]}>
              {won(v)}
            </Text>
          ))}
          <Text pointerEvents="none" style={[st.vol, { left: 4 }]}>
            거래량
          </Text>
          <Text pointerEvents="none" style={[st.vol, st.volV, { left: 40 }]}>
            {won((d ?? cs[last]).volume)}
          </Text>
          {dates.map(([date, x]) => (
            <Text key={date} pointerEvents="none" style={[st.lbl11, { position: 'absolute', top: 254, left: x * PX }]}>
              {date}
            </Text>
          ))}
          {d ? (
            <>
              <View pointerEvents="none" style={[st.priceDate, { left: Math.max(PLOT_L, Math.min(PLOT_R - 48, hx - 24)) }]}>
                <Text style={st.tagD}>{mmddOf(d.date)}</Text>
              </View>
              <View pointerEvents="none" onLayout={(e) => setBoxW(e.nativeEvent.layout.width)} style={[st.priceTip, MAX_CONTENT, { left: boxX, opacity: boxW ? 1 : 0 }]}>
                <Text style={st.priceTipT} numberOfLines={1}>
                  <Text style={st.priceTipB}>{mmddOf(d.date)} 일봉</Text> · 종가 {won(d.close)}
                  {pct == null ? null : <Text style={{ color: pct < 0 ? '#8FB0FF' : '#FF8A8E' }}> {`${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`}</Text>}
                </Text>
                <Text style={st.priceTipT} numberOfLines={1}>
                  시 {won(d.open)} · 고 {won(d.high)} · 저 {won(d.low)} · 거래량 {won(d.volume)}주
                </Text>
              </View>
            </>
          ) : null}
        </View>
      </View>
    </View>
  );
}

/* ---------- 시세정보 · 투자정보 (원본 Quote: 카드 230 · 왼쪽 6칸 · 52주 막대 · 오른쪽 6칸 + ?) ---------- */
const HELP_SMALL: Record<string, [string, string]> = {
  PER: ['PER · 주가수익비율', '이익에 비해 주가가 얼마나 높은지 보여줘요.\n계산: 주가 ÷ 주당순이익(EPS)'],
  EPS: ['EPS · 주당순이익', '회사가 벌어들인 순이익 중 보통주 한 주에 해당하는 금액이에요.\n직전 사업연도(사업보고서) 기준이에요. 한국투자증권 제공 값'],
  PBR: ['PBR · 주가순자산비율', '순자산에 비해 주가가 얼마나 높은지 보여줘요.\n계산: 주가 ÷ 주당순자산(BPS)'],
  BPS: ['BPS · 주당순자산', '자산에서 부채를 뺀 순자산 중 보통주 한 주에 해당하는 금액이에요.\n직전 사업연도(사업보고서) 말 기준이에요. 한국투자증권 제공 값'],
  시가총액: ['시가총액', '주식시장에서 평가하는 기업의 전체 주식 가치예요.\n계산: 현재 주가 × 상장주식 수'],
  상장주수: ['상장주수', '거래소에 상장된 주식의 총수예요. 실제 시장에서 거래 가능한 유통주식 수와는 다를 수 있어요.'],
};
function Quote({ p, ctl }: { p: CompanyInfoProps; ctl: TipCtl }) {
  const q = p.profile;
  const price = p.stock.price;
  const L: [string, string, boolean][] = [
    ['전일', won(q.prev_close), false],
    ['시가', won(q.open), q.open > q.prev_close],
    ['고가', won(q.high), q.high > q.prev_close],
    ['저가', won(q.low), q.low > q.prev_close],
    ['거래량', `${won(q.volume)}주`, false],
    ['거래대금', `${won(q.trading_value / 1e8)}억원`, false],
  ];
  const R: [string, string][] = [
    ['PER', q.per == null ? '—' : `${q.per.toFixed(2)}배`],
    ['EPS', q.eps == null ? '—' : `${won(q.eps)}원`],
    ['PBR', q.pbr == null ? '—' : `${q.pbr.toFixed(2)}배`],
    ['BPS', q.bps == null ? '—' : `${won(q.bps)}원`],
    ['시가총액', jo(q.market_cap / 1e8)],
    ['상장주수', `${won(q.shares_outstanding)}주`],
  ];
  const pos = (price - q.week52_low) / (q.week52_high - q.week52_low || 1);
  const cell = (key: string, v: string, red?: boolean, help?: boolean) => (
    <View key={key} style={[st.cell, ctl.open === key && { zIndex: 40 }]}>
      <View style={st.cellL}>
        <Text style={st.cellK}>{key}</Text>
        {help ? <HelpBtn id={key} ctl={ctl} label={key} /> : null}
      </View>
      <Text style={[st.cellV, red && { color: '#E5484D' }]}>{v}</Text>
      {help && ctl.open === key ? (
        <View style={[TIPBOX, { left: -12, top: 30, width: 218, gap: 6, padding: 12 }]}>
          <View style={st.tipHead}>
            <Text style={st.tipH}>{HELP_SMALL[key][0]}</Text>
            <X onPress={() => ctl.set(null)} />
          </View>
          <Text style={st.tipP}>{HELP_SMALL[key][1]}</Text>
        </View>
      ) : null}
    </View>
  );
  return (
    <View style={[st.card, { height: 230, zIndex: ctl.open && HELP_SMALL[ctl.open] ? 30 : 0 }]}>
      <View style={{ position: 'absolute', left: 21.56, top: 24, width: 270 * QX, gap: 3 }}>
        <View style={{ height: 68 }}>
          <Text style={[st.h20, { position: 'absolute', left: 0, top: 20 }]}>시세정보 · 투자정보</Text>
        </View>
        {[0, 2, 4].map((i) => (
          <View key={i} style={[st.cellRow, { gap: 20 }]}>
            {cell(L[i][0], L[i][1], L[i][2])}
            {cell(L[i + 1][0], L[i + 1][1], L[i + 1][2])}
          </View>
        ))}
      </View>
      <Text numberOfLines={1} style={[st.w52, { left: 343.82 * QX + 46 - 72, top: 40, width: 72, textAlign: 'right' }]}>52주 최저</Text>
      <Text numberOfLines={1} style={[st.w52, st.w52v, { left: 339.33 * QX + 51 - 72, top: 55, width: 72, textAlign: 'right' }]}>{won(q.week52_low)}</Text>
      <Text numberOfLines={1} style={[st.w52, { left: 627.11 * QX, top: 40, width: 72 }]}>52주 최고</Text>
      <Text numberOfLines={1} style={[st.w52, st.w52v, { left: 627.11 * QX, top: 55, width: 72 }]}>{won(q.week52_high)}</Text>
      <View style={{ position: 'absolute', top: 54, height: 6, borderRadius: 3, backgroundColor: '#D1D6DE', left: 396.33 * QX, width: 220 * QX + (QX - 1) * 6 }} />
      <View style={[st.pTag, { left: 396.33 * QX + Math.max(0, Math.min(1.74, pos / 0.254)) * 22.36 * QX }]}>
        <Text style={st.tagT} numberOfLines={1}>{won(price)}</Text>
      </View>
      <View style={{ position: 'absolute', top: 94, left: 307.56 * QX, width: 358.44 * QX + (QX - 1) * 24, gap: 3 }}>
        {[0, 2, 4].map((i) => (
          <View key={i} style={[st.cellRow, { gap: 12 }, ctl.open && [R[i][0], R[i + 1][0]].includes(ctl.open) ? { zIndex: 40 } : null]}>
            {cell(R[i][0], R[i][1], false, true)}
            {cell(R[i + 1][0], R[i + 1][1], false, true)}
          </View>
        ))}
      </View>
    </View>
  );
}

/* ---------- 실적 (원본 Financials: 분기 8개 · 전년 동기 대비 선 · 값이 없으면 —) ---------- */
type FinK = '매출' | '영업이익' | '당기순이익';
const FQ: Record<FinK, { color: string; key: 'revenue' | 'op' | 'net'; help: [string, string, string] }> = {
  매출: { color: '#B9AED8', key: 'revenue', help: ['매출이란?', '상품을 팔거나 서비스를 제공해 벌어들인 금액이에요. 아직 비용을 빼기 전의 금액으로, 기업의 사업 규모를 보여줘요.', '한눈에 · 얼마나 팔았나요?'] },
  영업이익: { color: '#51C38B', key: 'op', help: ['영업이익이란?', '매출에서 제품을 만드는 비용과 판매·관리에 든 비용을 뺀 이익이에요. 본업으로 얼마나 벌었는지 보여주며, 금액이 음수라면 영업손실이에요.', '한눈에 · 본업으로 얼마나 남겼나요?'] },
  당기순이익: { color: '#E8CF7E', key: 'net', help: ['당기순이익이란?', '모든 수익과 비용, 법인세까지 반영한 최종 이익이에요. 본업 외의 손익도 포함하며, 금액이 음수라면 당기순손실이에요.', '한눈에 · 최종적으로 얼마나 남았나요?'] },
};
const CX0 = 70 * FX;
const CX1 = 631 * FX;
const CY0 = 16;
const CY1 = 218;
const BW = 46;
const TIP_W = 159;
const TIP_H = 94;
const qx = (i: number) => CX0 + ((CX1 - CX0) / 8) * (i + 0.5);
const tipLeft = (i: number) => (qx(i) + BW / 2 + 10 + TIP_W <= 810 ? qx(i) + BW / 2 + 10 : qx(i) - BW / 2 - 10 - TIP_W);
function Financials({ all, ctl, k: scale }: { all: CompanyQuarter[]; ctl: TipCtl; k: number }) {
  const [k, setK] = useState<FinK>('매출');
  const [h, setH] = useState<number | null>(null);
  const Q8 = all.slice(-8);
  const F = FQ[k];
  const vals = Q8.map((q) => (q[F.key] == null ? null : (q[F.key] as number) / 10000));
  const yoy = Q8.map((q, i) => {
    const v = q[F.key];
    const pv = all[all.length - 8 + i - 4]?.[F.key];
    return v == null || pv == null || !pv ? null : (v / pv - 1) * 100;
  });
  const nums = vals.filter((x): x is number => x != null);
  const max = nums.length ? Math.max(...nums) : 1;
  const mag = Math.pow(10, Math.floor(Math.log10(max)));
  const step = mag * (max / mag > 5 ? 2 : 1);
  const top = Math.ceil(max / step) * step;
  const ticks = nums.length ? Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step) : [0];
  const y = (v: number) => CY1 - (v / top) * (CY1 - CY0);
  const ys = yoy.filter((x): x is number => x != null);
  const yMax = Math.max(1, ...ys.map(Math.abs));
  const ly = (v: number) => CY0 + 8 + ((yMax - v) / (2 * yMax)) * (CY1 - CY0 - 16);
  const last = vals[7];
  const lastY = yoy[7];
  const lbl = (n: number) => (n === 0 ? '0' : n >= 1 ? `${Number.isInteger(n) ? n : n.toFixed(1)}조` : `${Math.round(n * 10000).toLocaleString('ko-KR')}억`);
  const tipTop = (i: number) => Math.max(0, Math.min(226 - TIP_H, (vals[i] == null ? CY1 : y(vals[i] as number)) - TIP_H / 2));
  const line = yoy.map((v, i) => (v == null ? null : ([qx(i), ly(v)] as const)));
  const pts = line.filter((x): x is readonly [number, number] => !!x);
  const t = useProgress(true, 1000, k);
  return (
    <View style={[st.card, st.pad24, { zIndex: ctl.open === 'fin' ? 30 : 0 }]}>
      <View style={[st.finHead, ctl.open === 'fin' && { zIndex: 30 }]}>
        <View style={st.finTitle}>
          <Text style={st.h20}>실적</Text>
          <HelpBtn id="fin" ctl={ctl} size={18} label="실적" />
          {ctl.open === 'fin' ? (
            <View style={[TIPBOX, { left: 14, top: 32, width: 280, gap: 14, paddingHorizontal: 20, paddingVertical: 18 }]}>
              <View style={st.tipHead}>
                <Text style={[st.tipH, { ...fpx(17, 26) }]}>{F.help[0]}</Text>
                <X onPress={() => ctl.set(null)} />
              </View>
              <Text style={st.tipP}>{F.help[1]}</Text>
              <View style={st.tipBox}>
                <Text style={[st.tipP, { color: '#477BFF' }]}>{F.help[2]}</Text>
              </View>
            </View>
          ) : null}
        </View>
        <Text style={st.sub13}>{Q8[7].label} 기준 · 연결재무제표 · 분기</Text>
      </View>
      <View style={st.pills}>
        {(Object.keys(FQ) as FinK[]).map((key) => (
          <Pressable
            key={key}
            onPress={() => {
              setK(key);
              setH(null);
            }}
            accessibilityRole="tab"
            accessibilityState={{ selected: k === key }}
            style={[st.pillBtn, k === key && { backgroundColor: '#000000' }]}
          >
            {({ hovered }: Hover) => <Text style={[st.pillT, { color: k === key ? '#FFFFFF' : hovered ? '#191F28' : '#8F8F8F' }]}>{key}</Text>}
          </Pressable>
        ))}
      </View>
      <View style={st.sumRow}>
        <View style={st.sumCol}>
          <Text style={st.sub13}>
            {Q8[7].label} {k}
          </Text>
          <Text style={st.sumV}>{last == null ? '—' : jo(last * 10000)}</Text>
        </View>
        <View style={st.sumCol}>
          <Text style={st.sub13}>{all[all.length - 5].label} 대비</Text>
          <Text style={[st.sumV, { color: lastY == null ? '#191F28' : lastY >= 0 ? '#FF3D45' : '#477AFF' }]}>{lastY == null ? '—' : `${lastY >= 0 ? '+' : ''}${lastY.toFixed(2)}%`}</Text>
        </View>
        {!nums.length ? <Text style={[st.sub13, { marginLeft: 'auto', color: '#8B95A1' }]}>이 회사는 {k}을 공시하지 않아요 · 값이 없으면 — 로 보여요</Text> : null}
      </View>
      <View style={{ width: 810, height: 246 }}>
        <Svg width={810} height={246}>
          {ticks.map((tk) => (
            <Rect key={tk} x={CX0} y={y(tk)} width={CX1 - CX0} height={1} fill={tk === 0 ? '#B8BFC8' : '#E5E8EB'} />
          ))}
          {vals.map((v, i) => {
            if (v == null) return null;
            const s = seg(t * 1000, 0, 600);
            const hh = (CY1 - y(v)) * s;
            return <Rect key={i} x={qx(i) - BW / 2} y={CY1 - hh} width={BW} height={hh} rx={2} fill={F.color} opacity={h === null || h === i ? 1 : 0.55} />;
          })}
          {pts.length ? <Path d={pts.map((pt, i) => `${i ? 'L' : 'M'}${pt[0]} ${pt[1]}`).join('')} stroke="#33404B" strokeWidth={1.6} fill="none" strokeDasharray="1200" strokeDashoffset={1200 * (1 - seg(t * 1000, 300, 700))} /> : null}
          {pts.map((pt, i) => (
            <Ellipse key={i} cx={pt[0]} cy={pt[1]} rx={3} ry={3.5} fill="#FFFFFF" stroke="#33404B" strokeWidth={1.5} opacity={seg(t * 1000, 500, 300)} />
          ))}
        </Svg>
        {ticks.map((tk) => (
          <Text key={tk} style={[st.lbl11, { position: 'absolute', top: y(tk) - 6, left: 20 * FX - 18, width: 46, textAlign: 'right' }]}>
            {lbl(tk)}
          </Text>
        ))}
        {!nums.length ? <Text style={st.dash}>—</Text> : null}
        {Q8.map((q, i) => (
          <Text key={q.q} style={[st.lbl11, { position: 'absolute', top: 230, left: qx(i) - 24, width: 48, textAlign: 'center' }]}>
            {q.q}
          </Text>
        ))}
        <MouseArea
          width={CX1 - CX0}
          height={226}
          scale={scale}
          cursor="pointer"
          onMove={(x) => setH(Math.max(0, Math.min(7, Math.floor(x / ((CX1 - CX0) / 8)))))}
          onLeave={() => setH(null)}
          style={{ left: CX0, top: 0 }}
        />
        {h !== null ? (
          <View pointerEvents="none" style={[TIPBOX, { left: tipLeft(h), top: tipTop(h), width: TIP_W, gap: 4, paddingHorizontal: 12, paddingVertical: 10 }]}>
            <Text style={st.tipH}>{Q8[h].label}</Text>
            <Text style={st.fTipV}>{vals[h] == null ? '—' : jo((vals[h] as number) * 10000)}</Text>
            <Text style={[st.sub13, { fontWeight: '500', color: yoy[h] == null ? '#8B95A1' : (yoy[h] as number) >= 0 ? '#FF4047' : '#477AFF' }]}>
              {yoy[h] == null ? '—' : `${(yoy[h] as number) >= 0 ? '+' : ''}${(yoy[h] as number).toFixed(1)}%`} · 전년 동기 대비
            </Text>
          </View>
        ) : null}
      </View>
    </View>
  );
}

/* ---------- 수익성 (원본 Profit: 카드 404 · 분기 8개 · 0% 기준선 · ROA는 11-21에 뺌) ---------- */
const PROFIT = [
  { k: '영업이익률', c: '#000000', key: 'op_margin', help: '매출 중 본업으로 남긴 이익의 비율이에요.\n\n영업이익 ÷ 매출\n× 100' },
  { k: '순이익률', c: '#4A74B8', key: 'net_margin', help: '매출 중 모든 비용과 세금을 뺀 최종 이익의 비율이에요.\n\n당기순이익 ÷ 매출 × 100' },
  { k: 'ROE', c: '#C0392B', key: 'roe', help: '주주의 자본으로 얼마나 이익을 냈는지 보여줘요.\n\n당기순이익(연환산) ÷\n평균 자기자본 × 100' },
] as const; /* ROA는 빼기로 함 (11-21 결정 ③) */
function Profit({ all, ctl }: { all: CompanyQuarter[]; ctl: TipCtl }) {
  const X = (i: number) => (95 + (i * 493) / 7) * FX;
  const Q8 = all.slice(-8);
  const Y = (v: number) => Math.max(10, Math.min(232, 142 - v * 2.1));
  const t = useProgress(true, 1100);
  return (
    <View style={[st.card, st.pad24, { height: 404, zIndex: ctl.open && PROFIT.some((p) => p.k === ctl.open) ? 30 : 0 }]}>
      <View style={st.finHead}>
        <Text style={st.h20}>수익성</Text>
        <Text style={st.sub13}>분기 · {Q8[7].label} 기준</Text>
      </View>
      <View style={st.legend}>
        {PROFIT.map((pf) => {
          const nul = Q8.every((q) => q[pf.key] == null);
          return (
            <View key={pf.k} style={st.legItem}>
              <View style={[st.legDot, { backgroundColor: pf.c }]} />
              <Text style={st.legT}>
                {pf.k}
                {nul ? ' —' : ''}
              </Text>
              <HelpBtn id={pf.k} ctl={ctl} size={16} label={pf.k} />
              {ctl.open === pf.k ? (
                <View style={[TIPBOX, { top: 26, left: '100%', marginLeft: -28, width: 166, gap: 10, paddingHorizontal: 12, paddingVertical: 14 }]}>
                  <Text style={[st.tipH, { ...fpx(14, 21) }]}>{pf.k}</Text>
                  <Text style={st.tipP}>{pf.help}</Text>
                </View>
              ) : null}
            </View>
          );
        })}
      </View>
      <View style={{ width: 810, height: 260 }}>
        <Svg width={810} height={260}>
          {[16, 58, 100, 142, 184, 226].map((y) => (
            <Rect key={y} x={51 * FX} y={y} width={581 * FX} height={1} fill={y === 142 ? '#B8BFC8' : '#E5E8EB'} />
          ))}
          {PROFIT.map((pf, n) => {
            const v = Q8.map((q) => q[pf.key]);
            if (v.every((x) => x == null)) return null;
            const vv = v.map((x) => x ?? 0);
            return (
              <G key={pf.k}>
                <Path d={vv.map((x, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(x).toFixed(1)}`).join('')} stroke={pf.c} strokeWidth={2.5} fill="none" strokeLinejoin="round" strokeDasharray="1200" strokeDashoffset={1200 * (1 - seg(t * 1100, n * 100, 800))} />
                {vv.map((x, i) => (
                  <Circle key={i} cx={X(i)} cy={Y(x)} r={3.5} fill={pf.c} opacity={seg(t * 1100, n * 100 + 500, 300)} />
                ))}
              </G>
            );
          })}
        </Svg>
        {(
          [
            ['60%', 16, 27],
            ['40%', 58, 27],
            ['20%', 100, 27],
            ['0%', 142, 35],
            ['-20%', 184, 21],
            ['-40%', 226, 21],
          ] as const
        ).map(([tx, y, x]) => (
          <Text key={tx} style={[st.lbl11, { position: 'absolute', color: '#6B7684', left: x * FX + (FX - 1) * 10, top: y }]}>
            {tx}
          </Text>
        ))}
        {Q8.map((q, i) => (
          <Text key={q.q} style={[st.lbl11, { position: 'absolute', color: '#6B7684', top: 246, left: X(i) - 20, width: 40, textAlign: 'center' }]}>
            {q.q}
          </Text>
        ))}
      </View>
    </View>
  );
}

/* ---------- 기업 건전성 (원본 Health: 레이더 300 · 지표 이름 누르면 설명 · 오른쪽 목록) ---------- */
const HDESC: Record<string, [string, string]> = {
  부채비율: ['자기자본에 비해 부채가 얼마나 많은지 보여줘요.', '부채 ÷ 자기자본 × 100'],
  유동비율: ['1년 안에 갚을 빚을 1년 안에 현금이 되는 자산으로 얼마나 덮는지예요.', '유동자산 ÷ 유동부채 × 100 · 높을수록 단기 지급 여유가 커요.'],
  당좌비율: ['재고자산을 제외한 유동자산으로 단기 부채를 갚을 여력을 봐요.', '당좌자산 ÷ 유동부채 × 100'],
  이자보상비율: ['본업에서 번 이익으로 이자를 얼마나 감당할 수 있는지 봐요.', '영업이익 ÷ 이자비용'],
  유보율: ['자본금 대비 쌓인 잉여금의 비율이에요.', '(자본잉여금 + 이익잉여금) ÷ 자본금 × 100'],
};
/* 레이더 꼭짓점: 위 부채비율 · 오른쪽 위 유보율 · 오른쪽 아래 이자보상비율 · 왼쪽 아래 당좌비율 · 왼쪽 위 유동비율 */
const AX = ['부채비율', '유보율', '이자보상비율', '당좌비율', '유동비율'];
const LBL: [number, number][] = [
  [128, 42],
  [238, 114],
  [206, 219],
  [49, 219],
  [17, 114],
];
const HX = 40;
const HL = 420;
const HW = 390;
function Health({ p }: { p: CompanyInfoProps }) {
  const [sel, setSel] = useState<string | null>(null);
  const t = useProgress(true, 700);
  const sc = 1 - Math.pow(1 - t, 3);
  const keyOf = (name: string) => HEALTH_KEYS.find((h) => h.k === name)!.key;
  /* 다섯 축을 늘 그린다 (11-23: 11-21 결정 ② 대신). 값이 없는 지표(금융사의 유동·당좌·이자보상비율 등)는
     가운데 점으로 두고 점·라벨을 흐리게 → 금융사는 부채비율·유보율과 가운데를 잇는 삼각형이 된다 */
  const axes = AX.map((name, i) => ({ name, lbl: LBL[i], has: p.health[keyOf(name)] != null }));
  const ang = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / AX.length;
  const R0 = axes.map((_, i) => [150 + Math.cos(ang(i)) * 72, 150 + Math.sin(ang(i)) * 72] as const);
  const pts = R0.map(([x, y], i) => {
    const s = healthScore(keyOf(axes[i].name), p.health[keyOf(axes[i].name)]) * sc;
    return [150 + (x - 150) * s, 150 + (y - 150) * s] as const;
  });
  const ring = (r: number) =>
    axes
      .map((_, i) => `${(150 + Math.cos(ang(i)) * r).toFixed(1)},${(150 + Math.sin(ang(i)) * r).toFixed(1)}`)
      .join(' ');
  const LIST = ['부채비율', '유동비율', '당좌비율', '이자보상비율', '유보율'];
  const hasOf = (name: string) => p.health[keyOf(name)] != null;
  const val = (name: string) => healthVal(keyOf(name), p.health[keyOf(name)]);
  return (
    <View style={[st.card, st.pad24, { height: 404 }]}>
      <View style={st.finHead}>
        <Text style={st.h20}>기업 건전성</Text>
        <Text style={st.sub13}>
          {p.health_as_of.slice(0, 4)}년 {p.health_as_of.slice(5, 7)}월 기준
        </Text>
      </View>
      <View style={{ width: 810, height: 300 }}>
        <Svg width={300} height={300} style={{ position: 'absolute', top: 0, left: HX }}>
          {[18, 36, 54, 72].map((r) => (
            <Polygon key={r} points={ring(r)} fill="none" stroke="#B4B2A9" strokeOpacity={0.55} strokeWidth={0.8} />
          ))}
          {R0.map(([x, y], i) => (
            <Line key={i} x1={150} y1={150} x2={x} y2={y} stroke="#B4B2A9" strokeOpacity={0.55} strokeWidth={0.8} />
          ))}
          <Polygon points={pts.map((q) => q.join(',')).join(' ')} fill="#378ADD" fillOpacity={0.18} stroke="#378ADD" strokeWidth={1.8} />
          {pts.map((q, i) =>
            axes[i].has ? <Circle key={i} cx={q[0]} cy={q[1]} r={sel === axes[i].name ? 4 : 3} fill="#378ADD" stroke="#FFFFFF" strokeWidth={1.5} /> : null,
          )}
        </Svg>
        {axes.map(({ name: a }, i) => (
          <Pressable key={a} onPress={() => setSel(sel === a ? null : a)} accessibilityRole="button" style={{ position: 'absolute', left: axes[i].lbl[0] + HX, top: axes[i].lbl[1] }}>
            {({ hovered }: Hover) => <Text style={[st.hT, !axes[i].has && st.hOff, sel === a || hovered ? { color: '#191F28' } : null, sel === a && { fontWeight: '700' }]}>{a}</Text>}
          </Pressable>
        ))}
        <View style={[st.hLegend, { left: HL }]}>
          <View style={st.hDot} />
          <Text style={[st.sub13, { color: '#6B788C' }]}>{p.stock.name}</Text>
        </View>
        <View style={{ position: 'absolute', top: 34, left: HL, width: HW }}>
          {LIST.map((name) => {
            const on = sel === name;
            return (
              <Pressable key={name} onPress={() => setSel(on ? null : name)} accessibilityRole="button" style={st.hRow}>
                <Text style={[st.hT, !hasOf(name) && st.hOff, on && st.hOn]}>{name}</Text>
                <Text style={[st.hT, !hasOf(name) && st.hOff, on && st.hOn]}>{val(name)}</Text>
              </Pressable>
            );
          })}
        </View>
        <View key={sel ?? 'base'} style={[st.hInfo, { left: HL, width: HW }]}>
          {sel ? (
            <>
              <Text style={st.hInfoB}>
                {sel} · {val(sel)}
              </Text>
              <Text style={[st.hInfoP, { color: '#4E5968' }]}>{HDESC[sel][0]}</Text>
              <Text style={st.hInfoP}>{hasOf(sel) ? HDESC[sel][1] : '이 회사는 이 지표를 계산할 재무 값이 없어요. 은행·보험 같은 금융업은 공시하지 않는 지표예요.'}</Text>
            </>
          ) : (
            <>
              <Text style={st.hInfoB}>{p.stock.name} 재무 건전성</Text>
              <Text style={[st.hInfoP, { color: '#4E5968' }]}>바깥쪽으로 갈수록 안정적이에요. 지표 이름을 누르면 설명이 나와요.{axes.some((x) => !x.has) ? ' 값이 없는 지표는 가운데에 두고 흐리게 보여요.' : ''}</Text>
              <Text style={st.hInfoP}>바깥 테두리는 메모스톡 자체 기준 · 최근 분기 재무제표</Text>
            </>
          )}
        </View>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: webColor.page },
  flex: { flex: 1 },
  page: { width: 860, gap: 20, paddingTop: 56, paddingBottom: 96 },
  tabs: { flexDirection: 'row', gap: 8 },
  tab: { minHeight: 40, borderRadius: 20, paddingHorizontal: 20, justifyContent: 'center' },
  tabOn: { backgroundColor: '#000000' },
  tabOff: { backgroundColor: '#FFFFFF' },
  tabT: { ...fpx(15, 23), fontWeight: '500' },
  body: { gap: 32 },
  g24: { gap: 24 },
  card: { width: CW, borderRadius: 16, borderWidth: 1, borderColor: '#E5E8EB', backgroundColor: '#FFFFFF' },
  pad24: { padding: 24, gap: 20 },
  ovCard: { flexDirection: 'row', alignItems: 'center', gap: 40, padding: 24 },
  h20: { ...fpx(20, 29), fontWeight: '700', color: '#191F28' },
  ovT: { flex: 1, ...fpx(14, 23.1), color: '#191F28' },
  lbl11: { ...fpx(11, 16), color: '#6B788C' },
  vol: { position: 'absolute', top: 184, ...fpx(13, 20), fontWeight: '500', color: '#141A24' },
  volV: { fontWeight: '700', color: '#6B788C' },
  tagT: { ...fpx(13, 20), fontWeight: '700', color: '#FFFFFF' },
  tagD: { ...fpx(11, 16), fontWeight: '500', color: '#FFFFFF' },
  priceDate: { position: 'absolute', top: 247, width: 48, height: 20, borderRadius: 999, backgroundColor: '#16171A', alignItems: 'center', justifyContent: 'center' },
  priceTip: { position: 'absolute', top: GRID_Y[0] + 6, gap: 2, borderRadius: 12, backgroundColor: '#16171A', paddingHorizontal: 12, paddingVertical: 8 },
  priceTipT: { ...fpx(13, 20), color: '#FFFFFF' },
  priceTipB: { fontWeight: '700' },
  priceEmpty: { position: 'absolute', left: 0, top: 34, width: 816, height: 266, alignItems: 'center', justifyContent: 'center' },
  priceEmptyT: { ...fpx(15, 22), color: '#6B788C' },
  help: { borderWidth: 1, borderColor: '#E8ECF3', alignItems: 'center', justifyContent: 'center' },
  helpT: { lineHeight: 14, fontWeight: '700', color: '#747D8D', textAlign: 'center' },
  x: { ...fpx(20, 29), color: '#747D8D' },
  tipHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  tipH: { flex: 1, ...fpx(13, 20), fontWeight: '700', color: '#477BFF' },
  tipP: { ...fpx(13, 20), color: '#747D8D' },
  tipBox: { borderRadius: 9, backgroundColor: '#EEF3F8', paddingHorizontal: 12, paddingVertical: 10 },
  cellRow: { flexDirection: 'row', alignItems: 'flex-start', width: '100%' },
  cell: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: '#E5E8EB' },
  cellL: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  cellK: { ...fpx(13, 20), fontWeight: '500', color: '#6B7684' },
  cellV: { ...fpx(13, 20), fontWeight: '700', color: '#191F28' },
  w52: { position: 'absolute', width: 46, ...fpx(13, 20), color: '#6B788C' },
  w52v: { fontWeight: '700', color: '#141A24' },
  pTag: { position: 'absolute', top: 46, height: 22, width: 67, borderRadius: 11, backgroundColor: '#383B40', alignItems: 'center', justifyContent: 'center' },
  finHead: { width: 810, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  finTitle: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sub13: { ...fpx(13, 20), color: '#6B7684' },
  pills: { alignSelf: 'flex-start', flexDirection: 'row', gap: 4, borderRadius: 24, backgroundColor: '#F2F3F5', padding: 4 },
  pillBtn: { height: 40, borderRadius: 20, paddingHorizontal: 20, justifyContent: 'center' },
  pillT: { ...fpx(15, 23), fontWeight: '500' },
  sumRow: { width: 810, minHeight: 43, flexDirection: 'row', alignItems: 'center', gap: 24 },
  sumCol: { gap: 6 },
  sumV: { ...fpx(14, 21), fontWeight: '700', color: '#191F28' },
  dash: { position: 'absolute', top: 100, left: 0, right: 0, textAlign: 'center', fontSize: 28, lineHeight: 36, fontWeight: '700', color: '#C9CCD2' },
  fTipV: { ...fpx(17, 26), fontWeight: '700', color: '#747D8D' },
  legend: { flexDirection: 'row', alignItems: 'center', gap: 18, zIndex: 5 },
  legItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legDot: { width: 10, height: 10, borderRadius: 5 },
  legT: { ...fpx(13, 20), fontWeight: '500', color: '#6B7684' },
  hT: { ...fpx(13, 20), fontWeight: '500', color: '#333D4B' },
  hOn: { fontWeight: '700', color: '#191F28' },
  hOff: { color: '#B0B8C1' },
  hLegend: { position: 'absolute', top: 10, flexDirection: 'row', alignItems: 'center', gap: 6 },
  hDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#378ADD' },
  hRow: { height: 30, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: '#E5E8EB' },
  hInfo: { position: 'absolute', top: 192, gap: 4, borderRadius: 10, backgroundColor: '#F5F6F8', paddingHorizontal: 12, paddingVertical: 10 },
  hInfoB: { ...fpx(13, 20), fontWeight: '700', color: '#333D4B' },
  hInfoP: { ...fpx(13, 20), color: '#6B788C' },
  nudge: { position: 'absolute', left: 0, right: 0, bottom: 28, alignItems: 'center' },
});
