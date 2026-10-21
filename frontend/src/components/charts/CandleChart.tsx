import React, { useMemo, useState } from 'react';
import { View } from 'react-native';
import Svg, { Circle, Line, Rect } from 'react-native-svg';
import { T } from '@/components/ui/Text';
import { num } from '@/lib/format';
import { chartColors, colors } from '@/theme/tokens';
import type { Candle } from '@/types/models';
import { niceTicks, useChartPointer } from './useChartPointer';

const AXIS_W = 68;
const PRICE_H = 200;
const GAP = 34;
const VOL_H = 66;
const XLABEL_H = 26;

/**
 * 일봉 캔들 + 거래량 (토스증권 OHLCV)
 * - 웹: 마우스 오버로 시세 확인, 휠로 확대·축소 / 네이티브: 터치 드래그
 */
export function CandleChart({
  candles,
  upColor,
  downColor,
  onHoverCandle,
}: {
  candles: Candle[];
  upColor: string;
  downColor: string;
  onHoverCandle?: (c: Candle | null, prev: Candle | null) => void;
}) {
  const [w, setW] = useState(0);
  const [visible, setVisible] = useState<number | null>(null);
  const shown = useMemo(() => {
    const n = Math.max(10, Math.min(candles.length, visible ?? candles.length));
    return candles.slice(-n);
  }, [candles, visible]);

  const { ref, x, handlers } = useChartPointer({
    onWheel: (dy) => setVisible((v) => Math.max(10, Math.min(candles.length, Math.round((v ?? candles.length) * (dy > 0 ? 1.12 : 0.88))))),
  });

  const plotW = Math.max(0, w - AXIS_W);
  const n = shown.length;
  const step = n > 0 ? plotW / n : 0;
  const bodyW = Math.max(2, Math.min(14, step * 0.58));

  const lo = Math.min(...shown.map((c) => c.low));
  const hi = Math.max(...shown.map((c) => c.high));
  const padY = (hi - lo) * 0.08 || hi * 0.02;
  const ticks = niceTicks(lo - padY, hi + padY, 4);
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];
  const y = (v: number) => 8 + (1 - (v - yMin) / (yMax - yMin || 1)) * (PRICE_H - 16);
  const maxVol = Math.max(...shown.map((c) => c.volume), 1);
  const volTop = PRICE_H + GAP;
  const vy = (v: number) => volTop + VOL_H - (v / maxVol) * VOL_H;
  const cx = (i: number) => i * step + step / 2;

  const hoverIdx = x === null || step === 0 ? null : Math.max(0, Math.min(n - 1, Math.floor(x / step)));
  const hovered = hoverIdx !== null ? shown[hoverIdx] : null;
  const prevOfHover = hoverIdx !== null && hoverIdx > 0 ? shown[hoverIdx - 1] : null;

  React.useEffect(() => {
    onHoverCandle?.(hovered, prevOfHover);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hovered?.date]);

  const last = shown[n - 1];
  const tagValue = hovered ? hovered.close : last?.close;
  const labelEvery = Math.max(1, Math.round(n / 6));
  const H = PRICE_H + GAP + VOL_H + XLABEL_H;

  return (
    <View onLayout={(e) => setW(e.nativeEvent.layout.width)} style={{ height: H }}>
      {w > 0 && n > 0 && (
        <View ref={ref} {...handlers} style={{ width: w, height: H }}>
          <Svg width={w} height={H}>
            {/* 가격 영역 테두리 · 그리드 */}
            <Rect x={0.5} y={0.5} width={plotW - 1} height={PRICE_H - 1} fill="none" stroke={chartColors.grid} />
            {ticks.map((t) => (
              <Line key={t} x1={0} x2={plotW} y1={y(t)} y2={y(t)} stroke={chartColors.grid} strokeWidth={1} />
            ))}
            {shown.map((c, i) =>
              i % labelEvery === 0 && i > 0 ? (
                <Line key={`v${c.date}`} x1={cx(i)} x2={cx(i)} y1={0} y2={PRICE_H} stroke={chartColors.grid} strokeWidth={1} />
              ) : null,
            )}
            {/* 캔들 */}
            {shown.map((c, i) => {
              const up = c.close >= c.open;
              const col = up ? upColor : downColor;
              const top = y(Math.max(c.open, c.close));
              const bh = Math.max(1, Math.abs(y(c.open) - y(c.close)));
              return (
                <React.Fragment key={c.date}>
                  <Line x1={cx(i)} x2={cx(i)} y1={y(c.high)} y2={y(c.low)} stroke={col} strokeWidth={1} />
                  <Rect x={cx(i) - bodyW / 2} y={top} width={bodyW} height={bh} fill={col} rx={1} />
                  <Rect x={cx(i) - bodyW / 2} y={vy(c.volume)} width={bodyW} height={volTop + VOL_H - vy(c.volume)} fill={col} rx={1} />
                </React.Fragment>
              );
            })}
            <Line x1={0} x2={plotW} y1={volTop + VOL_H} y2={volTop + VOL_H} stroke={chartColors.grid} />
            {/* 현재가/호버 가로선 */}
            {tagValue !== undefined && <Line x1={0} x2={plotW} y1={y(tagValue)} y2={y(tagValue)} stroke="#9AA3B2" strokeWidth={1} />}
            {/* 크로스헤어 */}
            {hovered && hoverIdx !== null && (
              <>
                <Line x1={cx(hoverIdx)} x2={cx(hoverIdx)} y1={0} y2={volTop + VOL_H} stroke="#9AA3B2" strokeWidth={1} />
                <Circle cx={cx(hoverIdx)} cy={y(hovered.close)} r={3.5} fill="#FFF" stroke={colors.text} strokeWidth={1.6} />
              </>
            )}
          </Svg>

          {/* Y축 레이블 */}
          {ticks.map((t) => (
            <T key={t} size={10} color={chartColors.axis} style={{ position: 'absolute', left: plotW + 10, top: y(t) - 7 }} tabular>
              {num(t)}
            </T>
          ))}
          {tagValue !== undefined && (
            <View style={{ position: 'absolute', left: plotW + 2, top: y(tagValue) - 10, backgroundColor: '#2B2F36', borderRadius: 3, paddingHorizontal: 6, height: 20, justifyContent: 'center' }}>
              <T size={11} weight="semibold" color="#FFF" lh={1.1} tabular>
                {num(tagValue)}
              </T>
            </View>
          )}
          {/* 거래량 레이블 */}
          <View style={{ position: 'absolute', left: 0, top: PRICE_H + 8, flexDirection: 'row', gap: 10 }}>
            <T size={11} weight="medium" color={colors.textBody}>
              거래량
            </T>
            <T size={11} weight="semibold" color="#6B7684" tabular>
              {num((hovered ?? last).volume)}
            </T>
          </View>
          {/* X축 날짜 */}
          {shown.map((c, i) =>
            i % labelEvery === 0 ? (
              <T key={`x${c.date}`} size={10} color={chartColors.axis} style={{ position: 'absolute', top: volTop + VOL_H + 8, left: Math.max(0, cx(i) - 14) }}>
                {c.date.slice(5).replace('-', '.')}
              </T>
            ) : null,
          )}
          {hovered && hoverIdx !== null && (
            <View style={{ position: 'absolute', top: volTop + VOL_H + 4, left: Math.min(plotW - 84, Math.max(0, cx(hoverIdx) - 42)), width: 84, height: 22, backgroundColor: '#2B2F36', borderRadius: 3, alignItems: 'center', justifyContent: 'center' }}>
              <T size={10} color="#FFF" lh={1.1}>
                {hovered.date}
              </T>
            </View>
          )}
        </View>
      )}
    </View>
  );
}
