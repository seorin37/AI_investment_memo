import React, { useId } from 'react';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop } from 'react-native-svg';

/** 영역 + 라인 + 끝점 링 스파크라인 (지수 카드 · 종목 헤더) */
export function Sparkline({
  data,
  width,
  height,
  color,
  baseline,
  strokeWidth = 1.6,
  endDot = true,
}: {
  data: number[];
  width: number;
  height: number;
  color: string;
  baseline?: number; // 점선 기준(전일 종가 등)
  strokeWidth?: number;
  endDot?: boolean;
}) {
  const gid = useId().replace(/:/g, '');
  if (data.length < 2 || width <= 0) return <Svg width={width} height={height} />;
  const pad = endDot ? 6 : 2;
  const min = Math.min(...data, baseline ?? Infinity);
  const max = Math.max(...data, baseline ?? -Infinity);
  const span = max - min || 1;
  const xs = (i: number) => pad + (i / (data.length - 1)) * (width - pad * 2);
  const ys = (v: number) => pad + (1 - (v - min) / span) * (height - pad * 2);
  const line = data.map((v, i) => `${i === 0 ? 'M' : 'L'}${xs(i).toFixed(1)},${ys(v).toFixed(1)}`).join(' ');
  const area = `${line} L${xs(data.length - 1).toFixed(1)},${height} L${xs(0).toFixed(1)},${height} Z`;
  const lx = xs(data.length - 1);
  const ly = ys(data[data.length - 1]);
  return (
    <Svg width={width} height={height}>
      <Defs>
        <LinearGradient id={`g${gid}`} x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={color} stopOpacity={0.22} />
          <Stop offset="1" stopColor={color} stopOpacity={0} />
        </LinearGradient>
      </Defs>
      {baseline !== undefined && (
        <Line x1={0} x2={width} y1={ys(baseline)} y2={ys(baseline)} stroke="#C9CED6" strokeWidth={1} strokeDasharray="3 3" />
      )}
      <Path d={area} fill={`url(#g${gid})`} />
      <Path d={line} stroke={color} strokeWidth={strokeWidth} fill="none" strokeLinejoin="round" strokeLinecap="round" />
      {endDot && (
        <>
          <Circle cx={lx} cy={ly} r={5} fill="#FFFFFF" stroke={color} strokeWidth={1.4} />
          <Circle cx={lx} cy={ly} r={2} fill={color} />
        </>
      )}
    </Svg>
  );
}
