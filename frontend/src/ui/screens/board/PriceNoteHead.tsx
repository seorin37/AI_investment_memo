import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { StockLogo } from '@/ui/shared/StockLogo';
import type { StockHeadProps } from '@/ui/shared/StockHead.types';
import { appColor, fpx, ft, webColor } from '@/ui/theme';

/**
 * 시세가 없을 때의 보드 종목 머리 (2026-11-21). 가격·등락 숫자 대신 미연결 안내.
 * 기업정보도 쓰는 공용 StockHead 는 건드리지 않으려고 보드 안에 따로 둔다.
 */
export function PriceNoteHead({ stock: s, note, variant }: { stock: StockHeadProps; note: string; variant: 'app' | 'web' }) {
  const web = variant === 'web';
  return (
    <View style={web ? st.web : st.app}>
      <View style={st.row}>
        <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={web ? 32 : 40} variant={web ? 'webSide' : 'app'} />
        <View style={st.flex}>
          <Text style={web ? st.wname : st.name} numberOfLines={1}>{s.name}</Text>
          <Text style={web ? st.wcode : st.code} numberOfLines={1}>{s.stock_code} · {s.market}</Text>
        </View>
      </View>
      <Text style={web ? st.wnote : st.note}>{note}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  app: { borderRadius: 24, paddingTop: 18, paddingHorizontal: 18, paddingBottom: 16, backgroundColor: '#ECEDF1', gap: 14 },
  web: { minHeight: 64, width: '100%', gap: 6 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  flex: { flex: 1, minWidth: 0 },
  name: { ...ft(17), fontWeight: '700', color: appColor.ink },
  code: { ...ft(12), color: appColor.ink2, marginTop: 4 },
  note: { ...ft(13), color: appColor.ink2 },
  wname: { ...fpx(30, 40), fontWeight: '700', color: webColor.strong },
  wcode: { ...fpx(13, 20), color: '#6B7684' },
  wnote: { ...fpx(13, 20), color: '#6B7684' },
});
