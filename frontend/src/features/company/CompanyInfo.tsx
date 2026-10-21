import React, { useMemo, useState } from 'react';
import { Pressable, View, type StyleProp, type ViewStyle } from 'react-native';
import { CandleChart } from '@/components/charts/CandleChart';
import { BarLineChart, MultiLineChart, RadarChart, RangeBar } from '@/components/charts/FinanceCharts';
import { Icon } from '@/components/icons/Icon';
import { ErrorState, IconButton, Loading, PillTabs, QuestionDot } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useCandles, useFinancials, useProfile, useQuote } from '@/hooks/queries';
import { useBreakpoint, useMarketColors } from '@/hooks/useLayout';
import { krwUnit, num } from '@/lib/format';
import { chartColors, colors, shadow } from '@/theme/tokens';
import type { Candle, ChartRange, Financials, Stability } from '@/types/models';
import { glossary, type Term, type TermKey } from './glossary';

/** 7. 기업정보 — 개요 · 주가/거래량 · 시세/투자정보 · 매출/영업이익/순이익 · 수익성 · 건전성 */
export function CompanyInfo({ stockCode, stockName }: { stockCode: string; stockName: string }) {
  const { isDesktop, isMobile } = useBreakpoint();
  const profile = useProfile(stockCode);
  const fin = useFinancials(stockCode);

  if (profile.isLoading || fin.isLoading) return <Loading height={400} />;
  if (profile.error || fin.error || !profile.data || !fin.data)
    return <ErrorState message="기업 정보를 불러오지 못했어요." onRetry={() => void Promise.all([profile.refetch(), fin.refetch()])} />;

  const p = profile.data;
  return (
    <View style={{ gap: 32 }}>
      <Box style={{ flexDirection: isMobile ? 'column' : 'row', gap: isMobile ? 8 : 40, paddingVertical: 22 }}>
        <T size={18} weight="bold">
          기업 개요
        </T>
        <T size={14} color={colors.textBody} lh={1.65} style={{ flex: 1 }}>
          {p.overview}
        </T>
      </Box>

      <PriceSection stockCode={stockCode} />

      <View style={{ flexDirection: isDesktop ? 'row' : 'column', gap: 24 }}>
        <FinanceCard fin={fin.data} kind="revenue" />
        <FinanceCard fin={fin.data} kind="operating" />
        <FinanceCard fin={fin.data} kind="net" />
      </View>

      <View style={{ flexDirection: isDesktop ? 'row' : 'column', gap: 24 }}>
        <ProfitabilityCard fin={fin.data} />
        <HealthCard stability={fin.data.stability} name={stockName} />
      </View>
    </View>
  );
}

function Box({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[{ backgroundColor: colors.surface, borderRadius: 20, borderWidth: 1, borderColor: colors.border, padding: 24 }, style]}>{children}</View>;
}

// ─── 주가 · 거래량 + 시세/투자정보 ────────────────────────────
const RANGES: { key: ChartRange; label: string }[] = [
  { key: '1W', label: '1주' },
  { key: '1M', label: '1달' },
  { key: '3M', label: '3달' },
  { key: '1Y', label: '1년' },
];

