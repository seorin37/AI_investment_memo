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
  return `내 종목 ${S.length}곳 중 ${ups}곳이 올랐어요. ${top ? `${josa(top.name, '이', '가')} ${sign(top.pct)}로 가장 크게 움직였어요.` : ''}`;
}

/** 작은 주가 선 (원본 spark 58×20) */
export function Spark({ c, color, w = 58, h = 20 }: { c: number[]; color: string; w?: number; h?: number }) {
  const mn = Math.min(...c), mx = Math.max(...c);
  const pts = c.map((v, i) => `${(i * (w - 2)) / (c.length - 1) + 1},${h - 2 - ((v - mn) / (mx - mn || 1)) * (h - 4) + 1}`).join(' ');
  return <Svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}><Polyline points={pts} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" /></Svg>;
}

/** 넓은 주가 선 (원본 sparkW · 한 종목 표지) */
export function SparkWide({ c, color }: { c: number[]; color: string }) {
  const W = 300, H = 64, mn = Math.min(...c), mx = Math.max(...c);
  const x = (i: number) => 4 + (i * (W - 8)) / (c.length - 1), y = (v: number) => 6 + (H - 14) * (1 - (v - mn) / (mx - mn || 1));
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
  const xs = (k: number) => L + k * ((W - L - R) / 4), ys = (v: number) => T + ((r.yr[1] - v) / (r.yr[1] - r.yr[0])) * (H - T - B);
  const col = r.pct >= 0 ? '#E5323B' : '#2F6BDB';
  const line = r.closes.map((v, k) => `${xs(k)},${ys(v)}`).join(' ');
  const area = `M${xs(0)},${ys(r.closes[0])} ` + r.closes.map((v, k) => `L${xs(k)},${ys(v)}`).join(' ') + ` L${xs(4)},${H - B} L${xs(0)},${H - B}Z`;
  const ticks = [0, 1, 2, 3, 4].map((t) => r.yr[0] + ((r.yr[1] - r.yr[0]) * t) / 4);
  const last = r.closes[4];
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
          <Line x1={xs(k)} x2={xs(k)} y1={12} y2={ys(r.closes[k])} stroke="#D5D7DD" />
          <Circle cx={xs(k)} cy={10} r={7} fill={EVC[kind]} />
          <SvgText x={xs(k)} y={13.5} fontSize={9.5} fontWeight="700" fill="#fff" textAnchor="middle">{String(no)}</SvgText>
        </React.Fragment>
      ))}
      <Path d={area} fill={`url(#ga${id})`} />
      <Polyline points={line} fill="none" stroke={col} strokeWidth={2} strokeLinejoin="round" />
      {r.closes.map((v, k) => <Circle key={k} cx={xs(k)} cy={ys(v)} r={k === 4 ? 3.2 : 2.6} fill="#fff" stroke={col} strokeWidth={1.6} />)}
      <Rect x={W - R + 2} y={ys(last) - 8} width={R - 4} height={16} rx={4} fill={col} />
      <SvgText x={W - R / 2} y={ys(last) + 3.5} fontSize={10} fontWeight="700" fill="#fff" textAnchor="middle">{won(last)}</SvgText>
      {days.map((d, k) => <SvgText key={d} x={xs(k)} y={H - 6} fontSize={10} fill="#9A9EA7" textAnchor={k === 0 ? 'start' : k === 4 ? 'end' : 'middle'}>{d}</SvgText>)}
    </Svg>
    </View>
  );
}
