import React, { useState } from 'react';
import { View } from 'react-native';
import Svg, { Circle, Line, Path, Polygon, Rect } from 'react-native-svg';
import { T } from '@/components/ui/Text';
import { joAxis, krwUnit } from '@/lib/format';
import { chartColors, colors, shadow } from '@/theme/tokens';
import { niceTicks, useChartPointer } from './useChartPointer';

const LEFT = 38;

const periodLabel = (p: string) => `${p.slice(2, 4)}년 ${Number(p.slice(5, 7))}월`;
const periodLong = (p: string) => `${p.slice(0, 4)}년 ${Number(p.slice(5, 7))}월`;

/**
 * 매출 · 영업이익 · 당기순이익: 막대(금액) 위에 전년 대비 증감률 꺾은선을 얹은 차트
 * (팀 결정: 막대는 그대로 두고 증감률 라인을 오버레이)
 */
export function BarLineChart({
  periods,
  values,
  yoy,
  color,
  height = 230,
  upColor,
  downColor,
}: {
  periods: string[];
  values: number[];
  yoy: (number | null)[];
  color: string;
  height?: number;
  upColor: string;
  downColor: string;
}) {
  const [w, setW] = useState(0);
  const { ref, x, handlers } = useChartPointer();
  const plotW = Math.max(0, w - LEFT);
  const plotH = height - 26;
  const n = values.length;
  const ticks = niceTicks(Math.min(0, ...values), Math.max(...values) * 1.02, 5);
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];
  const y = (v: number) => 6 + (1 - (v - yMin) / (yMax - yMin || 1)) * (plotH - 12);
  const step = n ? plotW / n : 0;
  const cx = (i: number) => LEFT + step * i + step / 2;
  const barW = Math.min(28, step * 0.5);

  // 증감률 라인은 별도 스케일(플롯 영역 15%~85%)에 매핑
  const yv = yoy.filter((v): v is number => v !== null);
  const lmin = Math.min(...yv);
  const lmax = Math.max(...yv);
  const ly = (v: number) => 6 + plotH * 0.12 + (1 - (v - lmin) / (lmax - lmin || 1)) * (plotH * 0.62);
  const linePath = yoy
    .map((v, i) => (v === null ? null : `${cx(i).toFixed(1)},${ly(v).toFixed(1)}`))
    .filter(Boolean)
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p}`)
    .join(' ');

  const hi = x === null || step === 0 ? null : Math.max(0, Math.min(n - 1, Math.floor((x - LEFT) / step)));

  return (
    <View onLayout={(e) => setW(e.nativeEvent.layout.width)} style={{ height }}>
      {w > 0 && (
        <View ref={ref} {...handlers} style={{ width: w, height }}>
          <Svg width={w} height={height}>
            {ticks.map((t) => (
              <Line key={t} x1={LEFT} x2={w} y1={y(t)} y2={y(t)} stroke={t === 0 ? '#C9CED6' : chartColors.grid} strokeWidth={1} />
            ))}
            {values.map((v, i) => {
              const top = y(Math.max(0, v));
              const h = Math.abs(y(v) - y(0));
              return <Rect key={i} x={cx(i) - barW / 2} y={top} width={barW} height={Math.max(1, h)} fill={color} opacity={hi === null || hi === i ? 1 : 0.55} />;
            })}
            <Path d={linePath} stroke={chartColors.yoyLine} strokeWidth={1.4} fill="none" />
            {yoy.map((v, i) => (v === null ? null : <Circle key={i} cx={cx(i)} cy={ly(v)} r={3.2} fill="#FFF" stroke={chartColors.yoyLine} strokeWidth={1.4} />))}
          </Svg>
          {ticks.map((t) => (
            <T key={t} size={9} color={chartColors.axis} style={{ position: 'absolute', left: 0, width: LEFT - 6, top: y(t) - 6, textAlign: 'right' }}>
              {joAxis(t)}
            </T>
          ))}
          {periods.map((p, i) => (
            <T key={p} size={9} color={chartColors.axis} style={{ position: 'absolute', top: plotH + 8, left: cx(i) - 22, width: 44, textAlign: 'center' }}>
              {periodLabel(p)}
            </T>
          ))}
          {hi !== null && (
            <View
              pointerEvents="none"
              style={{
                position: 'absolute',
                top: 8,
                left: Math.min(w - 176, Math.max(LEFT, cx(hi) - 88)),
                width: 172,
                backgroundColor: '#FFF',
                borderRadius: 14,
                borderWidth: 1,
                borderColor: colors.border,
                padding: 12,
                gap: 4,
                ...shadow.pop,
              }}
            >
              <T size={11} weight="semibold" color={colors.blue}>
                {periodLong(periods[hi])}
              </T>
              <T size={16} weight="bold" color="#6B7684">
                {krwUnit(values[hi])}원
              </T>
              {yoy[hi] !== null && (
                <T size={12} color={(yoy[hi] ?? 0) >= 0 ? upColor : downColor}>
                  {(yoy[hi] ?? 0) >= 0 ? '+' : ''}
                  {(yoy[hi] ?? 0).toFixed(1)}% · 전년 대비
                </T>
              )}
            </View>
          )}
        </View>
      )}
    </View>
  );
}

/** 수익성: 영업이익률 · 순이익률 · ROE 꺾은선 */
export function MultiLineChart({
  periods,
  series,
  height = 260,
}: {
  periods: string[];
  series: { key: string; label: string; color: string; values: number[] }[];
  height?: number;
}) {
  const [w, setW] = useState(0);
  const { ref, x, handlers } = useChartPointer();
  const all = series.flatMap((s) => s.values);
  const ticks = niceTicks(Math.min(...all, 0), Math.max(...all), 5);
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];
  const plotH = height - 28;
  const plotW = Math.max(0, w - LEFT);
  const n = periods.length;
  const y = (v: number) => 6 + (1 - (v - yMin) / (yMax - yMin || 1)) * (plotH - 12);
  const cx = (i: number) => LEFT + 24 + (i / Math.max(1, n - 1)) * (plotW - 48);
  const hi = x === null ? null : Math.max(0, Math.min(n - 1, Math.round(((x - LEFT - 24) / Math.max(1, plotW - 48)) * (n - 1))));

  return (
    <View onLayout={(e) => setW(e.nativeEvent.layout.width)} style={{ height }}>
      {w > 0 && (
        <View ref={ref} {...handlers} style={{ width: w, height }}>
          <Svg width={w} height={height}>
            {ticks.map((t) => (
              <Line key={t} x1={LEFT} x2={w} y1={y(t)} y2={y(t)} stroke={t === 0 ? '#C9CED6' : chartColors.grid} />
            ))}
            {hi !== null && <Line x1={cx(hi)} x2={cx(hi)} y1={0} y2={plotH} stroke="#C9CED6" strokeDasharray="3 3" />}
            {series.map((s) => (
              <React.Fragment key={s.key}>
                <Path d={s.values.map((v, i) => `${i === 0 ? 'M' : 'L'}${cx(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')} stroke={s.color} strokeWidth={2} fill="none" />
                {s.values.map((v, i) => (
                  <Circle key={i} cx={cx(i)} cy={y(v)} r={hi === i ? 4.5 : 3.2} fill={s.color} />
                ))}
              </React.Fragment>
            ))}
          </Svg>
          {ticks.map((t) => (
            <T key={t} size={9} color={chartColors.axis} style={{ position: 'absolute', left: 0, width: LEFT - 8, top: y(t) - 6, textAlign: 'right' }}>
              {t}%
            </T>
          ))}
          {periods.map((p, i) => (
            <T key={p} size={9} color={chartColors.axis} style={{ position: 'absolute', top: plotH + 10, left: cx(i) - 24, width: 48, textAlign: 'center' }}>
              {p.replace('-', '/')}
            </T>
          ))}
          {hi !== null && (
            <View
              pointerEvents="none"
              style={{ position: 'absolute', top: 6, left: Math.min(w - 150, Math.max(LEFT, cx(hi) + 10)), width: 140, backgroundColor: '#FFF', borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 10, gap: 3, ...shadow.pop }}
            >
              <T size={11} weight="semibold" color={colors.blue}>
                {p2(periods[hi])}
              </T>
              {series.map((s) => (
                <View key={s.key} style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                  <T size={11} color={colors.textSub}>
                    {s.label}
                  </T>
                  <T size={11} weight="semibold" color={s.color}>
                    {s.values[hi].toFixed(1)}%
                  </T>
                </View>
              ))}
            </View>
          )}
        </View>
      )}
    </View>
  );
}
const p2 = (p: string) => `${p.slice(0, 4)}년 ${Number(p.slice(5, 7))}월`;

