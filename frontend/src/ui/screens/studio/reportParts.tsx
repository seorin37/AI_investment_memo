import React from 'react';
import { View } from 'react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Polyline, Rect, Stop, Text as SvgText } from 'react-native-svg';
import type { ReportStock } from './Studio.mock';

/** 주간보고서 공통 계산 · 그림 (앱·웹 같이 씀). 숫자는 모두 Studio.mock 에서 */
export const won = (n: number) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
export const sign = (v: number) => `${v > 0 ? '+' : v < 0 ? '-' : ''}${Math.abs(v).toFixed(1)}%`;
const josa = (w: string, a: string, b: string) => { const c = w.charCodeAt(w.length - 1); return w + (c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? a : b); };

/** '이번 주 한눈에' — 기본 3종목은 mock 문장, 그 밖은 숫자로만 만든 사실 문장 (해석 없음) */
export function reportSummary(S: ReportStock[], allDefault: boolean, fallback: string, lastClose: string) {
  if (allDefault) return fallback;
  if (S.length === 1) {
    const r = S[0];
    const it = [r.counts.공시 ? `공시 ${r.counts.공시}건` : '', r.counts.뉴스 ? `뉴스 ${r.counts.뉴스}건` : ''].filter(Boolean).join('·');
    return `${josa(r.name, '은', '는')} 이번 주 ${Math.abs(r.pct).toFixed(1)}% ${r.pct >= 0 ? '올랐고' : '내렸고'}, ${lastClose} 종가 기준 ${won(r.close)}원이에요. ${it ? `${josa(it, '이', '가')} 나왔어요.` : '새 공시·뉴스는 없었어요.'}`;
  }
  const ups = S.filter((r) => r.pct > 0).length;
  const top = S.slice().sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct))[0];
  const downs = S.filter((r) => r.pct < 0).length;
  /* '4곳 중 0곳이 올랐어요' 대신 모두 오르거나 내린 주는 그렇게 말한다 (2026-11-23) */
  const head = ups === S.length ? `내 종목 ${S.length}곳이 모두 올랐어요.` : downs === S.length ? `내 종목 ${S.length}곳이 모두 내렸어요.` : `내 종목 ${S.length}곳 중 ${ups}곳이 올랐어요.`;
  return `${head} ${top ? `${josa(top.name, '이', '가')} ${sign(top.pct)}로 가장 크게 움직였어요.` : ''}${memoSummary(S)}`;
}

/** 이번 주 한눈에 끝 문장 (2026-11-24): "이번 주 내 메모 7개 중 4개에 새 소식이 붙었어요 (SK하이닉스 2 · NAVER 1)." */
export function memoSummary(S: ReportStock[]): string {
  const withMemos = S.filter((r) => r.memos?.length);
  if (!withMemos.length) return '';
  const n = withMemos.reduce((a, r) => a + (r.memos?.length ?? 0), 0);
  const per = withMemos.map((r) => [r.name, (r.memos ?? []).filter((m) => m.cards.length).length] as const).filter(([, k]) => k > 0);
  const k = per.reduce((a, [, x]) => a + x, 0);
  return k
    ? ` 이번 주 내 메모 ${n}개 중 ${k}개에 새 소식이 붙었어요 (${per.map(([name, x]) => `${name} ${x}`).join(' · ')}).`
    : ` 이번 주 내 메모 ${n}개에 새로 붙은 소식은 없었어요.`;
}

/** 서버 보고서 추가 칸 (2026-11-23) — 이슈 정리 문단 · 밸류 칸 · 분기 실적 한 줄 */
export const stripRefs = (t: string) => t.replace(/\s*\((?:\[\d+\][,\s]*)+\)/g, '').replace(/\s*\[\d+\]/g, '');   // '1건([10])' → '1건'
/** 긴 국내 증시 시황을 웹 2단·앱 문단으로 읽을 수 있게 사실 문장만 묶는다. */
export function marketParas(t: string): string[] {
  const clean = stripRefs(t).trim();
  if (!clean) return [];
  const explicit = clean.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  if (explicit.length > 1) return explicit;
  const sentences = clean.match(/.*?[.!?](?=\s|$)|.+$/g)?.map((s) => s.trim()).filter(Boolean) ?? [clean];
  if (sentences.length <= 3) return [clean];
  const half = Math.ceil(sentences.length / 2);
  return [sentences.slice(0, half).join(' '), sentences.slice(half).join(' ')].filter(Boolean);
}
export function issueParas(s: ReportStock): string[] {
  return (s.issues ?? '').split(/\n\s*\n/).map((p) => stripRefs(p).trim()).filter(Boolean);
}
export function valuationCells(s: ReportStock): [string, string][] {
  const v = s.valuation;
  if (!v) return [];
  const x = (n: number | null, d = 2) => (n == null ? '-' : n.toFixed(d));
  return [['PER', x(v.per)], ['PBR', x(v.pbr)], ['시가총액', v.market_cap || '-'], ['52주 위치', v.w52_pos == null ? '-' : `${v.w52_pos}%`]];
}
export function quarterLine(s: ReportStock): string {
  const q = s.quarter;
  if (!q) return '';
  const y = (n: number | null) => (n == null ? '' : ` (전년 같은 분기 ${n > 0 ? '+' : ''}${n.toFixed(1)}%)`);
  const bits = [
    q.revenue ? `매출 ${q.revenue}${y(q.revenue_yoy)}` : '',
    q.operating_income ? `영업이익 ${q.operating_income}${y(q.op_yoy)}` : '',
    q.net_income ? `순이익 ${q.net_income}` : '',
  ].filter(Boolean);
  return bits.length ? `${q.label}(${q.basis}) ${bits.join(' · ')}` : '';
}

