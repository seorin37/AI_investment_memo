import React from 'react';
import { StyleSheet, View } from 'react-native';
import type { StockHeadProps } from '@/ui/shared/StockHead.types';
import { PriceNoteHead } from '../PriceNoteHead';
import { AppStockCard } from './StockCard';

/**
 * 앱 종목 상세 위 카드 — 메모 보드 · 기업정보 탭이 같이 씀 (자리 · 그림자 · 시세가 같아서 탭을 바꿔도 그대로).
 * 위 6 · 좌우 16 · 그림자 0 8 20 -14 rgba(0,0,0,.25). loading: 시세를 받기 전에는 숫자 자리를 비워 둠
 */
export function AppStockTop({ stock, priceNote, loading, company }: { stock: StockHeadProps; priceNote?: string; loading?: boolean; company?: boolean }) {
  return <View style={st.wrap}>{priceNote ? <PriceNoteHead stock={stock} note={priceNote} variant="app" /> : <AppStockCard {...stock} loading={loading} company={company} />}</View>;
}

const st = StyleSheet.create({
  wrap: { marginTop: 6, marginHorizontal: 16, borderRadius: 24, backgroundColor: '#ECEDF1', boxShadow: '0px 8px 20px -14px rgba(0,0,0,0.25)' },
});