function PriceSection({ stockCode }: { stockCode: string }) {
  const [range, setRange] = useState<ChartRange>('3M');
  const { data: candles } = useCandles(stockCode, range);
  const { data: profile } = useProfile(stockCode);
  const { data: quote } = useQuote(stockCode);
  const mc = useMarketColors();
  const { isMobile } = useBreakpoint();
  const [hover, setHover] = useState<{ c: Candle; prev: Candle | null } | null>(null);
  const [term, setTerm] = useState<TermKey | null>(null);

  const shown = hover?.c ?? candles?.[candles.length - 1];
  const prevClose = hover ? hover.prev?.close : profile?.prev_close;
  const chg = shown && prevClose ? ((shown.close - prevClose) / prevClose) * 100 : 0;

  const cells: { label: string; value: string; color?: string; term?: TermKey }[][] = profile
    ? [
        [
          { label: '전일', value: num(profile.prev_close) },
          { label: '고가', value: num(profile.high), color: mc.of(profile.high - profile.prev_close) },
          { label: '거래량', value: `${num(profile.volume)}주` },
        ],
        [
          { label: '시가', value: num(profile.open), color: mc.of(profile.open - profile.prev_close) },
          { label: '저가', value: num(profile.low), color: mc.of(profile.low - profile.prev_close) },
          { label: '거래대금', value: `${num(Math.round(profile.trading_value / 1e8))}억원` },
        ],
        [
          { label: 'PER', value: profile.per ? `${profile.per.toFixed(2)}배` : '—', term: 'per' },
          { label: 'PBR', value: profile.pbr ? `${profile.pbr.toFixed(2)}배` : '—', term: 'pbr' },
          { label: '시가총액', value: krwUnit(profile.market_cap, true), term: 'mcap' },
        ],
        [
          { label: 'EPS', value: profile.eps ? `${num(profile.eps)}원` : '—', term: 'eps' },
          { label: 'BPS', value: profile.bps ? `${num(profile.bps)}원` : '—', term: 'bps' },
          { label: '상장주수', value: `${num(profile.shares_outstanding)}주`, term: 'shares' },
        ],
      ]
    : [];

  return (
    <Box style={{ gap: 14, zIndex: term ? 10 : 1 }}>
      <View style={{ flexDirection: isMobile ? 'column' : 'row', justifyContent: 'space-between', alignItems: isMobile ? 'flex-start' : 'center', gap: 10 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <T size={18} weight="bold">
            주가 · 거래량
          </T>
          <PillTabs items={RANGES} value={range} onChange={setRange} size="sm" />
        </View>
        <T size={11} color={colors.textSub}>
          일봉 · {isMobile ? '터치로 시세 확인' : '마우스로 시세 확인 · 스크롤로 확대·축소'}
        </T>
      </View>
      {shown && (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 14 }}>
          {(
            [
              ['시', shown.open],
              ['고', shown.high],
              ['저', shown.low],
              ['종', shown.close],
            ] as const
          ).map(([k, v]) => (
            <T key={k} size={11} color={colors.textBody} tabular>
              {k} {num(v)}
            </T>
          ))}
          <T size={11} color={mc.of(chg)} tabular>
            {chg >= 0 ? '▲' : '▼'} {Math.abs(chg).toFixed(2)}%
          </T>
          <T size={11} color={colors.textBody} tabular>
            거 {num(shown.volume)}
          </T>
        </View>
      )}
      {candles ? (
        <CandleChart candles={candles} upColor={mc.up} downColor={mc.down} onHoverCandle={(c, prev) => setHover(c ? { c, prev } : null)} />
      ) : (
        <Loading height={326} />
      )}

      {profile && (
        <>
          <View style={{ flexDirection: isMobile ? 'column' : 'row', alignItems: isMobile ? 'stretch' : 'center', gap: isMobile ? 10 : 20, marginTop: 10 }}>
            <T size={18} weight="bold">
              시세정보 · 투자정보
            </T>
            <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <RangeEnd label="52주 최저" value={profile.week52_low} align="right" />
              <View style={{ flex: 1 }}>
                <RangeBar low={profile.week52_low} high={profile.week52_high} value={quote?.price ?? profile.prev_close} label={num(quote?.price ?? profile.prev_close)} />
              </View>
              <RangeEnd label="52주 최고" value={profile.week52_high} align="left" />
            </View>
          </View>
          <View style={{ flexDirection: isMobile ? 'column' : 'row', gap: isMobile ? 0 : 20, zIndex: 5 }}>
            {cells.map((col, ci) => (
              <View key={ci} style={{ flex: 1, zIndex: col.some((c) => c.term === term) ? 10 : 1 }}>
                {col.map((c) => (
                  <View key={c.label} style={{ height: 38, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderColor: colors.borderSoft, zIndex: c.term === term ? 10 : 1 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                      <T size={13} color={colors.textSub}>
                        {c.label}
                      </T>
                      {c.term && <QuestionDot onPress={() => setTerm(term === c.term ? null : c.term!)} />}
                    </View>
                    <T size={13} weight="semibold" color={c.color ?? colors.text} tabular>
                      {c.value}
                    </T>
                    {c.term && term === c.term && <TermPopover term={glossary[c.term]} onClose={() => setTerm(null)} style={{ bottom: 40, left: 0 }} />}
                  </View>
                ))}
              </View>
            ))}
          </View>
        </>
      )}
    </Box>
  );
}

function RangeEnd({ label, value, align }: { label: string; value: number; align: 'left' | 'right' }) {
  return (
    <View style={{ alignItems: align === 'left' ? 'flex-start' : 'flex-end' }}>
      <T size={10} color={colors.textSub}>
        {label}
      </T>
      <T size={13} weight="semibold" tabular>
        {num(value)}
      </T>
    </View>
  );
}

function TermPopover({ term, onClose, style, wide }: { term: Term; onClose: () => void; style?: StyleProp<ViewStyle>; wide?: boolean }) {
  return (
    <View
      style={[
        {
          position: 'absolute',
          width: wide ? 260 : 220,
          backgroundColor: '#FFF',
          borderRadius: 14,
          borderWidth: 1,
          borderColor: colors.border,
          padding: wide ? 18 : 12,
          gap: 8,
          zIndex: 50,
          ...shadow.pop,
        },
        style,
      ]}
    >
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <T size={wide ? 16 : 12} weight="semibold" color={colors.blue}>
          {term.title}
        </T>
        <IconButton name="x" label="닫기" size={14} box={22} onPress={onClose} color={colors.textSub} />
      </View>
      <T size={wide ? 13 : 11} color={colors.textSub} lh={1.6}>
        {term.desc}
      </T>
      {term.formula && (
        <T size={wide ? 12 : 11} color={colors.textSub}>
          계산: {term.formula}
        </T>
      )}
      {term.glance && (
        <View style={{ backgroundColor: colors.blueSoft, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10 }}>
          <T size={12} color={colors.blueStrong}>
            {term.glance}
          </T>
        </View>
      )}
    </View>
  );
}

// ─── 매출 · 영업이익 · 당기순이익 ─────────────────────────────
const FIN_META = {
  revenue: { label: '매출', field: 'revenue', color: chartColors.revenue },
  operating: { label: '영업이익', field: 'operating_income', color: chartColors.operating },
  net: { label: '당기순이익', field: 'net_income', color: chartColors.net },
} as const;

function FinanceCard({ fin, kind }: { fin: Financials; kind: keyof typeof FIN_META }) {
  const meta = FIN_META[kind];
  const mc = useMarketColors();
  const [help, setHelp] = useState(false);
  const all = fin.annual.map((a) => a[meta.field]);
  const recent = fin.annual.slice(-6);
  const values = recent.map((a) => a[meta.field]);
  const yoy = recent.map((a) => {
    const idx = fin.annual.indexOf(a);
    const prev = all[idx - 1];
    return prev === undefined || prev === 0 ? null : ((a[meta.field] - prev) / Math.abs(prev)) * 100;
  });
  const last = recent[recent.length - 1];
  const lastYoy = yoy[yoy.length - 1];
  const prevPeriod = recent[recent.length - 2]?.period ?? '';
  const periodText = (p: string) => `${p.slice(0, 4)}년 ${Number(p.slice(5, 7))}월`;

  return (
    <Box style={{ flex: 1, gap: 12, zIndex: help ? 10 : 1 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <T size={18} weight="bold">
            {meta.label}
          </T>
          <QuestionDot onPress={() => setHelp((h) => !h)} />
        </View>
        <T size={10} color={colors.textSub}>
          {fin.basis}
        </T>
      </View>
      <View style={{ flexDirection: 'row', gap: 24 }}>
        <View>
          <T size={11} color={colors.textSub}>
            {periodText(last.period)} {meta.label}
          </T>
          <T size={14} weight="bold" tabular>
            {krwUnit(last[meta.field])}원
          </T>
        </View>
        <View>
          <T size={11} color={colors.textSub}>
            {periodText(prevPeriod)} 대비
          </T>
          <T size={14} weight="bold" color={mc.of(lastYoy ?? 0)} tabular>
            {lastYoy === null ? '—' : `${lastYoy >= 0 ? '+' : ''}${lastYoy.toFixed(2)}%`}
          </T>
        </View>
      </View>
      <BarLineChart periods={recent.map((r) => r.period)} values={values} yoy={yoy} color={meta.color} upColor={mc.up} downColor={mc.down} />
      <View style={{ flexDirection: 'row', gap: 14 }}>
        <Legend color={meta.color} label="금액" square />
        <Legend color={chartColors.yoyLine} label="전년 대비 증감률" />
      </View>
      {help && <TermPopover term={glossary[kind]} onClose={() => setHelp(false)} wide style={{ top: 110, left: 60, right: 14, width: undefined }} />}
    </Box>
  );
}

function Legend({ color, label, square }: { color: string; label: string; square?: boolean }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
      <View style={{ width: square ? 10 : 12, height: square ? 10 : 2, borderRadius: square ? 2 : 1, backgroundColor: color }} />
      <T size={11} color={colors.textSub}>
        {label}
      </T>
    </View>
  );
}

// ─── 수익성 ──────────────────────────────────────────────────
function ProfitabilityCard({ fin }: { fin: Financials }) {
  const [term, setTerm] = useState<'opm' | 'npm' | 'roe' | null>(null);
  const recent = fin.annual.slice(-6);
  const series = [
    { key: 'opm' as const, label: '영업이익률', color: chartColors.opm, values: recent.map((r) => r.operating_margin) },
    { key: 'npm' as const, label: '순이익률', color: chartColors.npm, values: recent.map((r) => r.net_margin) },
    { key: 'roe' as const, label: 'ROE', color: chartColors.roe, values: recent.map((r) => r.roe) },
  ];
  return (
    <Box style={{ flex: 1.1, gap: 14, zIndex: term ? 10 : 1 }}>
      <T size={18} weight="bold">
        수익성
      </T>
      <View style={{ flexDirection: 'row', gap: 22, flexWrap: 'wrap', zIndex: 5 }}>
        {series.map((s) => (
          <View key={s.key} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <View style={{ width: 9, height: 9, borderRadius: 5, backgroundColor: s.color }} />
            <T size={12} color={colors.textBody}>
              {s.label}
            </T>
            <QuestionDot onPress={() => setTerm(term === s.key ? null : s.key)} />
            {term === s.key && <TermPopover term={glossary[s.key]} onClose={() => setTerm(null)} style={{ top: 24, left: -8, width: 170 }} />}
          </View>
        ))}
      </View>
      <MultiLineChart periods={recent.map((r) => r.period)} series={series} />
    </Box>
  );
}

// ─── 기업 건전성 (레이더) ────────────────────────────────────
const clamp = (v: number) => Math.max(0, Math.min(1, v));
const HEALTH: { key: TermKey; label: string; field: keyof Stability; unit: string; score: (v: number) => number }[] = [
  { key: 'debt', label: '부채비율', field: 'debt_ratio', unit: '%', score: (v) => clamp(1 - v / 200) },
  { key: 'reserve', label: '유보율', field: 'reserve_ratio', unit: '%', score: (v) => clamp(Math.log10(Math.max(1, v)) / Math.log10(5000)) },
  { key: 'icr', label: '이자보상비율', field: 'interest_coverage', unit: '배', score: (v) => clamp(Math.log10(v + 1) / Math.log10(51)) },
  { key: 'quick', label: '당좌비율', field: 'quick_ratio', unit: '%', score: (v) => clamp(v / 200) },
  { key: 'current', label: '유동비율', field: 'current_ratio', unit: '%', score: (v) => clamp(v / 250) },
];
// 우측 목록 순서(시안): 부채 · 유동 · 당좌 · 이자보상 · 유보
const LIST_ORDER: TermKey[] = ['debt', 'current', 'quick', 'icr', 'reserve'];

function HealthCard({ stability, name }: { stability: Stability; name: string }) {
  const [sel, setSel] = useState<number | null>(null);
  const { isMobile } = useBreakpoint();
  const values = useMemo(() => HEALTH.map((h) => h.score(stability[h.field] as number)), [stability]);
  const selected = sel !== null ? HEALTH[sel] : null;
  const fmt = (h: (typeof HEALTH)[number]) => `${num(stability[h.field] as number)}${h.unit}`;

  return (
    <Box style={{ flex: 1, gap: 8 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <T size={18} weight="bold">
          기업 건전성
        </T>
        <T size={11} color={colors.textSub}>
          {stability.as_of.replace('-', '년 ')}월 기준
        </T>
      </View>
      <View style={{ flexDirection: isMobile ? 'column' : 'row', alignItems: 'center', gap: 12 }}>
        <RadarChart axes={HEALTH.map((h) => h.label)} values={values} highlight={sel} size={270} onPressAxis={(i) => setSel(sel === i ? null : i)} />
        <View style={{ flex: 1, alignSelf: 'stretch', gap: 6, paddingTop: 8 }}>
          <View style={{ flexDirection: 'row', gap: 10, marginBottom: 6 }}>
            <Legend color={chartColors.radar} label={name} square />
            <Legend color={colors.danger} label="선택" square />
          </View>
          {LIST_ORDER.map((k) => {
            const i = HEALTH.findIndex((h) => h.key === k);
            const h = HEALTH[i];
            const on = sel === i;
            return (
              <Pressable key={k} onPress={() => setSel(on ? null : i)} style={{ height: 28, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <T size={12} weight={on ? 'semibold' : 'regular'} color={on ? colors.danger : colors.textBody}>
                    {h.label}
                  </T>
                  <QuestionDot active={on} onPress={() => setSel(on ? null : i)} />
                </View>
                <T size={12} weight={on ? 'semibold' : 'regular'} color={on ? colors.danger : colors.textBody} tabular>
                  {fmt(h)}
                </T>
              </Pressable>
            );
          })}
          <View style={{ backgroundColor: '#F7F8FA', borderRadius: 12, padding: 12, gap: 4, marginTop: 8 }}>
            {selected ? (
              <>
                <T size={12} weight="semibold" color={colors.danger}>
                  {selected.label} · {fmt(selected)}
                </T>
                <T size={11} color={colors.textBody} lh={1.6}>
                  {glossary[selected.key].desc}
                </T>
                <T size={11} color={colors.textSub}>
                  {(glossary[selected.key] as Term).formula}
                </T>
              </>
            ) : (
              <>
                <T size={12} weight="semibold">
                  {name} 재무 건전성
                </T>
                <T size={11} color={colors.textBody} lh={1.6}>
                  바깥쪽으로 갈수록 안정적이에요. 지표 옆 ?를 누르면 설명이 나와요.
                </T>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                  <Icon name="info" size={11} color={colors.textMuted} />
                  <T size={10} color={colors.textMuted}>
                    바깥 테두리는 메모스톡 자체 기준 · 예시 수치
                  </T>
                </View>
              </>
            )}
          </View>
        </View>
      </View>
    </Box>
  );
}
