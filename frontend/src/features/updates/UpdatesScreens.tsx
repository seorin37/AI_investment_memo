import React from 'react';
import { Linking, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Page, PageHeader } from '@/components/layout/Page';
import { Badge, EmptyState, ErrorState, Hoverable, Loading, PillTabs } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useMyStocks, useUpdates } from '@/hooks/queries';
import { useBreakpoint } from '@/hooks/useLayout';
import { relative } from '@/lib/format';
import { colors, updateBadge } from '@/theme/tokens';
import type { MarketUpdate, MyStock, UpdateType } from '@/types/models';

function StockTabs({ active }: { active: string }) {
  const router = useRouter();
  const { data: stocks = [] } = useMyStocks();
  return (
    <View style={{ marginBottom: 24 }}>
      <PillTabs
        items={[{ key: 'all', label: '업데이트' }, ...stocks.map((s) => ({ key: s.code, label: s.name }))]}
        value={active}
        onChange={(k) => router.navigate(k === 'all' ? '/updates' : `/updates/${k}`)}
      />
    </View>
  );
}

export function TypeBadge({ type }: { type: UpdateType }) {
  const b = updateBadge[type];
  return <Badge label={b.label} bg={b.bg} fg={b.fg} />;
}

const openSource = (u: MarketUpdate) => {
  if (u.url) void Linking.openURL(u.url);
};

/** 3.1 최신 업데이트 — 종목별 최신 공시 · 뉴스 · 주가 */
export function UpdatesOverview() {
  const { data: stocks, isLoading } = useMyStocks();
  const { data: updates = [], error, refetch, isRefetching } = useUpdates();
  const router = useRouter();

  const latestByType = (code: string) => {
    const mine = updates.filter((u) => u.stock_code === code);
    const pick = (['disclosure', 'news', 'price'] as UpdateType[]).map((t) => mine.find((u) => u.type === t)).filter(Boolean) as MarketUpdate[];
    return pick;
  };

  // 새 소식이 많은 종목부터
  const ordered = [...(stocks ?? [])].sort((a, b) => b.unread_updates - a.unread_updates);

  return (
    <Page top={80} onRefresh={() => void refetch()} refreshing={isRefetching}>
      <PageHeader title="최신 업데이트" subtitle="내 종목의 공시·뉴스·주가 변동을 모아봤어요" size={28} />
      <StockTabs active="all" />
      {isLoading && <Loading />}
      {error && <ErrorState message="업데이트를 불러오지 못했어요." onRetry={() => void refetch()} />}
      {stocks?.length === 0 && <EmptyState title="아직 추가한 종목이 없어요" desc="사이드바의 '내 종목 +'로 종목을 추가하면 소식이 모여요." />}
      <View style={{ gap: 24, maxWidth: 568 }}>
        {ordered.map((s) => (
          <StockUpdateCard key={s.code} stock={s} items={latestByType(s.code)} onOpenStock={() => router.navigate(`/updates/${s.code}`)} />
        ))}
      </View>
    </Page>
  );
}

function StockUpdateCard({ stock, items, onOpenStock }: { stock: MyStock; items: MarketUpdate[]; onOpenStock: () => void }) {
  return (
    <View style={{ backgroundColor: colors.surface, borderRadius: 20, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 20, paddingTop: 20, paddingBottom: 12 }}>
      <Hoverable onPress={onOpenStock} style={{ gap: 6, paddingBottom: 14, borderBottomWidth: 1, borderColor: colors.borderSoft }} hoverStyle={{ opacity: 0.8 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <T size={18} weight="bold">
            {stock.name}
          </T>
          <Badge label={stock.status === 'holding' ? '보유' : '관심'} bg="#EEF0F3" fg={colors.textBody} size={11} />
          {stock.unread_updates > 0 && (
            <T size={11} color={colors.danger} weight="semibold" style={{ marginLeft: 'auto' }}>
              새 소식 {stock.unread_updates}
            </T>
          )}
        </View>
        <T size={11} color={colors.textSub}>
          {stock.code} · {stock.market}
        </T>
      </Hoverable>
      {items.length === 0 ? (
        <T size={13} color={colors.textMuted} style={{ paddingVertical: 14 }}>
          아직 새 소식이 없어요
        </T>
      ) : (
        items.map((u) => (
          <Hoverable key={u.id} onPress={() => openSource(u)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, height: 34, borderRadius: 6 }} hoverStyle={{ backgroundColor: '#FAFAFB' }}>
            <TypeBadge type={u.type} />
            <T size={14} weight="medium" numberOfLines={1} style={{ flex: 1 }}>
              {u.title}
            </T>
            <T size={11} color={colors.textSub}>
              {relative(u.published_at)}
            </T>
          </Hoverable>
        ))
      )}
    </View>
  );
}

/** 3.2 종목별 최신 업데이트 — 시간순 전체 목록 */
export function StockUpdatesList({ code }: { code: string }) {
  const { data: stocks = [] } = useMyStocks();
  const { data: updates, isLoading, error, refetch, isRefetching } = useUpdates(code);
  const { isMobile } = useBreakpoint();
  const name = stocks.find((s) => s.code === code)?.name ?? code;

  return (
    <Page top={80} onRefresh={() => void refetch()} refreshing={isRefetching}>
      <PageHeader title={`${name} 업데이트`} subtitle={`${name}의 공시·뉴스·주가 변동을 시간순으로 모았어요`} size={28} />
      <StockTabs active={code} />
      {isLoading && <Loading />}
      {error && <ErrorState message="업데이트를 불러오지 못했어요." onRetry={() => void refetch()} />}
      {updates && updates.length === 0 && <EmptyState title="아직 소식이 없어요" />}
      {updates && updates.length > 0 && (
        <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 20, overflow: 'hidden', backgroundColor: colors.surface }}>
          {updates.map((u, i) => (
            <Hoverable
              key={u.id}
              onPress={() => openSource(u)}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 53, paddingHorizontal: 20, paddingVertical: 10, borderTopWidth: i === 0 ? 0 : 1, borderColor: colors.borderSoft }}
              hoverStyle={{ backgroundColor: '#FAFAFB' }}
            >
              {!isMobile && <Badge label={u.stock_name} bg="#F3F4F6" fg={colors.text} />}
              <TypeBadge type={u.type} />
              <T size={14} weight="medium" numberOfLines={isMobile ? 2 : 1} style={{ flex: 1 }}>
                {u.title}
              </T>
              <T size={11} color={colors.textSub}>
                {u.type === 'disclosure' ? 'DART' : u.type === 'price' ? '시세' : '뉴스'} · {relative(u.published_at)}
              </T>
            </Hoverable>
          ))}
        </View>
      )}
    </Page>
  );
}
