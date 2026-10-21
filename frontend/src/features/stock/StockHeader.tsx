import React, { useState } from 'react';
import { Pressable, TextInput, View, Platform } from 'react-native';
import { Sparkline } from '@/components/charts/Sparkline';
import { Button, Hoverable } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useAddStock, useQuote, useUpdateStock } from '@/hooks/queries';
import { useBreakpoint, useMarketColors } from '@/hooks/useLayout';
import { asOfLabel, num, signed, signedPct } from '@/lib/format';
import { colors, fonts } from '@/theme/tokens';
import type { MyStock, StockMaster } from '@/types/models';

/** 종목 헤더 — 이름 · 코드 · 보유/관심 배지 · 태그 / 현재가 · 등락 · 스파크라인 */
export function StockHeader({ stock, mine, large }: { stock: StockMaster; mine: MyStock | undefined; large?: boolean }) {
  const { data: quote } = useQuote(stock.code);
  const mc = useMarketColors();
  const { isMobile } = useBreakpoint();
  const update = useUpdateStock();
  const add = useAddStock();
  const [tagDraft, setTagDraft] = useState<string | null>(null);

  const commitTag = () => {
    const t = tagDraft?.trim().replace(/^#/, '');
    if (t && mine) update.mutate({ code: stock.code, patch: { tags: [...mine.tags, t] } });
    setTagDraft(null);
  };

  return (
    <View style={{ flexDirection: isMobile ? 'column' : 'row', justifyContent: 'space-between', alignItems: isMobile ? 'flex-start' : 'center', gap: 16 }}>
      <View style={{ gap: 8 }}>
        <T size={large ? 36 : 30} weight="bold">
          {stock.name}
        </T>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <T size={large ? 14 : 12} color={colors.textSub}>
            {stock.code} · {stock.market}
          </T>
          {mine ? (
            <Pressable
              accessibilityLabel="보유/관심 전환"
              onPress={() => update.mutate({ code: stock.code, patch: { status: mine.status === 'holding' ? 'watching' : 'holding' } })}
              style={{ backgroundColor: '#E8EDF5', borderRadius: 4, paddingHorizontal: 8, height: large ? 26 : 20, justifyContent: 'center' }}
            >
              <T size={large ? 13 : 12} weight="medium" color={colors.textBody} lh={1.1}>
                {mine.status === 'holding' ? '보유 중' : '관심'}
              </T>
            </Pressable>
          ) : (
            <Button label="내 종목에 추가" size="sm" variant="outline" icon="plus" onPress={() => add.mutate({ code: stock.code, status: 'watching' })} loading={add.isPending} />
          )}
          {mine?.tags.map((t) => (
            <View key={t} style={{ backgroundColor: '#F3F4F6', borderRadius: 4, paddingHorizontal: 8, height: 20, justifyContent: 'center' }}>
              <T size={12} color={colors.textBody} lh={1.1}>
                #{t}
              </T>
            </View>
          ))}
          {mine && !large && (tagDraft === null ? (
            <Hoverable onPress={() => setTagDraft('')} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 4, paddingHorizontal: 8, height: 20, justifyContent: 'center' }} hoverStyle={{ backgroundColor: '#F7F8FA' }}>
              <T size={12} color={colors.textSub} lh={1.1}>
                + 태그
              </T>
            </Hoverable>
          ) : (
            <TextInput
              autoFocus
              value={tagDraft}
              onChangeText={setTagDraft}
              onSubmitEditing={commitTag}
              onBlur={commitTag}
              placeholder="태그 입력"
              placeholderTextColor={colors.placeholder}
              style={[{ height: 22, width: 90, borderWidth: 1, borderColor: colors.borderStrong, borderRadius: 4, paddingHorizontal: 6, fontFamily: fonts.regular, fontSize: 12, color: colors.text }, Platform.OS === 'web' && ({ outlineStyle: 'none' } as object)]}
            />
          ))}
        </View>
      </View>

      {quote && (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 20 }}>
          <View style={{ alignItems: isMobile ? 'flex-start' : 'flex-end' }}>
            <T size={large ? 30 : 26} weight="bold" tabular>
              {num(quote.price)}원
            </T>
            <T size={large ? 16 : 14} weight="semibold" color={mc.of(quote.change)} tabular>
              {signed(quote.change)} {signedPct(quote.change_pct)}
            </T>
            <T size={11} color={colors.textSub}>
              {asOfLabel(quote.as_of)}
            </T>
          </View>
          {!isMobile && <Sparkline data={quote.spark} width={large ? 150 : 120} height={large ? 64 : 56} color={mc.of(quote.change)} baseline={quote.spark[0]} />}
        </View>
      )}
    </View>
  );
}
