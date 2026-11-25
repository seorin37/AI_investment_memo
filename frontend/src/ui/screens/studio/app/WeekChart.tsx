import React from 'react';
import { View } from 'react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Polyline, Rect, Stop } from 'react-native-svg';
import { SvgText } from '@/ui/shared/app/SvgText';
import type { ReportStock } from '../Studio.mock';
import { won } from '../reportParts';

const EVC = { g: '#7C5CE0', n: '#3D73F0' };
/** 앱 종목 주간 차트 — reportParts 의 WeekChart 와 같고 글자만 Pretendard (그쪽은 웹과 공용이라 따로)
 * (원본 chart3 348×150 · 눈금 · 지난주 종가 점선 · 소식 번호 · 마지막 값 꼬리표) */
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
          <SvgText x={xs(k)} y={13.5} fontSize={9.5} bold fill="#fff" textAnchor="middle">{String(no)}</SvgText>
        </React.Fragment>
      ))}
      <Path d={area} fill={`url(#ga${id})`} />
      <Polyline points={line} fill="none" stroke={col} strokeWidth={2} strokeLinejoin="round" />
      {r.closes.map((v, k) => <Circle key={k} cx={xs(k)} cy={ys(v)} r={k === end ? 3.2 : 2.6} fill="#fff" stroke={col} strokeWidth={1.6} />)}
      <Rect x={W - R + 2} y={ys(last) - 8} width={R - 4} height={16} rx={4} fill={col} />
      <SvgText x={W - R / 2} y={ys(last) + 3.5} fontSize={10} bold fill="#fff" textAnchor="middle">{won(last)}</SvgText>
      {days.slice(0, n).map((d, k) => <SvgText key={d} x={xs(k)} y={H - 6} fontSize={10} fill="#9A9EA7" textAnchor={k === 0 ? 'start' : k === end ? 'end' : 'middle'}>{d}</SvgText>)}
    </Svg>
    </View>
  );
}
