import React from 'react';
import { Pressable, View } from 'react-native';
import { Sparkline } from '@/components/charts/Sparkline';
import { Button } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useAddStock, useQuote, useUpdateStock } from '@/hooks/queries';
import { useBreakpoint, useMarketColors } from '@/hooks/useLayout';
import { asOfLabel, num, signed, signedPct } from '@/lib/format';
import { colors } from '@/theme/tokens';
import type { MyStock, StockMaster } from '@/types/models';

/** 보드·기업정보 공통 헤더 — 이름 · 코드 · 보유/관심 / 현재가 · 등락 · 스파크라인 */
export function StockHeader({ stock, mine }: { stock: StockMaster; mine: MyStock | undefined }) {
  const { data: quote } = useQuote(stock.code);
  const mc = useMarketColors();
  const { isMobile, isDesktop } = useBreakpoint();
  const update = useUpdateStock();
  const add = useAddStock();

  return (
    <View style={{ flexDirection: isDesktop ? 'row' : 'column', justifyContent: 'space-between', alignItems: isDesktop ? 'center' : 'stretch', gap: 16 }}>
      <View style={{ gap: 8, flexShrink: 1, minWidth: 0 }}>
        <T size={isMobile ? 28 : 32} weight="bold">
          {stock.name}
        </T>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <T size={14} color={colors.textSub}>
            {stock.code} · {stock.market}
          </T>
          {mine ? (
            <Pressable
              accessibilityLabel="보유/관심 전환"
              onPress={() => update.mutate({ code: stock.code, patch: { status: mine.status === 'holding' ? 'watching' : 'holding' } })}
              style={{ backgroundColor: '#E8EDF5', borderRadius: 4, paddingHorizontal: 8, height: 26, justifyContent: 'center' }}
            >
              <T size={13} weight="medium" color={colors.textBody} lh={1.1}>
                {mine.status === 'holding' ? '보유 중' : '관심'}
              </T>
            </Pressable>
          ) : (
            <Button label="내 종목에 추가" size="sm" variant="outline" icon="plus" onPress={() => add.mutate({ code: stock.code, status: 'watching' })} loading={add.isPending} />
          )}
        </View>
      </View>

      {quote && (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 20, flexShrink: 0 }}>
          <View style={{ alignItems: isDesktop ? 'flex-end' : 'flex-start' }}>
            <T size={isMobile ? 26 : 30} weight="bold" tabular>
              {num(quote.price)}원
            </T>
            <T size={16} weight="semibold" color={mc.of(quote.change)} tabular>
              {signed(quote.change)} {signedPct(quote.change_pct)}
            </T>
            <T size={11} color={colors.textSub}>
              {asOfLabel(quote.as_of)}
            </T>
          </View>
          {isDesktop && <Sparkline data={quote.spark} width={150} height={64} color={mc.of(quote.change)} baseline={quote.spark[0]} />}
        </View>
      )}
    </View>
  );
}
