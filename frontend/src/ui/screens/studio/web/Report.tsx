import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Rect, Stop, Text as SvgText } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { FeatIcon } from '@/ui/layout/web/StudioColumnFrame';
import { FixedFrame } from '@/ui/layout/web/FixedFrame';
import { Sheet } from '@/ui/shared/Sheet';
import { CloseX } from '../../my/web/parts';
import type { mockReport, ReportStock, ReportWatch } from '../Studio.mock';
import type { MadeItem } from '../Studio.types';
import { issueParas, marketParas, quarterLine, reportSummary, sign, stripRefs, valuationCells, won } from '../reportParts';
import { Check } from './AudioPopup';
import { GBtn } from './Credit';
import { Keep } from '@/ui/shared/Dark';

type Hover = { hovered?: boolean; pressed?: boolean };
type Rep = typeof mockReport;
const UPC = '#E5484D', DNC = '#2F6FE0';
const pc = (v: number) => (v >= 0 ? UPC : DNC);
const TR = { letterSpacing: -0.2 };

/** 웹 주간보고서 만들기 창 = 원본 studio.tsx ReportPopup (468) */
export function WebReportPopup({ open, stocks, sub, onClose, onMake, counts = true, preset }: { open: boolean; stocks: ReportStock[]; sub: string; onClose: () => void; onMake: (p: { codes: string[]; market: boolean }) => void; /** 종목별 '공시·뉴스 N' 미리 보기 (실제 모드는 없음) */ counts?: boolean; /** 넛지에서 열 때 미리 고를 종목 (목록에 있는 것만 · 없거나 0개면 전체) */ preset?: string[] }) {
  const all = stocks.map((s) => s.stock_code);
  const [sel, setSel] = useState<string[]>(all);
  const [sum, setSum] = useState(false);
  const [prev, setPrev] = useState(open);
  if (open !== prev) {
    setPrev(open);
    if (open) {
      const pick = preset?.filter((c) => all.includes(c)) ?? [];
      setSel(pick.length ? pick : all);
      setSum(false);
    }
  }
  const want = (q: 'all' | 'own' | 'watch') => stocks.filter((s) => q === 'all' || (q === 'own' ? s.own === '보유' : s.own === '관심')).map((s) => s.stock_code);
  const eq = (a: string[]) => a.length > 0 && a.length === sel.length && a.every((x) => sel.includes(x));
  return (
    <Sheet open={open} onClose={onClose} width={468} scrim="rgba(21,23,26,0.4)" label="주간보고서 만들기">
      <View style={st.pop}>
        <View style={st.ph}>
          <View style={st.phI}><FeatIcon f="report" size={22} /></View>
          <View style={{ flex: 1, minWidth: 0, gap: 2 }}><Text style={st.phH}>주간보고서 만들기</Text><Text style={st.phS}>{sub}</Text></View>
          <CloseX onPress={onClose} />
        </View>
        <View style={{ gap: 14, paddingHorizontal: 22, paddingTop: 4, paddingBottom: 16 }}>
          <View style={st.pickHead}><Text style={st.pickTitle}>보고서에 넣을 종목</Text><Text style={st.pickCount}>{sel.length}개 선택</Text></View>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {([['all', '전체 종목'], ['own', '보유 종목 전체'], ['watch', '관심 종목 전체']] as const).map(([q, l]) => {
              const on = eq(want(q));
              return (
                <Pressable key={q} onPress={() => setSel(want(q))} accessibilityRole="button" accessibilityState={{ selected: on }} style={({ hovered }: Hover) => [st.pre, on ? st.preOn : hovered && { backgroundColor: '#F9F9F9' }]}>
                  <Text style={[st.preT, on && { color: '#FFFFFF' }]}>{l}</Text>
                </Pressable>
              );
            })}
          </View>
          <View style={st.box}>
            {stocks.map((s) => {
              const on = sel.includes(s.stock_code);
              return (
                <Pressable key={s.stock_code} onPress={() => setSel((a) => (on ? a.filter((x) => x !== s.stock_code) : [...a, s.stock_code]))} accessibilityRole="checkbox" accessibilityState={{ checked: on }} style={({ hovered }: Hover) => [st.row, hovered && { backgroundColor: '#F9F9F9' }]}>
                  <Check on={on} />
                  <Text style={st.name} numberOfLines={1}>{s.name}</Text>
                  {counts ? <Text style={st.cnt}>공시 {s.counts.공시} · 뉴스 {s.counts.뉴스}</Text> : null}
                  <View style={st.chip}><Text style={st.chipT}>{s.own}</Text></View>
                </Pressable>
              );
            })}
            <View style={{ height: 1, backgroundColor: '#E8ECF3' }} />
            <Pressable onPress={() => setSum(!sum)} accessibilityRole="checkbox" accessibilityState={{ checked: sum }} style={({ hovered }: Hover) => [st.row, { height: undefined, paddingVertical: 10 }, hovered && { backgroundColor: '#F9F9F9' }]}>
              <Check on={sum} />
              <View style={{ flex: 1, minWidth: 0, gap: 1 }}><Text style={st.name}>국내 증시 주간 요약</Text><Text style={st.cnt}>코스피·코스닥·원/달러 한 주 흐름</Text></View>
              <View style={st.chip}><Text style={st.chipT}>선택</Text></View>
            </Pressable>
          </View>
        </View>
        <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 22, paddingTop: 12, paddingBottom: 20 }}>
          <GBtn h={48} onPress={onClose}>취소</GBtn>
          <GBtn h={48} flex dark disabled={!sel.length} onPress={() => onMake({ codes: all.filter((c) => sel.includes(c)), market: sum })}>보고서 만들기</GBtn>
        </View>
      </View>
    </Sheet>
  );
}

