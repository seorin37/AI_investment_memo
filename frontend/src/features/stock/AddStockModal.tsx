import React, { useState } from 'react';
import { Pressable, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Sheet } from '@/components/ui/Modal';
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
    <Sheet visible onClose={onClose} width={520} padding={28} radius={20}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <T size={20} weight="bold">
          종목 추가
        </T>
        <Pressable onPress={onClose} hitSlop={8}>
          <T size={14} color={colors.textBody}>
            닫기
          </T>
        </Pressable>
      </View>

      <Step n={1} label="종목 검색" />
      <TextField
        autoFocus
        value={q}
        onChangeText={(t) => {
          setQ(t);
          setPicked(null);
        }}
        placeholder="종목명 또는 종목코드"
        style={{ height: 48, borderColor: q ? colors.text : colors.border, backgroundColor: q ? '#F6F7F9' : colors.surface }}
      />
      <View style={{ marginTop: 8, minHeight: 40, gap: 2 }}>
        {q.trim() && results.length === 0 && !isFetching && (
          <T size={13} color={colors.textMuted} style={{ padding: 12 }}>
            검색 결과가 없어요
          </T>
        )}
        {results.slice(0, 5).map((s) => {
          const active = picked?.code === s.code;
          return (
            <Hoverable
              key={s.code}
              onPress={() => setPicked(s)}
              style={[{ height: 42, borderRadius: 8, paddingHorizontal: 14, flexDirection: 'row', alignItems: 'center', gap: 10 }, active && { backgroundColor: '#F1F1F2' }]}
              hoverStyle={{ backgroundColor: '#F6F6F7' }}
            >
              <T size={14} weight={active ? 'bold' : 'medium'}>
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
              onPress={() => setStatus(k)}
              style={{ flex: 1, height: 42, borderRadius: radius.sm, backgroundColor: active ? colors.black : '#F5F5F6', alignItems: 'center', justifyContent: 'center' }}
            >
              <T size={14} weight="bold" color={active ? '#FFF' : '#9A9AA0'}>
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
        <Button label="취소" variant="secondary" size="sm" onPress={onClose} style={{ height: 40, paddingHorizontal: 26, backgroundColor: '#F2F2F3' }} />
        <Button label="확인" size="sm" onPress={submit} disabled={!picked} loading={add.isPending} style={{ height: 40, paddingHorizontal: 26 }} />
      </View>
    </Sheet>
  );
}

function Step({ n, label }: { n: number; label: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10, marginBottom: 12 }}>
      <View style={{ width: 20, height: 20, borderRadius: 10, backgroundColor: colors.black, alignItems: 'center', justifyContent: 'center' }}>
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
