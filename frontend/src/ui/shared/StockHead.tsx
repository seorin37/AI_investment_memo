import React, { useState } from 'react';
import { StyleSheet, View, useWindowDimensions } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { appColor, fpx, ft, webColor } from '@/ui/theme';
import { Sparkline } from './Sparkline';
import type { StockHeadProps } from './StockHead.types';
import { StockLogo } from './StockLogo';

const won = (n: number) => Math.round(n).toLocaleString('ko-KR');
/* 165deg */
const SIN = Math.sin((165 * Math.PI) / 180);
const COS = -Math.cos((165 * Math.PI) / 180);
const pct = (n: number) => Math.abs(n).toFixed(2);

/**
 * 앱 종목 카드 (원본 memo.html .stock: 라운드 24 · 안쪽 18/18/14 · 바탕 165° #F3F4F6 → #E2E4E9 · 그림자 0 8px 20px -14px .25
 * 1줄: 로고 40 · 이름 17px 700 · 코드 12px #575B63 · 오른쪽 보유 태그 (흰 · 라운드 7 · 3/8 · 12px 600)
 * 2줄(위 12): 가격 27px 800 자간 -0.5 · 등락 13px (상승 #E5323B) · 오른쪽 작은 선 120×44
 * 3줄(위 12): 'MM.DD 종가 기준' 11.5px #9A9EA7). 바깥 여백(좌우 16)은 부모가.
 */
export function AppStockCard({ loading, ...s }: StockHeadProps & { loading?: boolean }) {
  const { width: W } = useWindowDimensions();
  /* 첫 그림은 화면 폭으로 짐작하고, 재면 그 값으로 */
  const [box, setBox] = useState({ w: W - 32, h: 178 });
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

/**
 * 웹 종목 머리 (원본 board.tsx StockHead: 높이 64 · 오른쪽 8
 * 왼쪽: 로고 32 라운드 9.6 + 이름 30/40 bold #191F28 · 아래 '코드 · 시장' 13/20 #6B7684 + 태그(#E8EDF5 · 라운드 6 · 8/3 · 13/20 medium '보유 중'/'관심')
 * 오른쪽: 가격 26/35 bold · 등락 13/20 bold · 'MM.DD 종가 기준' 13/20 #6B7684 · 사이 24 · 미니 차트 116×64)
 */
export function WebStockHead(s: StockHeadProps) {
  const up = s.change >= 0;
  const c = up ? webColor.up : webColor.down;
  const lf = s.logo.length > 2 ? 9 : s.logo.length > 1 ? 10.9 : 13.6;
  return (
    <View style={st.web}>
      <View style={st.wl}>
        <View style={st.wn}>
          <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={32} radius={9.6} fontSize={lf} variant="webSide" />
          <Text style={st.wname} numberOfLines={1}>
            {s.name}
          </Text>
        </View>
        <View style={st.wsub}>
          <Text style={st.wcode}>
            {s.stock_code} · {s.market}
          </Text>
          <View style={st.wtag}>
            <Text style={st.wtagT}>{s.status === 'holding' ? '보유 중' : '관심'}</Text>
          </View>
        </View>
      </View>
      <View style={st.wr}>
        <View style={st.wprice}>
          <Text style={st.wp}>{won(s.price)}원</Text>
          <Text style={[st.wchg, { color: c }]}>
            {up ? '+' : '-'}
            {won(Math.abs(s.change))}
            {'  '}
            {up ? '+' : '-'}
            {pct(s.change_pct)}%
          </Text>
          <Text style={st.wcode}>{s.as_of} 종가 기준</Text>
        </View>
        <Sparkline data={s.closes} color={c} variant="webMini" />
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  card: { borderRadius: 24, paddingTop: 18, paddingHorizontal: 18, paddingBottom: 14, overflow: 'hidden', backgroundColor: '#ECEDF1' },
  flex: { flex: 1, minWidth: 0 },
  r1: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  name: { ...ft(17), fontWeight: '700', color: appColor.ink },
  code: { ...ft(12), color: appColor.ink2, marginTop: 4 },
  hold: { borderRadius: 7, backgroundColor: appColor.surface, paddingVertical: 3, paddingHorizontal: 8 },
  holdT: { ...ft(12), fontWeight: '600', color: appColor.ink },
  hide: { opacity: 0 },
  r2: { flexDirection: 'row', alignItems: 'flex-end', marginTop: 12 },
  price: { ...ft(27), fontWeight: '800', letterSpacing: -0.5, color: appColor.ink },
  chg: { ...ft(13), marginTop: 2 },
  note: { ...ft(11.5), color: appColor.ink3, marginTop: 12 },
  web: { height: 64, width: '100%', flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', paddingRight: 8, top: -1 },
  wl: { gap: 6, alignItems: 'flex-start', flexShrink: 1 },
  wn: { height: 34, flexDirection: 'row', alignItems: 'center', gap: 10 },
  wname: { ...fpx(30, 40), fontWeight: '700', color: webColor.strong, flexShrink: 1 },
  wsub: { height: 20, flexDirection: 'row', alignItems: 'center', gap: 8 },
  wcode: { ...fpx(13, 20), color: '#6B7684' },
  wtag: { borderRadius: 6, backgroundColor: '#E8EDF5', paddingHorizontal: 8, paddingVertical: 3 },
  wtagT: { ...fpx(13, 20), fontWeight: '500', color: '#000000' },
  wr: { flexDirection: 'row', alignItems: 'flex-start', gap: 24 },
  wprice: { alignItems: 'flex-end', gap: 2 },
  wp: { ...fpx(26, 35), fontWeight: '700', color: webColor.strong },
  wchg: { ...fpx(13, 20), fontWeight: '700' },
});