function Logo({ s, size, r }: { s: ReportStock; size: number; r: number }) {
  return <Keep style={{ width: size, height: size, borderRadius: r, backgroundColor: s.logo_bg, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: size > 30 ? 15 : size > 24 ? 15 : 11, lineHeight: size * 0.7, fontWeight: '700', color: s.logo_ink ?? '#FFFFFF' }}>{s.logo}</Text></Keep>;
}

/** 작은 선 (원본 Mini 50×20 · 끝 점) */
function MiniLine({ v, w = 50, h = 20 }: { v: number[]; w?: number; h?: number }) {
  const mn = Math.min(...v), mx = Math.max(...v), c = v[v.length - 1] >= v[0] ? UPC : DNC;
  const pts = v.map((x, i) => [0.9 + (i / Math.max(1, v.length - 1)) * (w - 2), 0.9 + ((mx - x) / (mx - mn || 1)) * (h - 2)] as const);
  const [ex, ey] = pts[pts.length - 1];
  return <Svg width={w + 2} height={h + 2}><Path d={pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(2)} ${p[1].toFixed(2)}`).join('')} stroke={c} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" fill="none" /><Circle cx={ex} cy={ey} r={2.5} fill={c} /></Svg>;
}

const counts = (s: ReportStock) => [s.counts.공시 ? `공시 ${s.counts.공시}` : '', s.counts.뉴스 ? `뉴스 ${s.counts.뉴스}` : ''].filter(Boolean);

/**
 * 웹 주간보고서 요약 (스튜디오 열) = 원본 studio.tsx ReportSum + gen/ReportSummary
 * ← AI 주간보고서 · 머리 · 이번 주 한눈에 · 증시 3칸 · 종목별 흐름 줄 · [자세히 보기] · 안내
 */
export function WebReportSum({ rep, item, stocks, allDefault, onBack, onDetail }: { rep: Rep; item: MadeItem; stocks: ReportStock[]; allDefault: boolean; onBack: () => void; onDetail: () => void }) {
  const lastClose = rep.days[rep.days.length - 1]?.split(' ')[0] ?? rep.range;
  return (
    <ScrollView contentContainerStyle={{ paddingBottom: 24 }} showsVerticalScrollIndicator={false}>
      <View style={st.subHead}>
        <Pressable onPress={onBack} accessibilityRole="button" accessibilityLabel="뒤로" style={{ padding: 4, margin: -4 }}>
          <Svg width={24} height={24} viewBox="0 0 24 24" fill="none"><Path d="M19 12H5M12 5L5 12L12 19" stroke="black" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" /></Svg>
        </Pressable>
        <Text style={st.subHeadT}>AI 주간보고서</Text>
      </View>
      <View style={{ gap: 16, paddingHorizontal: 16, paddingTop: 6 }}>
        <View style={{ gap: 4 }}>
          <Text style={st.sLbl}>MEMO&apos;S 주간보고서 · {rep.week}</Text>
          <Text style={st.sTitle}>{item.title}</Text>
          <Text style={st.sLbl2}>{rep.range} · 거래일 {rep.days.length}일 · {stocks.length}종목</Text>
        </View>
        <View style={st.glance}><Text style={st.glanceH}>이번 주 한눈에</Text><Text keepAll style={st.glanceP}>{reportSummary(stocks, allDefault, rep.summary_default, lastClose)}</Text></View>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {rep.market.map((m) => <View key={m.name} style={st.mk}><Text style={st.sLbl2}>{m.name}</Text><Text style={[st.mkV, { color: pc(m.pct) }]}>{sign(m.pct)}</Text></View>)}
        </View>
        <Text style={st.sH}>종목별 흐름</Text>
        <View style={st.list}>
          {stocks.map((s, i) => {
            const bits = counts(s);
            const memo = s.memos ? (s.memos.length ? `메모 ${s.memos.length}개` : '') : s.memo ? '메모 1개와 연결' : '';
            return (
              <View key={s.stock_code} style={[st.sr, i > 0 && { borderTopWidth: 1, borderTopColor: '#EEF0F3' }]}>
                <Logo s={s} size={28} r={8.4} />
                <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
                  <Text style={st.srN} numberOfLines={1}>{s.name}</Text>
                  <Text keepAll style={st.srS} numberOfLines={2}>{[bits.length ? bits.join(' · ') : '새 소식 없음', memo || (bits.length ? '' : '연결된 메모 없음')].filter(Boolean).join(' · ')}</Text>
                </View>
                <MiniLine v={s.closes} />
                <Text style={[st.srP, { color: pc(s.pct) }]}>{sign(s.pct)}</Text>
              </View>
            );
          })}
        </View>
        <Pressable onPress={onDetail} accessibilityRole="button" style={({ hovered }: Hover) => [st.detail, hovered && { backgroundColor: '#2A2C31' }]}><Text style={st.detailT}>자세히 보기</Text></Pressable>
        <Text keepAll style={st.disc}>공시·뉴스·시세에서 가져온 정보예요. 투자 권유나 주가 예측이 아니에요.</Text>
      </View>
    </ScrollView>
  );
}

/** 넓은 차트 (원본 ReportDetail Chart 760×210 · 지난주 종가 점선 · 소식 난 날 검은 점) */
function DetailChart({ s, days }: { s: ReportStock; days: string[] }) {
  const W = 760, H = 210, v = [s.prev, ...s.closes], mn = Math.min(...v), mx = Math.max(...v), pad = (mx - mn) * 0.15 || mx * 0.01;
  const lo = mn - pad, hi = mx + pad, X = (k: number) => 56 + (k / (v.length - 1)) * (W - 76), Y = (x: number) => 14 + ((hi - x) / (hi - lo)) * (H - 44);
  const c = pc(s.pct), unit = Math.pow(10, Math.floor(Math.log10(Math.max(1, (hi - lo) / 3))));
  const ticks = [0, 1, 2, 3].map((k) => Math.round((lo + ((hi - lo) * (3 - k)) / 3) / unit) * unit);
  const ev = new Set(s.events.map((e) => e[0]));
  return (
    <View style={{ width: '100%', aspectRatio: W / H }}>
      <Svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} fill="none">
        {ticks.map((t) => <React.Fragment key={t}><Line x1={56} x2={W - 20} y1={Y(t)} y2={Y(t)} stroke="#EEF0F3" /><SvgText x={48} y={Y(t) + 4} textAnchor="end" fontSize={11} fill="#8B95A1">{won(t)}</SvgText></React.Fragment>)}
        <Line x1={X(0)} x2={W - 20} y1={Y(v[0])} y2={Y(v[0])} stroke="#9AA0AA" strokeDasharray="4 4" />
        <Path d={v.slice(1).map((x, k) => `${k ? 'L' : 'M'}${X(k + 1).toFixed(1)} ${Y(x).toFixed(1)}`).join('')} stroke={c} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" />
        {v.slice(1).map((x, k) => <Circle key={k} cx={X(k + 1)} cy={Y(x)} r={ev.has(k) ? 5 : 3} fill={ev.has(k) ? '#15171A' : '#FFFFFF'} stroke={c} strokeWidth={2} />)}
        {days.slice(0, s.closes.length).map((d, k) => <SvgText key={d} x={X(k + 1)} y={H - 6} textAnchor="middle" fontSize={11} fill="#8B95A1">{d.split(' ')[0]}</SvgText>)}
        <SvgText x={X(0) + 4} y={Y(v[0]) - 6} fontSize={11} fill="#8B95A1">지난주 종가</SvgText>
      </Svg>
    </View>
  );
}

const KCH = { 공시: { bg: '#FBEDED', c: '#E5484D' }, 뉴스: { bg: '#E8EDF5', c: '#15171A' } };

/**
 * 웹 주간보고서 자세히 보기 (가운데 860) = 원본 screens/report.tsx + gen/ReportDetail
 * 보라 표지(종목 카드 · 공시/뉴스/메모 수) · 이번 주 한눈에 · (01 국내 증시 주간 요약) · 종목 섹션 · 안내
 */
export function WebReportDetail({ rep, item, stocks, market, allDefault, onMemo, onWatch, onOpenMemo }: { rep: Rep; item: MadeItem | undefined; stocks: ReportStock[]; market: boolean; allDefault: boolean; onMemo: (code: string) => void; onWatch?: (s: ReportStock, w: ReportWatch) => void; onOpenMemo?: (code: string, memoId: string) => void }) {
  if (!item) {
    return (
      <FixedFrame>
        <View style={{ width: 860, alignItems: 'center', gap: 12, paddingVertical: 96 }}>
          <Text style={{ fontSize: 22, lineHeight: 30, fontWeight: '700', color: '#15171A' }}>보고서를 찾을 수 없어요</Text>
          <Text style={{ fontSize: 15, lineHeight: 22, color: '#6B7684' }}>만든 지 30일이 지나 지워졌거나 아직 만들지 않았어요.</Text>
        </View>
      </FixedFrame>
    );
  }
  const tot = stocks.reduce((a, s) => ({ d: a.d + s.counts.공시, n: a.n + s.counts.뉴스, m: a.m + (s.memos ? s.memos.length : s.memo ? 1 : 0) }), { d: 0, n: 0, m: 0 });
  const lastClose = rep.days[rep.days.length - 1]?.split(' ')[0] ?? rep.range;
  const marketText = marketParas(rep.market_summary);
  return (
    <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false}>
      <FixedFrame>
        <View style={{ width: 860, gap: 20, paddingTop: 32, paddingBottom: 40 }}>
          <View style={st.hero}>
            <Svg style={StyleSheet.absoluteFill} preserveAspectRatio="none" viewBox="0 0 10 10"><Defs><LinearGradient id="hg" x1="0" y1="0" x2="1" y2="0"><Stop offset="0" stopColor="#17151F" /><Stop offset="1" stopColor="#2E2550" /></LinearGradient></Defs><Rect width="10" height="10" fill="url(#hg)" /></Svg>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', alignSelf: 'stretch' }}>
              <Text style={st.heroK}>MEMO&apos;S WEEKLY REPORT</Text>
              <View style={st.heroP}><Text style={st.heroPT}>{rep.week}</Text></View>
            </View>
            <View style={{ gap: 6 }}>
              <Text style={st.heroT}>{item.title}</Text>
              <Text style={st.heroS}>{rep.range} · 거래일 {rep.days.length}일 · {stocks.length}종목 · {rep.made_at} 작성</Text>
            </View>
            <View style={{ height: 1, alignSelf: 'stretch', backgroundColor: 'rgba(255,255,255,0.14)' }} />
            <View style={{ flexDirection: 'row', gap: 10, alignSelf: 'stretch' }}>
              {stocks.slice(0, 6).map((s) => {
                const c = s.pct >= 0 ? '#FF7B80' : '#7FA8FF', v = s.closes, mn = Math.min(...v), mx = Math.max(...v);
                return (
                  <View key={s.stock_code} style={st.hc}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><Logo s={s} size={22} r={6.6} /><Text style={st.hcN} numberOfLines={1}>{s.name}</Text></View>
                    <View style={{ flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', alignSelf: 'stretch' }}>
                      <Text style={[st.hcP, { color: c }]}>{sign(s.pct)}</Text>
                      <Svg width={62} height={24} viewBox="0 0 62 24" fill="none"><Path d={v.map((x, k) => `${k ? 'L' : 'M'}${(0.9 + (k / Math.max(1, v.length - 1)) * 60).toFixed(2)} ${(0.9 + ((mx - x) / (mx - mn || 1)) * 22).toFixed(2)}`).join('')} stroke={c} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" /></Svg>
                    </View>
                    <Text style={st.hcS}>{counts(s).join(' · ') || '새 소식 없음'}</Text>
                  </View>
                );
              })}
            </View>
            <View style={{ flexDirection: 'row', gap: 24 }}>
              {([['공시', `${tot.d}건`], ['뉴스', `${tot.n}건`], ['메모와 연결', `${tot.m}개`]] as const).map(([l, n]) => <Text key={l} style={st.heroS}>{l} <Text style={{ color: '#FFFFFF', fontWeight: '700' }}>{n}</Text></Text>)}
            </View>
          </View>
          <View style={st.dGlance}><Text style={[st.glanceH, { fontSize: 17 }]}>이번 주 한눈에</Text><Text keepAll style={{ fontSize: 17, lineHeight: 27, color: '#2B2F36' }}>{reportSummary(stocks, allDefault, rep.summary_default, lastClose)}</Text></View>
          {market ? (
            <>
            {/* 섹션 제목은 '02 종목별 리포트'와 같은 모양 (카드 바깥, 2026-11-23) */}
            <View style={st.sectionIntro}><Text style={st.sectionNo}>01</Text><View style={{ gap: 2 }}><Text style={st.sectionTitle}>국내 증시 현황</Text><Text style={st.sectionDesc}>{rep.range} · 거래일 {rep.days.length}일 기준 지수와 한 주 시황이에요</Text></View></View>
            <View style={[st.sec, st.marketSec]}>
              <View style={[st.marketStrip, st.marketStripTop]}>
                {rep.market.map((m, i) => <View key={m.name} style={[st.marketCell, i > 0 && st.marketCellLine]}><Text style={st.cellL}>{m.name}</Text><View style={st.marketNumber}><Text style={st.marketValue}>{m.value}</Text><Text style={[st.marketPct, { color: pc(m.pct) }]}>{sign(m.pct)}</Text></View></View>)}
              </View>
              {marketText.length || rep.flow.length ? (
                <View style={st.marketColumns}>
                  {marketText.length ? <View style={st.marketStory}><Text style={st.marketColumnH}>한 주 시황</Text>{marketText.map((p, i) => <Text key={i} keepAll style={st.marketParagraph}>{p}</Text>)}</View> : null}
                  {rep.flow.length ? <View style={[st.marketFlow, marketText.length > 0 && st.marketFlowLine]}><Text style={st.marketColumnH}>날짜별 흐름</Text>{rep.flow.map((f, i) => <View key={f.day} style={[st.timelineRow, i === rep.flow.length - 1 && { borderBottomWidth: 0, paddingBottom: 0 }]}><Text style={st.timelineDay}>{f.day}</Text><Text keepAll style={[st.flow, { flex: 1 }]}>{f.text}</Text></View>)}</View> : null}
                </View>
              ) : null}
            </View>
            </>
          ) : null}
          <View style={st.sectionIntro}><Text style={st.sectionNo}>{market ? '02' : '01'}</Text><View style={{ gap: 2 }}><Text style={st.sectionTitle}>종목별 리포트</Text><Text style={st.sectionDesc}>숫자부터 소식과 메모까지 종목별로 정리했어요</Text></View></View>
          {stocks.map((s, stockIndex) => (
            <View key={s.stock_code} style={st.sec}>
              <View style={st.stockHead}>
                <Logo s={s} size={36} r={10} />
                <View style={{ flex: 1, minWidth: 0, gap: 3 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><Text style={st.dN} numberOfLines={1}>{s.name}</Text><View style={st.ownChip}><Text style={st.ownChipT}>{s.own}</Text></View></View>
                  <Text style={st.stockOrder}>종목 {String(stockIndex + 1).padStart(2, '0')} · {lastClose} 종가 기준</Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}><Text style={st.dC}>{won(s.close)}원</Text><Text style={[st.dP, { color: pc(s.pct) }]}>{sign(s.pct)}</Text></View>
              </View>
              <View style={st.metricBlock}>
                <View style={st.blockHead}><Text style={st.blockLabel}>핵심 숫자</Text><Text style={st.blockMeta}>{s.valuation?.basis ?? rep.range}</Text></View>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  {([['주간 등락', sign(s.pct)], ['주간 최고', s.hi], ['주간 최저', s.lo], ['거래량', s.vol]] as const).map(([l, x]) => <View key={l} style={st.metricCell}><Text style={st.cellL}>{l}</Text><Text style={[st.cellV, l === '주간 등락' && { color: pc(s.pct) }]}>{x}</Text></View>)}
                </View>
                {valuationCells(s).length ? <View style={{ flexDirection: 'row', gap: 8 }}>{valuationCells(s).map(([l, x]) => <View key={l} style={st.metricCell}><Text style={st.cellL}>{l}</Text><Text style={st.cellV}>{x}</Text></View>)}</View> : null}
              </View>
              {quarterLine(s) ? <View style={st.quarterBox}><View style={st.blockHead}><Text style={st.blockLabel}>최근 분기 실적</Text><Text style={st.blockMeta}>{s.quarter?.label} · {s.quarter?.basis}</Text></View><Text keepAll style={st.quarterText}>{quarterLine(s)}</Text></View> : null}
              {s.memos?.length ? <MemoDigest s={s} onOpen={(id) => (onOpenMemo ? onOpenMemo(s.stock_code, id) : onMemo(s.stock_code))} /> : null}
              <View style={st.contentBlock}><Text style={st.subH}>이번 주 흐름</Text><DetailChart s={s} days={rep.days} /><Text style={st.note}>검은 점은 공시·뉴스가 나온 날이에요</Text><Text keepAll style={st.story}>{stripRefs(s.story)}</Text></View>
              {issueParas(s).length ? (
                <View style={st.issueBox}>
                  <Text style={st.subH}>이번 주 이슈 정리</Text>
                  {issueParas(s).map((t, k) => <Text key={k} keepAll style={st.issueText}>{t}</Text>)}
                </View>
              ) : null}
              <View style={st.contentBlock}>
                <View style={st.blockHead}><Text style={st.subH}>이번 주 소식</Text><Text style={st.blockMeta}>공시 {s.counts.공시} · 뉴스 {s.counts.뉴스}</Text></View>
                {!s.items.length ? <Text style={st.note}>새로 나온 소식이 없어요</Text> : null}
                {s.items.map((u) => (
                  <View key={u.no} style={st.item}>
                    <View style={[st.itemNo, { backgroundColor: KCH[u.kind].c }]}><Text style={st.itemNoT}>{u.no}</Text></View>
                    <View style={[st.kch, { backgroundColor: KCH[u.kind].bg }]}><Text style={[st.kchT, { color: KCH[u.kind].c }]}>{u.kind}</Text></View>
                    <Text style={[st.note, { width: 44 }]}>{u.date}</Text>
                    <Text style={st.itemT}>{u.title}</Text>
                    <Text style={st.note}>{u.src}</Text>
                  </View>
                ))}
              </View>
              {s.memos ? null : <View style={[st.memoBox, s.memo && { backgroundColor: s.memo.bg }]}>
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Text style={[st.subH, s.memo && { color: s.memo.ink }]}>내 메모와의 연결</Text>
                  <Pressable onPress={() => onMemo(s.stock_code)} accessibilityRole="link">{({ hovered }: Hover) => <Text style={[st.memoL, s.memo && { color: s.memo.ink }, hovered && { color: '#15171A' }]}>{s.memo ? '원본 메모 보기 ›' : '메모 쓰기 ›'}</Text>}</Pressable>
                </View>
                {s.memo ? <><Text style={[st.memoTitle, { color: s.memo.ink }]}>{s.memo.title} <Text style={st.memoMeta}>{s.memo.meta}</Text></Text><Text keepAll style={[st.flow, { color: s.memo.ink }]}>{stripRefs(s.memo.body)}</Text><Text style={[st.memoMeta, { color: s.memo.ink }]}>이번 주 연결된 소식 {s.memo.linked_count ?? s.counts.공시 + s.counts.뉴스}건</Text></> : <Text keepAll style={[st.flow, { color: '#747D8D' }]}>이번 주 소식과 연결된 메모가 없어요.</Text>}
              </View>}
              <View style={st.watchBox}>
                <Text style={st.subH}>앞으로 지켜볼 것</Text>
                {s.watch.map((w) => (
                  <View key={w.sid ?? w.text} style={st.watchRow}>
                    <View style={st.dot} />
                    <View style={{ flex: 1, minWidth: 0, gap: 2 }}><Text keepAll style={st.watchText}>{w.text}</Text><Text keepAll style={st.watchWhy}>근거 · {w.why}</Text></View>
                    {w.tracked ? (
                      <View style={st.watchDone}><Text style={st.watchDoneT}>✓ 추적 중</Text></View>
                    ) : w.added ? (
                      <View style={st.watchDone}><Text style={st.watchDoneT}>✓ 추가됨</Text></View>
                    ) : onWatch ? (
                      <Pressable onPress={() => onWatch(s, w)} accessibilityRole="button" accessibilityLabel={`${w.text} 메모에 추가`} style={({ hovered }: Hover) => [st.watchBtn, hovered && { opacity: 0.85 }]}>
                        <Text style={st.watchBtnT}>메모에 추가</Text>
                      </Pressable>
                    ) : null}
                  </View>
                ))}
              </View>
            </View>
          ))}
          <Text style={[st.disc, { textAlign: 'center' }]}>공시·뉴스·시세에서 가져온 정보예요. 투자 권유나 주가 예측이 아니에요.</Text>
        </View>
      </FixedFrame>
    </ScrollView>
  );
}

/** 이번 주 내 메모 정리 (2026-11-24): 맨 위 종합 2~3문장 + 메모별 그 주 카드·답·가격 상태 (카드 문장 그대로) */
function MemoDigest({ s, onOpen }: { s: ReportStock; onOpen: (memoId: string) => void }) {
  return (
    <View style={st.digestBox}>
      <Text style={st.subH}>이번 주 내 메모 정리</Text>
      {s.memo_digest ? <Text keepAll style={st.digestLead}>{stripRefs(s.memo_digest)}</Text> : null}
      {(s.memos ?? []).map((m) => (
        <View key={m.memo_id} style={st.digestMemo}>
          <Pressable onPress={() => onOpen(m.memo_id)} accessibilityRole="link" accessibilityLabel={`${m.title} 메모 열기`}>
            {({ hovered }: Hover) => <Text style={[st.digestTitle, hovered && { textDecorationLine: 'underline' }]}>{m.title} <Text style={st.digestMeta}>{m.meta} ›</Text></Text>}
          </Pressable>
          {m.cards.map((c) => (
            <View key={c.id} style={st.digestCard}>
              <Text style={st.digestDate}>{c.date}</Text>
              <View style={[st.digestKind, c.kind === '답' && { backgroundColor: '#F1EEFB' }, c.kind === '가격' && { backgroundColor: '#FFF4E5' }]}><Text style={st.digestKindT}>{c.kind}</Text></View>
              <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
                <Text keepAll style={st.digestCardT}>{c.title}{c.refs.length ? <Text style={st.digestMeta}>{'  '}{c.refs.map((r) => `[${r}]`).join('')}</Text> : null}</Text>
                <Text keepAll style={st.digestCardB} numberOfLines={2}>{c.text}</Text>
              </View>
            </View>
          ))}
          {m.status.map((x) => <Text key={x} keepAll style={st.digestStatus}>· {x}</Text>)}
          {!m.cards.length && !m.status.length ? <Text style={st.digestNone}>이번 주 새 소식 없음 · 추적 중</Text> : null}
          {m.more ? <Text style={st.digestNone}>그 밖에 {m.more}건 · 메모에서 보기</Text> : null}
        </View>
      ))}
    </View>
  );
}

const st = StyleSheet.create({
  pop: { width: 468, maxWidth: '100%', overflow: 'hidden', borderRadius: 28, backgroundColor: '#FFFFFF' },
  ph: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 22, paddingTop: 22, paddingBottom: 12 },
  phI: { width: 44, height: 44, borderRadius: 13, backgroundColor: '#F5F6F8', alignItems: 'center', justifyContent: 'center' },
  phH: { fontSize: 22, lineHeight: 29, fontWeight: '700', letterSpacing: -0.4, color: '#15171A' },
  phS: { fontSize: 14, lineHeight: 18, color: '#8E8A97', ...TR },
  pickHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  pickTitle: { fontSize: 15, lineHeight: 21, fontWeight: '700', color: '#15171A' },
  pickCount: { fontSize: 13, lineHeight: 18, fontWeight: '700', color: '#8569E3' },
  pre: { height: 40, borderRadius: 999, paddingHorizontal: 16, justifyContent: 'center', borderWidth: 1, borderColor: '#D9D9D9', backgroundColor: '#FFFFFF' },
  preOn: { backgroundColor: '#15171A', borderColor: '#15171A' },
  preT: { fontSize: 15, lineHeight: 18, fontWeight: '700', color: '#404752', ...TR },
  box: { gap: 2, borderRadius: 18, borderWidth: 1, borderColor: '#E5E3E8', padding: 6 },
  row: { height: 58, flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 14, paddingHorizontal: 12 },
  name: { flex: 1, minWidth: 0, fontSize: 17, lineHeight: 22, fontWeight: '700', color: '#15171A', ...TR },
  cnt: { fontSize: 14, lineHeight: 18, color: '#8E8A97', ...TR },
  chip: { height: 24, borderRadius: 999, paddingHorizontal: 9, justifyContent: 'center', backgroundColor: '#F5F6F8' },
  chipT: { fontSize: 13, lineHeight: 16, fontWeight: '700', color: '#404752' },
  subHead: { height: 48, flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, backgroundColor: '#FFFFFF' },
  subHeadT: { fontSize: 20, lineHeight: 29, fontWeight: '700', color: '#16171A' },
  sLbl: { fontSize: 14, lineHeight: 20, fontWeight: '500', color: '#747D8D' },
  sLbl2: { fontSize: 14, lineHeight: 20, color: '#747D8D' },
  sTitle: { fontSize: 22, lineHeight: 30, fontWeight: '700', color: '#15171A' },
  glance: { gap: 6, borderRadius: 12, backgroundColor: '#F5F6F8', paddingHorizontal: 16, paddingVertical: 14 },
  glanceH: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: '#575B63' },
  glanceP: { fontSize: 15, lineHeight: 23, color: '#2B2F36' },
  mk: { flex: 1, minWidth: 0, gap: 2, borderRadius: 10, backgroundColor: '#F5F6F8', paddingHorizontal: 12, paddingVertical: 10 },
  mkV: { fontSize: 15, lineHeight: 21, fontWeight: '700' },
  sH: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: '#15171A' },
  list: { borderRadius: 12, borderWidth: 1, borderColor: '#E8ECF3', overflow: 'hidden' },
  sr: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, paddingHorizontal: 14 },
  srN: { fontSize: 15, lineHeight: 21, fontWeight: '700', color: '#15171A' },
  srS: { fontSize: 14, lineHeight: 20, color: '#747D8D' },
  srP: { width: 54, textAlign: 'right', fontSize: 15, lineHeight: 21, fontWeight: '700' },
  detail: { alignItems: 'center', justifyContent: 'center', borderRadius: 12, backgroundColor: '#15171A', paddingVertical: 13 },
  detailT: { fontSize: 15, lineHeight: 21, fontWeight: '700', color: '#FFFFFF' },
  disc: { fontSize: 14, lineHeight: 21, color: '#8E8A97' },
  hero: { overflow: 'hidden', borderRadius: 20, padding: 28, gap: 16, alignItems: 'flex-start' },
  heroK: { fontSize: 15, lineHeight: 20, fontWeight: '700', letterSpacing: 1.6, color: '#B9A8E8' },
  heroP: { borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.12)', paddingHorizontal: 10, paddingVertical: 4 },
  heroPT: { fontSize: 15, lineHeight: 20, fontWeight: '500', color: '#FFFFFF' },
  heroT: { fontSize: 30, lineHeight: 40, fontWeight: '700', color: '#FFFFFF' },
  heroS: { fontSize: 15, lineHeight: 22, color: '#C9C3DC' },
  hc: { flex: 1, minWidth: 0, gap: 10, borderRadius: 14, borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)', backgroundColor: 'rgba(255,255,255,0.07)', padding: 14 },
  hcN: { fontSize: 15, lineHeight: 21, fontWeight: '700', color: '#FFFFFF' },
  hcP: { fontSize: 26, lineHeight: 34, fontWeight: '700' },
  hcS: { fontSize: 15, lineHeight: 21, color: '#B6B0C9' },
  dGlance: { gap: 8, borderRadius: 20, backgroundColor: '#F5F6F8', padding: 24 },
  sec: { gap: 20, borderRadius: 20, borderWidth: 1, borderColor: '#E8ECF3', backgroundColor: '#FFFFFF', padding: 24 },
  secH: { fontSize: 20, lineHeight: 28, fontWeight: '700', color: '#15171A' },
  sectionIntro: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 4, paddingTop: 4 },
  sectionNo: { fontSize: 14, lineHeight: 20, fontWeight: '700', color: '#8569E3' },
  sectionTitle: { fontSize: 20, lineHeight: 28, fontWeight: '700', color: '#15171A' },
  sectionDesc: { fontSize: 14, lineHeight: 20, color: '#747D8D' },
  marketSec: { gap: 0, padding: 0, overflow: 'hidden' },
  marketStrip: { flexDirection: 'row', borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#E8ECF3', backgroundColor: '#FAFAFB', paddingHorizontal: 24, paddingVertical: 14 },
  /* 카드 맨 위에 올 때는 위 선 없이 (제목을 카드 밖으로 뺌) */
  marketStripTop: { borderTopWidth: 0 },
  marketCell: { flex: 1, minWidth: 0, gap: 4, paddingHorizontal: 18 },
  marketCellLine: { borderLeftWidth: 1, borderLeftColor: '#E1E4E8' },
  marketNumber: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 },
  marketValue: { fontSize: 20, lineHeight: 27, fontWeight: '700', color: '#15171A' },
  marketPct: { fontSize: 14, lineHeight: 20, fontWeight: '700' },
  marketColumns: { flexDirection: 'row', gap: 0, padding: 24 },
  marketStory: { flex: 1.55, gap: 10, paddingRight: 28 },
  marketFlow: { flex: 1, gap: 2, paddingLeft: 0 },
  marketFlowLine: { borderLeftWidth: 1, borderLeftColor: '#E8ECF3', paddingLeft: 28 },
  marketColumnH: { fontSize: 15, lineHeight: 21, fontWeight: '700', color: '#15171A', marginBottom: 2 },
  marketParagraph: { fontSize: 15, lineHeight: 25, color: '#333D4B' },
  timelineRow: { gap: 3, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F0F1F4' },
  timelineDay: { fontSize: 13, lineHeight: 19, fontWeight: '600', color: '#747D8D' },
  stockHead: { flexDirection: 'row', alignItems: 'center', gap: 12, borderBottomWidth: 1, borderBottomColor: '#EEF0F3', paddingBottom: 18 },
  ownChip: { borderRadius: 999, backgroundColor: '#F0F1F4', paddingHorizontal: 8, paddingVertical: 2 },
  ownChipT: { fontSize: 12, lineHeight: 17, fontWeight: '700', color: '#575B63' },
  stockOrder: { fontSize: 13, lineHeight: 18, color: '#8B95A1' },
  metricBlock: { gap: 10, borderRadius: 16, backgroundColor: '#F7F8FA', padding: 16 },
  blockHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  blockLabel: { fontSize: 14, lineHeight: 20, fontWeight: '700', color: '#575B63' },
  blockMeta: { fontSize: 13, lineHeight: 18, color: '#8B95A1' },
  metricCell: { flex: 1, minWidth: 0, gap: 2, borderRadius: 10, backgroundColor: '#FFFFFF', paddingHorizontal: 12, paddingVertical: 10 },
  quarterBox: { gap: 8, borderRadius: 14, borderWidth: 1, borderColor: '#E8ECF3', padding: 16 },
  quarterText: { fontSize: 15, lineHeight: 24, color: '#2B2F36' },
  contentBlock: { gap: 10 },
  issueBox: { gap: 10, borderLeftWidth: 3, borderLeftColor: '#8569E3', backgroundColor: '#F8F7FC', paddingHorizontal: 18, paddingVertical: 16 },
  issueText: { fontSize: 15, lineHeight: 25, color: '#333D4B' },
  cell: { flex: 1, minWidth: 0, gap: 2, borderRadius: 12, backgroundColor: '#F5F6F8', paddingHorizontal: 16, paddingVertical: 12 },
  cellL: { fontSize: 14, lineHeight: 20, color: '#747D8D' },
  cellV: { fontSize: 17, lineHeight: 24, fontWeight: '700', color: '#15171A' },
  flow: { fontSize: 15, lineHeight: 23, color: '#333D4B' },
  dN: { flex: 1, minWidth: 0, fontSize: 22, lineHeight: 30, fontWeight: '700', color: '#15171A' },
  dC: { fontSize: 20, lineHeight: 28, fontWeight: '700', color: '#15171A' },
  dP: { textAlign: 'right', fontSize: 17, lineHeight: 24, fontWeight: '700' },
  note: { fontSize: 13, lineHeight: 20, color: '#8B95A1' },
  story: { fontSize: 15, lineHeight: 24, color: '#2B2F36' },
  subH: { fontSize: 17, lineHeight: 24, fontWeight: '700', color: '#15171A' },
  item: { flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 12, borderBottomWidth: 1, borderBottomColor: '#F0F1F4', paddingHorizontal: 4, paddingVertical: 11 },
  itemNo: { width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
  itemNoT: { fontSize: 11, lineHeight: 14, fontWeight: '700', color: '#FFFFFF' },
  kch: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  kchT: { fontSize: 13, lineHeight: 18, fontWeight: '500' },
  itemT: { flex: 1, minWidth: 0, fontSize: 15, lineHeight: 21, fontWeight: '500', color: '#15171A' },
  memoBox: { gap: 8, borderRadius: 14, backgroundColor: '#F7F8FA', padding: 16 },
  digestBox: { gap: 12, borderRadius: 14, backgroundColor: '#FFF9E6', borderWidth: 1, borderColor: '#F3E6B5', padding: 16 },
  digestLead: { fontSize: 15, lineHeight: 23, color: '#3F3A2A' },
  digestMemo: { gap: 6, borderRadius: 10, backgroundColor: '#FFFFFF', padding: 12 },
  digestTitle: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: '#15171A' },
  digestMeta: { fontSize: 12.5, lineHeight: 18, fontWeight: '500', color: '#8B95A1' },
  digestCard: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  digestDate: { width: 40, fontSize: 13, lineHeight: 20, color: '#8B95A1', fontVariant: ['tabular-nums'] },
  digestKind: { paddingHorizontal: 6, borderRadius: 6, backgroundColor: '#EAF2FF', height: 20, justifyContent: 'center' },
  digestKindT: { fontSize: 11.5, lineHeight: 16, fontWeight: '700', color: '#333D4B' },
  digestCardT: { fontSize: 14, lineHeight: 20, fontWeight: '600', color: '#2B2F36' },
  digestCardB: { fontSize: 13, lineHeight: 19, color: '#5B6270' },
  digestStatus: { fontSize: 13, lineHeight: 19, color: '#A35A00' },
  digestNone: { fontSize: 13, lineHeight: 19, color: '#8B95A1' },
  memoL: { fontSize: 14, lineHeight: 20, fontWeight: '700', color: '#575B63' },
  memoTitle: { fontSize: 16, lineHeight: 23, fontWeight: '700' },
  memoMeta: { fontSize: 12, lineHeight: 18, fontWeight: '500', opacity: 0.7 },
  watchBox: { gap: 10, borderRadius: 14, borderWidth: 1, borderColor: '#EEE7FB', backgroundColor: '#FBF8FF', padding: 16 },
  watchRow: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', borderRadius: 10, backgroundColor: '#FFFFFF', padding: 12 },
  watchText: { fontSize: 15, lineHeight: 22, fontWeight: '600', color: '#2B2F36' },
  watchWhy: { fontSize: 13, lineHeight: 19, color: '#8B95A1' },
  watchBtn: { alignSelf: 'center', height: 34, paddingHorizontal: 14, borderRadius: 10, backgroundColor: '#15171A', justifyContent: 'center' },
  watchBtnT: { fontSize: 13.5, lineHeight: 19, fontWeight: '700', color: '#FFFFFF' },
  watchDone: { alignSelf: 'center', height: 34, paddingHorizontal: 12, borderRadius: 10, borderWidth: 1, borderColor: '#E8EAED', backgroundColor: '#FFFFFF', justifyContent: 'center' },
  watchDoneT: { fontSize: 13.5, lineHeight: 19, fontWeight: '600', color: '#8B95A1' },
  dot: { width: 5, height: 5, borderRadius: 3, backgroundColor: '#15171A', marginTop: 9 },
});