/** 기업 건전성 레이더 — 업종 평균 없이 선택 기업만 (팀 결정) */
export function RadarChart({
  axes,
  values,
  highlight,
  size = 260,
  onPressAxis,
}: {
  axes: string[];
  values: number[]; // 0~1 (바깥일수록 안정)
  highlight: number | null;
  size?: number;
  onPressAxis?: (i: number) => void;
}) {
  const c = size / 2;
  const R = size / 2 - 46;
  const n = axes.length;
  const pt = (i: number, r: number) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    return [c + Math.cos(a) * r, c + Math.sin(a) * r] as const;
  };
  const ring = (k: number) => axes.map((_, i) => pt(i, (R * k) / 4).join(',')).join(' ');
  const shape = values.map((v, i) => pt(i, R * Math.max(0.08, Math.min(1, v))).join(',')).join(' ');
  return (
    <View style={{ width: size, height: size }}>
      <Svg width={size} height={size}>
        {[1, 2, 3, 4].map((k) => (
          <Polygon key={k} points={ring(k)} fill={k === 4 ? '#F7F9FC' : 'none'} stroke="#DDE3EC" strokeWidth={1} />
        ))}
        {axes.map((_, i) => {
          const [x2, y2] = pt(i, R);
          return <Line key={i} x1={c} y1={c} x2={x2} y2={y2} stroke="#DDE3EC" />;
        })}
        <Polygon points={shape} fill={chartColors.radarFill} stroke={chartColors.radar} strokeWidth={2} />
        {values.map((v, i) => {
          const [px, py] = pt(i, R * Math.max(0.08, Math.min(1, v)));
          const on = highlight === i;
          return <Circle key={i} cx={px} cy={py} r={on ? 5 : 3.5} fill={on ? colors.danger : chartColors.radar} stroke="#FFF" strokeWidth={1.5} />;
        })}
      </Svg>
      {axes.map((label, i) => {
        const [lx, ly] = pt(i, R + 26);
        const on = highlight === i;
        return (
          <T
            key={label}
            size={12}
            weight={on ? 'semibold' : 'regular'}
            color={on ? colors.danger : colors.textBody}
            onPress={onPressAxis ? () => onPressAxis(i) : undefined}
            style={{ position: 'absolute', left: lx - 40, top: ly - 9, width: 80, textAlign: 'center' }}
          >
            {label}
          </T>
        );
      })}
    </View>
  );
}

/** 52주 최저~최고 범위 막대 + 현재가 알약 */
export function RangeBar({ low, high, value, label }: { low: number; high: number; value: number; label: string }) {
  const [w, setW] = useState(0);
  const ratio = Math.max(0, Math.min(1, (value - low) / (high - low || 1)));
  const pillW = 84;
  return (
    <View style={{ height: 32, justifyContent: 'center' }} onLayout={(e) => setW(e.nativeEvent.layout.width)}>
      <View style={{ height: 6, borderRadius: 3, backgroundColor: '#D5D9E0' }} />
      {w > 0 && (
        <View
          style={{
            position: 'absolute',
            left: Math.max(0, Math.min(w - pillW, ratio * w - pillW / 2)),
            width: pillW,
            height: 30,
            borderRadius: 15,
            backgroundColor: '#2B2F36',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <T size={13} weight="semibold" color="#FFF" lh={1.1} tabular>
            {label}
          </T>
        </View>
      )}
    </View>
  );
}
