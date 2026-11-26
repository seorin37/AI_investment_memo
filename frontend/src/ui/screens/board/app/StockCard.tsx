import React, { useState } from 'react';
import { StyleSheet, View, useWindowDimensions } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { Sparkline } from '@/ui/shared/Sparkline';
import { StockLogo } from '@/ui/shared/StockLogo';
import type { StockHeadProps } from '@/ui/shared/StockHead.types';
import { nf } from '@/ui/shared/app/nf';
import { appColor } from '@/ui/theme';

const won = (n: number) => Math.round(n).toLocaleString('ko-KR');
/* 165deg */
const SIN = Math.sin((165 * Math.PI) / 180);
const COS = -Math.cos((165 * Math.PI) / 180);
const pct = (n: number) => Math.abs(n).toFixed(2);

/**
 * 앱 종목 카드 (원본 memo.html .stock: 라운드 24 · 안쪽 18/18/14 · 바탕 165° #F3F4F6 → #E2E4E9)
 * 두 탭(메모 보드 · 기업정보)이 같은 글자 크기·굵기 (메모 보드 원본 기준: 주가 800 · 보유 600 · 등락 400)
 * 높이 160 = 18 + 로고 40 + 12 + 가격 33 + 2 + 등락 15 + 12 + 날짜 14 + 14
 * shared/StockHead 의 앱 카드와 같고 줄 높이만 원본 값 (그쪽은 웹과 같은 파일이라 따로 둠). 바깥 여백(좌우 16)은 부모가.
 */
export function AppStockCard({ loading, ...s }: StockHeadProps & { loading?: boolean }) {
  const { width: W } = useWindowDimensions();
  /* 첫 그림은 화면 폭으로 짐작하고, 재면 그 값으로 */
  const [box, setBox] = useState({ w: W - 32, h: 160 });
  /* CSS 165deg 선: 길이 = w·sin + h·cos (가운데 기준 반씩) */
  const half = (box.w * SIN + box.h * COS) / 2;
  const gx = half * SIN;
  const gy = half * COS;
  const up = s.change >= 0;
  const c = up ? '#E5323B' : appColor.down;
  return (
    <View
      style={st.card}
      onLayout={(e) => {
        const { width: w, height: h } = e.nativeEvent.layout;
        setBox((b) => (b.w === w && b.h === h ? b : { w, h }));
      }}
    >
      <Svg style={StyleSheet.absoluteFill} width="100%" height="100%">
        <Defs>
          {/* 165deg: 위·약간 왼쪽 → 아래·약간 오른쪽 */}
          <LinearGradient id="stockcard" gradientUnits="userSpaceOnUse" x1={box.w / 2 - gx} y1={box.h / 2 - gy} x2={box.w / 2 + gx} y2={box.h / 2 + gy}>
            <Stop offset="0" stopColor="#F3F4F6" />
            <Stop offset="1" stopColor="#E2E4E9" />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#stockcard)" />
      </Svg>
      <View style={st.r1}>
        <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={40} variant="app" />
        <View style={st.flex}>
          <Text style={st.name} numberOfLines={1}>
            {s.name}
          </Text>
          <Text style={st.code} numberOfLines={1}>
            {s.stock_code} · {s.market}
          </Text>
        </View>
        <View style={st.hold}>
          <Text style={st.holdT}>{s.status === 'holding' ? '보유' : '관심'}</Text>
        </View>
      </View>
      <View style={[st.r2, loading && st.hide]}>
        <View style={st.flex}>
          <Text style={st.price} numberOfLines={1}>
            {won(s.price)}원
          </Text>
          <Text style={[st.chg, { color: c }]} numberOfLines={1}>
            {up ? '+' : '-'}
            {won(Math.abs(s.change))} ({up ? '+' : '-'}
            {pct(s.change_pct)}%)
          </Text>
        </View>
        <Sparkline data={s.closes} color={c} variant="appCard" />
      </View>
      <Text style={[st.note, loading && st.hide]}>{s.as_of} 종가 기준</Text>
    </View>
  );
}

const st = StyleSheet.create({
  card: { borderRadius: 24, paddingTop: 18, paddingHorizontal: 18, paddingBottom: 14, overflow: 'hidden', backgroundColor: '#ECEDF1' },
  flex: { flex: 1, minWidth: 0 },
  r1: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  name: { ...nf(17), fontWeight: '700', color: appColor.ink },
  code: { ...nf(12), color: appColor.ink2, marginTop: 4 },
  hold: { borderRadius: 7, backgroundColor: appColor.surface, paddingVertical: 3, paddingHorizontal: 8 },
  holdT: { ...nf(12), fontWeight: '600', color: appColor.ink },
  hide: { opacity: 0 },
  r2: { flexDirection: 'row', alignItems: 'flex-end', marginTop: 12 },
  price: { ...nf(27), fontWeight: '800', letterSpacing: -0.5, color: appColor.ink },
  chg: { ...nf(13), marginTop: 2 },
  note: { ...nf(11.5), color: appColor.ink3, marginTop: 12 },
});
