import React, { useMemo, useState } from 'react';
import { Linking, Platform, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Sparkline } from '@/components/charts/Sparkline';
import { FlagDot, Icon } from '@/components/icons/Icon';
import { CountBadge, Hoverable, Loading } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useCalendar, useCreateCalendarEvent, useMarketOverview, useMyStocks, useNews } from '@/hooks/queries';
import { useBreakpoint, useMarketColors } from '@/hooks/useLayout';
import { hhmm, isSameDay, num, relative, WEEKDAYS, ymd } from '@/lib/format';
import { colors, fonts, shadow } from '@/theme/tokens';
import type { CalendarCategory, IndexRange, MarketIndex } from '@/types/models';

// ─── 시장 지수 · 환율 (+ 매크로 띠, D안) ────────────────────────
const RANGE_TABS: { key: IndexRange; label: string }[] = [
  { key: '1D', label: '1일' },
  { key: '1W', label: '1주' },
  { key: '1M', label: '1달' },
  { key: '1Y', label: '1년' },
];

export function MarketWidget({ showMacro = true }: { showMacro?: boolean }) {
  const { data, isLoading } = useMarketOverview();
  const { isMobile } = useBreakpoint();
  const mc = useMarketColors();
  if (isLoading || !data) return <Loading height={190} />;
  return (
    <View style={{ gap: 12 }}>
      <View style={{ flexDirection: isMobile ? 'column' : 'row', gap: 16 }}>
        {data.indices.map((i) => (
          <IndexCard key={i.key} index={i} />
        ))}
      </View>
      {showMacro && (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', backgroundColor: colors.surface, borderRadius: 16, borderWidth: 1, borderColor: '#EEF0F3', paddingVertical: 12, paddingHorizontal: 6 }}>
          {data.macro.map((m, idx) => (
            <View key={m.key} style={{ flex: 1, minWidth: 110, paddingHorizontal: 14, borderLeftWidth: idx === 0 ? 0 : 1, borderColor: '#EEF0F3', gap: 2 }}>
              <T size={11} color={colors.textSub}>
                {m.label}
              </T>
              <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 6 }}>
                <T size={14} weight="bold" tabular>
                  {m.unit === '$' ? `$${num(m.value, m.value < 100 ? 1 : 0)}` : `${m.value.toFixed(2)}${m.unit}`}
                </T>
                <T size={11} color={mc.of(m.change)} tabular>
                  {m.change === 0 ? '보합' : `${m.change > 0 ? '+' : '−'}${Math.abs(m.change).toFixed(m.unit === '%' ? 2 : 1)}${m.unit === '%' ? '%p' : '%'}`}
                </T>
              </View>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

function IndexCard({ index }: { index: MarketIndex }) {
  const [range, setRange] = useState<IndexRange>('1D');
  const [w, setW] = useState(0);
  const mc = useMarketColors();
  const color = mc.of(index.change);
  const series = index.series[range];
  return (
    <View
      onLayout={(e) => setW(e.nativeEvent.layout.width)}
      style={{ flex: 1, backgroundColor: colors.surface, borderRadius: 20, borderWidth: 1, borderColor: '#F0F1F4', padding: 16, paddingBottom: 12, gap: 2, ...shadow.card }}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <FlagDot flag={index.flag} size={11} />
        <T size={10} color={colors.textBody}>
          {index.label}
        </T>
      </View>
      <T size={24} weight="bold" tabular>
        {num(index.value, 2)}
      </T>
      <View style={{ flexDirection: 'row', gap: 6 }}>
        <T size={10} color={color} tabular>
          {index.change > 0 ? '+' : '−'}
          {Math.abs(index.change).toFixed(2)} ({index.change_pct > 0 ? '+' : '−'}
          {Math.abs(index.change_pct).toFixed(2)}%)
        </T>
        <T size={10} color={colors.textMuted}>
          오늘
        </T>
      </View>
      <View style={{ marginVertical: 8 }}>{w > 0 && <Sparkline data={series} width={w - 32} height={56} color={color} baseline={series[0]} />}</View>
      <View style={{ flexDirection: 'row', backgroundColor: '#F6F7F9', borderRadius: 8, padding: 2 }}>
        {RANGE_TABS.map((t) => {
          const on = t.key === range;
          return (
            <Hoverable key={t.key} accessibilityRole="tab" accessibilityState={{ selected: on }} onPress={() => setRange(t.key)} style={[{ flex: 1, height: 22, borderRadius: 6, alignItems: 'center', justifyContent: 'center' }, on && { backgroundColor: colors.surface, ...shadow.card }]} hoverStyle={!on && { backgroundColor: colors.brandSoft }}>
              <T size={10} weight={on ? 'semibold' : 'regular'} color={on ? colors.brand : colors.textSub} lh={1}>
                {t.label}
              </T>
            </Hoverable>
          );
        })}
      </View>
    </View>
  );
}

// ─── 업데이트 (종목별 새 소식) ────────────────────────────────
export function UpdatesWidget() {
  const router = useRouter();
  const { data: stocks, isLoading } = useMyStocks();
  return (
    <View style={{ flexGrow: 1, backgroundColor: colors.surface, borderRadius: 24, borderWidth: 1, borderColor: '#F0F1F4', padding: 22, gap: 6, ...shadow.card }}>
      <T size={20} weight="semibold">
        업데이트
      </T>
      <T size={12} color={colors.textSub} style={{ marginBottom: 6 }}>
        내 종목의 새로운 소식
      </T>
      {isLoading && <Loading />}
      <View style={{ gap: 12 }}>
        {stocks?.map((s) => (
          <Hoverable
            key={s.code}
            onPress={() => router.navigate(`/updates/${s.code}`)}
            style={{ borderRadius: 12, borderWidth: 1, borderColor: '#E5E8EB', padding: 12, paddingVertical: 14, flexDirection: 'row', alignItems: 'center', gap: 8 }}
            hoverStyle={{ borderColor: colors.brand, backgroundColor: colors.brandSoft }}
          >
            <View style={{ flex: 1, gap: 8 }}>
              <T size={15} weight="semibold">
                {s.name}
              </T>
              <T size={12} color={colors.textSub}>
                {s.status === 'holding' ? '보유' : '관심'} · {s.unread_updates > 0 ? `새 업데이트 ${s.unread_updates}건` : '모두 확인했어요'}
              </T>
            </View>
            <CountBadge count={s.unread_updates} />
          </Hoverable>
        ))}
      </View>
      <View style={{ flex: 1, minHeight: 16 }} />
      <T size={12} color={colors.textSub}>
        공시, 뉴스, 실적 소식을{'\n'}종목별로 모아 확인하세요.
      </T>
      <Hoverable onPress={() => router.navigate('/updates')} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 10 }}>
        <T size={13} weight="medium" color={colors.brand}>
          전체 업데이트 보기
        </T>
        <Icon name="arrowRight" size={13} color={colors.brand} />
      </Hoverable>
    </View>
  );
}

// ─── 주요 증시 일정 (캘린더) ──────────────────────────────────
const DOT: Record<CalendarCategory, string> = { holiday: '#E5484D', market: '#477BFF', mine: '#986BEE' };
const CAL_TABS = [
  { key: 'all', label: '전체' },
  { key: 'market', label: '증시' },
  { key: 'mine', label: '내 일정' },
] as const;

export function CalendarWidget() {
  const today = new Date();
  const [cursor, setCursor] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const [selected, setSelected] = useState(today);
  const [tab, setTab] = useState<(typeof CAL_TABS)[number]['key']>('all');
  const [draft, setDraft] = useState<string | null>(null);
  const month = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, '0')}`;
  const { data: events = [] } = useCalendar(month);
  const createEvent = useCreateCalendarEvent();

  const filtered = events.filter((e) => tab === 'all' || (tab === 'market' ? e.category !== 'mine' : e.category === 'mine'));
  const days = useMemo(() => {
    const first = new Date(cursor);
    const start = new Date(first);
    start.setDate(1 - first.getDay());
    return Array.from({ length: 35 }, (_, i) => {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      return d;
    });
  }, [cursor]);
  const dayEvents = filtered.filter((e) => e.date === ymd(selected));

  const commit = () => {
    const t = draft?.trim();
    if (t) createEvent.mutate({ date: ymd(selected), title: t });
    setDraft(null);
  };

  return (
    <View style={{ flexGrow: 1, backgroundColor: colors.surface, borderRadius: 24, borderWidth: 1, borderColor: '#F0F1F4', padding: 24, gap: 14, ...shadow.card }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <T size={20} weight="semibold">
          주요 증시 일정
        </T>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
          <Hoverable onPress={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} style={{ padding: 4 }}>
            <Icon name="chevronLeft" size={14} color={colors.brand} />
          </Hoverable>
          <T size={17} weight="medium">
            {cursor.getFullYear()}년 {cursor.getMonth() + 1}월
          </T>
          <Hoverable onPress={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} style={{ padding: 4 }}>
            <Icon name="chevronRight" size={14} color={colors.brand} />
          </Hoverable>
          <Hoverable
            onPress={() => {
              setCursor(new Date(today.getFullYear(), today.getMonth(), 1));
              setSelected(today);
            }}
            style={{ height: 30, paddingHorizontal: 14, borderRadius: 15, backgroundColor: colors.brandSoft, justifyContent: 'center' }}
          >
            <T size={12} weight="medium" color={colors.brand} lh={1}>
              오늘
            </T>
          </Hoverable>
        </View>
      </View>
      <View style={{ flexDirection: 'row', gap: 6 }}>
        {CAL_TABS.map((t) => (
          <Hoverable key={t.key} accessibilityRole="tab" accessibilityState={{ selected: tab === t.key }} onPress={() => setTab(t.key)} style={{ height: 30, paddingHorizontal: 14, borderRadius: 15, justifyContent: 'center', backgroundColor: tab === t.key ? colors.brandSoft : 'transparent' }} hoverStyle={{ backgroundColor: colors.brandSoft }}>
            <T size={12} weight="medium" color={colors.brand} lh={1}>
              {t.label}
            </T>
          </Hoverable>
        ))}
      </View>
      <View>
        <View style={{ flexDirection: 'row' }}>
          {WEEKDAYS.map((w, i) => (
            <T key={w} size={11} color={i === 0 ? '#E5484D' : i === 6 ? colors.blue : colors.textSub} style={{ flex: 1, textAlign: 'center' }}>
              {w}
            </T>
          ))}
        </View>
        {[0, 1, 2, 3, 4].map((row) => (
          <View key={row} style={{ flexDirection: 'row', marginTop: 6 }}>
            {days.slice(row * 7, row * 7 + 7).map((d) => {
              const inMonth = d.getMonth() === cursor.getMonth();
              const isToday = isSameDay(d, today);
              const isSel = isSameDay(d, selected);
              const evs = filtered.filter((e) => e.date === ymd(d));
              const wd = d.getDay();
              const holiday = evs.some((e) => e.category === 'holiday');
              const fg = !inMonth ? '#D3D7DE' : wd === 0 || holiday ? '#E5484D' : wd === 6 ? colors.blue : colors.text;
              return (
                <Hoverable key={d.toISOString()} onPress={() => setSelected(d)} style={{ flex: 1, alignItems: 'center', height: 36, gap: 2 }}>
                  <View
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: 15,
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderWidth: isToday ? 1.5 : 0,
                      borderColor: colors.brand,
                      backgroundColor: isToday || isSel ? colors.brandSoft : 'transparent',
                    }}
                  >
                    <T size={12} color={fg} weight={isToday ? 'semibold' : 'regular'} lh={1}>
                      {d.getDate()}
                    </T>
                  </View>
                  <View style={{ flexDirection: 'row', gap: 2, height: 4, marginTop: -4 }}>
                    {inMonth && evs.slice(0, 3).map((e) => <View key={e.id} style={{ width: 4, height: 4, borderRadius: 2, backgroundColor: DOT[e.category] }} />)}
                  </View>
                </Hoverable>
              );
            })}
          </View>
        ))}
      </View>
      <View style={{ gap: 6 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <T size={12} weight="medium">
            {selected.getMonth() + 1}월 {selected.getDate()}일 ({WEEKDAYS[selected.getDay()]})
          </T>
          <Hoverable onPress={() => setDraft(draft === null ? '' : null)}>
            <T size={11} color={colors.brand}>
              + 일정 추가
            </T>
          </Hoverable>
        </View>
        {draft !== null && (
          <TextInput
            autoFocus
            value={draft}
            onChangeText={setDraft}
            onSubmitEditing={commit}
            placeholder="일정 입력 후 Enter (내 일정)"
            placeholderTextColor={colors.placeholder}
            style={[{ height: 34, borderRadius: 8, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 10, fontFamily: fonts.regular, fontSize: 13, color: colors.text }, Platform.OS === 'web' && ({ outlineStyle: 'none' } as object)]}
          />
        )}
        {dayEvents.length === 0 ? (
          <>
            <T size={13} weight="semibold">
              등록된 일정이 없어요
            </T>
            <T size={10} color={colors.textSub}>
              상단 또는 날짜 옆에서 일정을 추가해보세요.
            </T>
          </>
        ) : (
          dayEvents.map((e) => (
            <View key={e.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: DOT[e.category] }} />
              <T size={13} weight="medium">
                {e.title}
              </T>
            </View>
          ))
        )}
      </View>
    </View>
  );
}

// ─── 뉴스 (C안 · 헤드라인 강조형) ─────────────────────────────
export function NewsWidget() {
  const { data, isLoading } = useNews();
  const open = (url: string) => void Linking.openURL(url);
  const top = data?.[0];
  return (
    <View style={{ flexGrow: 1, backgroundColor: colors.surface, borderRadius: 24, borderWidth: 1, borderColor: '#F0F1F4', padding: 22, gap: 12, ...shadow.card }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <T size={20} weight="semibold">
          뉴스
        </T>
        <T size={11} color={colors.textSub}>
          오늘 · {data?.length ?? 0}건
        </T>
      </View>
      {isLoading && <Loading />}
      {top && (
        <Hoverable onPress={() => open(top.url)} style={{ backgroundColor: colors.blueSoft, borderRadius: 16, padding: 14, gap: 8 }} hoverStyle={{ backgroundColor: '#E5ECFF' }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <View style={{ backgroundColor: '#FFF', borderRadius: 4, paddingHorizontal: 8, height: 20, justifyContent: 'center' }}>
              <T size={10} weight="medium" lh={1}>
                {top.source}
              </T>
            </View>
            <T size={11} color={colors.blue}>
              {hhmm(top.published_at)} · {relative(top.published_at)}
            </T>
          </View>
          <T size={19} weight="bold" color="#1F3A8A" lh={1.35}>
            {top.title}
          </T>
          <T size={12} color={colors.blue}>
            원문 읽기 ↗
          </T>
        </Hoverable>
      )}
      <View>
        {data?.slice(1).map((n) => (
          <Hoverable key={n.id} onPress={() => open(n.url)} style={{ flexDirection: 'row', gap: 12, paddingVertical: 11, borderTopWidth: 1, borderColor: '#EEF0F3' }} hoverStyle={{ backgroundColor: '#FAFAFB' }}>
            <T size={12} color={colors.textSub} style={{ width: 36 }} tabular>
              {hhmm(n.published_at)}
            </T>
            <View style={{ flex: 1, gap: 2 }}>
              <T size={14} weight="medium" numberOfLines={2}>
                {n.title}
              </T>
              <T size={10} color={colors.textSub}>
                {n.source}
              </T>
            </View>
            <Icon name="external" size={13} color={colors.textMuted} />
          </Hoverable>
        ))}
      </View>
    </View>
  );
}
