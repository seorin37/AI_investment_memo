import React, { useState } from 'react';
import { View } from 'react-native';
import { useRouter } from 'expo-router';
import { Sheet, SheetHeader } from '@/components/ui/Modal';
import { Button, Hoverable, TextField } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useAddStock, useMyStocks, useStockSearch } from '@/hooks/queries';
import { useUI } from '@/store/ui';
import { colors, radius } from '@/theme/tokens';
import type { StockMaster, StockStatus } from '@/types/models';

/** 4. 종목 추가 — ① 종목 검색 ② 구분 선택(보유/관심) ③ 확인 */
export function AddStockModal({ onClose, preset }: { onClose: () => void; preset?: StockMaster }) {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const [q, setQ] = useState(preset?.name ?? '');
  const [picked, setPicked] = useState<StockMaster | null>(preset ?? null);
  const [status, setStatus] = useState<StockStatus>('holding');
  const { data: results = [], isFetching } = useStockSearch(q);
  const { data: mine = [] } = useMyStocks();
  const add = useAddStock();

  const already = picked && mine.find((m) => m.code === picked.code);

  const submit = () => {
    if (!picked) return;
    add.mutate(
      { code: picked.code, status },
      {
        onSuccess: (s) => {
          toast(`${s.name}을(를) ${status === 'holding' ? '보유' : '관심'} 종목에 추가했어요`);
          onClose();
          router.navigate(`/stocks/${s.code}`);
        },
      },
    );
  };

  return (
    <Sheet visible onClose={onClose} width={520} radius={20}>
      <SheetHeader title="종목 추가" onClose={onClose} />

      <Step n={1} label="종목 검색" />
      <TextField
        autoFocus
        value={q}
        onChangeText={(t) => {
          setQ(t);
          setPicked(null);
        }}
        placeholder="종목명 또는 종목코드"
        style={{ backgroundColor: colors.surfaceMuted }}
      />
      <View style={{ marginTop: 8, minHeight: 40, gap: 2 }}>
        {q.trim().length > 0 && results.length === 0 && !isFetching && (
          <T size={13} color={colors.textMuted} style={{ padding: 12 }}>
            검색 결과가 없어요
          </T>
        )}
        {results.slice(0, 5).map((s) => {
          const active = picked?.code === s.code;
          return (
            <Hoverable
              key={s.code}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              onPress={() => setPicked(s)}
              style={[{ height: 42, borderRadius: 8, paddingHorizontal: 14, flexDirection: 'row', alignItems: 'center', gap: 8 }, active && { backgroundColor: colors.brandSoft }]}
              hoverStyle={{ backgroundColor: colors.brandSoft }}
            >
              <T size={14} weight={active ? 'bold' : 'medium'} color={active ? colors.brand : colors.text}>
                {s.name}
              </T>
              <T size={12} color={colors.textMuted}>
                {s.code} · {s.market}
              </T>
              {mine.some((m) => m.code === s.code) && (
                <T size={11} color={colors.brand} style={{ marginLeft: 'auto' }}>
                  이미 추가됨
                </T>
              )}
            </Hoverable>
          );
        })}
      </View>

      <Step n={2} label="구분 선택" />
      <View style={{ flexDirection: 'row', gap: 10 }}>
        {(
          [
            ['holding', '보유'],
            ['watching', '관심'],
          ] as const
        ).map(([k, label]) => {
          const active = status === k;
          return (
            <Hoverable
              key={k}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              onPress={() => setStatus(k)}
              style={{ flex: 1, height: 44, borderRadius: radius.md, backgroundColor: active ? colors.brand : colors.surfaceSubtle, alignItems: 'center', justifyContent: 'center' }}
              hoverStyle={{ opacity: 0.9 }}
            >
              <T size={14} weight="semibold" color={active ? colors.surface : colors.textSub}>
                {label}
              </T>
            </Hoverable>
          );
        })}
      </View>

      <Step n={3} label="확인" />
      <T size={13} color={colors.textSub}>
        {picked
          ? already
            ? `${picked.name}은(는) 이미 ${already.status === 'holding' ? '보유' : '관심'} 종목이에요. 확인을 누르면 구분이 바뀌어요.`
            : `${picked.name} (${picked.code})을(를) ${status === 'holding' ? '보유' : '관심'} 종목으로 추가해요.`
          : '추가할 종목을 검색 결과에서 선택해 주세요.'}
      </T>
      <View style={{ flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 18 }}>
        <Button label="취소" variant="secondary" onPress={onClose} />
        <Button label="확인" onPress={submit} disabled={!picked} loading={add.isPending} />
      </View>
    </Sheet>
  );
}

function Step({ n, label }: { n: number; label: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10, marginBottom: 12 }}>
      <View style={{ width: 20, height: 20, borderRadius: 10, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center' }}>
        <T size={11} weight="bold" color="#FFF" lh={1}>
          {n}
        </T>
      </View>
      <T size={14} weight="bold">
        {label}
      </T>
    </View>
  );
}