/** 작은 주가 선 (원본 spark 58×20) */
export function Spark({ c, color, w = 58, h = 20 }: { c: number[]; color: string; w?: number; h?: number }) {
  const mn = Math.min(...c), mx = Math.max(...c);
  const pts = c.map((v, i) => `${(i * (w - 2)) / Math.max(1, c.length - 1) + 1},${h - 2 - ((v - mn) / (mx - mn || 1)) * (h - 4) + 1}`).join(' ');
  return <Svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}><Polyline points={pts} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" /></Svg>;
}

/** 넓은 주가 선 (원본 sparkW · 한 종목 표지) */
export function SparkWide({ c, color }: { c: number[]; color: string }) {
  const W = 300, H = 64, mn = Math.min(...c), mx = Math.max(...c);
  const x = (i: number) => 4 + (i * (W - 8)) / Math.max(1, c.length - 1), y = (v: number) => 6 + (H - 14) * (1 - (v - mn) / (mx - mn || 1));
  const d = c.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  return (
    <Svg width="100%" height={64} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <Defs><LinearGradient id="sw1" x1="0" y1="0" x2="0" y2="1"><Stop offset="0" stopColor={color} stopOpacity={0.32} /><Stop offset="1" stopColor={color} stopOpacity={0} /></LinearGradient></Defs>
      <Path d={`${d} L${x(c.length - 1)} ${H} L${x(0)} ${H}Z`} fill="url(#sw1)" />
      <Path d={d} fill="none" stroke={color} strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round" />
    </Svg>
  );
}

const EVC = { g: '#7C5CE0', n: '#3D73F0' };
/** 종목 주간 차트 (원본 chart3 348×150 · 눈금 · 지난주 종가 점선 · 소식 번호 · 마지막 값 꼬리표) */
export function WeekChart({ r, days, id }: { r: ReportStock; days: string[]; id: string }) {
  const W = 348, H = 150, L = 4, R = 56, T = 20, B = 22;
  /* 거래일 수만큼 (5일보다 적을 수 있다 — 휴장·아직 없는 금요일 시세, 2026-11-23) */
  const n = Math.max(1, r.closes.length), end = n - 1, at = (k: number) => Math.min(k, end);
  const xs = (k: number) => L + at(k) * ((W - L - R) / Math.max(1, end)), ys = (v: number) => T + ((r.yr[1] - v) / (r.yr[1] - r.yr[0])) * (H - T - B);
  const col = r.pct >= 0 ? '#E5323B' : '#2F6BDB';
  const line = r.closes.map((v, k) => `${xs(k)},${ys(v)}`).join(' ');
  const area = `M${xs(0)},${ys(r.closes[0])} ` + r.closes.map((v, k) => `L${xs(k)},${ys(v)}`).join(' ') + ` L${xs(end)},${H - B} L${xs(0)},${H - B}Z`;
  const ticks = [0, 1, 2, 3, 4].map((t) => r.yr[0] + ((r.yr[1] - r.yr[0]) * t) / 4);
  const last = r.closes[end];
  return (
    <View style={{ width: '100%', aspectRatio: W / H }}>
    <Svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`}>
      <Defs><LinearGradient id={`ga${id}`} x1="0" y1="0" x2="0" y2="1"><Stop offset="0" stopColor={col} stopOpacity={0.16} /><Stop offset="1" stopColor={col} stopOpacity={0} /></LinearGradient></Defs>
      {ticks.map((v) => (
        <React.Fragment key={v}>
          <Line x1={L} x2={W - R} y1={ys(v)} y2={ys(v)} stroke="#F1F2F4" />
          <SvgText x={W - R + 6} y={ys(v) + 3.5} fontSize={10} fill="#9A9EA7">{won(v)}</SvgText>
        </React.Fragment>
      ))}
      <Line x1={L} x2={W - R} y1={ys(r.prev)} y2={ys(r.prev)} stroke="#B5B9C0" strokeDasharray="3 3" />
      {r.events.map(([k, no, kind]) => (
        <React.Fragment key={no}>
          <Line x1={xs(k)} x2={xs(k)} y1={12} y2={ys(r.closes[at(k)])} stroke="#D5D7DD" />
          <Circle cx={xs(k)} cy={10} r={7} fill={EVC[kind]} />
          <SvgText x={xs(k)} y={13.5} fontSize={9.5} fontWeight="700" fill="#fff" textAnchor="middle">{String(no)}</SvgText>
        </React.Fragment>
      ))}
      <Path d={area} fill={`url(#ga${id})`} />
      <Polyline points={line} fill="none" stroke={col} strokeWidth={2} strokeLinejoin="round" />
      {r.closes.map((v, k) => <Circle key={k} cx={xs(k)} cy={ys(v)} r={k === end ? 3.2 : 2.6} fill="#fff" stroke={col} strokeWidth={1.6} />)}
      <Rect x={W - R + 2} y={ys(last) - 8} width={R - 4} height={16} rx={4} fill={col} />
      <SvgText x={W - R / 2} y={ys(last) + 3.5} fontSize={10} fontWeight="700" fill="#fff" textAnchor="middle">{won(last)}</SvgText>
      {days.slice(0, n).map((d, k) => <SvgText key={d} x={xs(k)} y={H - 6} fontSize={10} fill="#9A9EA7" textAnchor={k === 0 ? 'start' : k === end ? 'end' : 'middle'}>{d}</SvgText>)}
    </Svg>
    </View>
  );
}
