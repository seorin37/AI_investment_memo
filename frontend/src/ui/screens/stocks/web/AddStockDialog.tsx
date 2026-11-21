import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { Text, TextInput } from '@/components/ui/AppText';
import { Sheet } from '@/ui/shared/Sheet';
import { fpx } from '@/ui/theme';
import type { AddStockProps, Hold } from '../MyStocks.types';
import { Keep } from '@/ui/shared/Dark';

type Hover = { pressed: boolean; hovered?: boolean };
const CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';
const cho = (t: string) =>
  [...t]
    .map((c) => {
      const n = c.charCodeAt(0) - 44032;
      return n >= 0 && n < 11172 ? CHO[Math.floor(n / 588)] : c;
    })
    .join('');

/**
 * 웹 종목 추가 창 (원본 overlays.tsx AddStock · 11.16: 휴지통과 같은 680×660 · 같은 머리)
 * 검색칸(포커스면 1.5 검정 테두리) · 처음엔 아직 담지 않은 종목 8개 · 분야 칩 · 이미 있는 종목은 흐리게 · 어떻게 담을까요? · [관심 종목으로 추가]
 * 내 종목 화면 · 사이드바 + 에서 같이 씀. Enter = 추가.
 */
export function WebAddStockDialog({ open, mine, universe, onClose, onAdd }: AddStockProps) {
  const [q, setQ] = useState('');
  const [pick, setPick] = useState<string | null>(null);
  const [hold, setHold] = useState<Hold>('watching');
  const [focus, setFocus] = useState(false);
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setQ('');
      setPick(null);
      setHold('watching');
    }
  }
  const t = q.trim();
  const list = t ? universe.filter((s) => s.name.includes(t) || cho(s.name).includes(t) || s.stock_code.includes(t) || s.sector.includes(t)) : universe.filter((s) => !mine.some((m) => m.stock_code === s.stock_code)).slice(0, 8);
  const had = (c: string) => mine.find((m) => m.stock_code === c);
  const sel = list.find((s) => s.stock_code === pick && !had(s.stock_code));
  const ok = () => {
    if (!sel) return;
    onClose();
    onAdd(sel.stock_code, hold);
  };
  const holdKo = hold === 'holding' ? '보유' : '관심';
  return (
    <Sheet open={open} onClose={onClose} width={680} label="종목 추가">
      <View style={st.box}>
        <View style={st.head}>
          <View style={st.headL}>
            <Text style={st.title}>종목 추가</Text>
            <Text style={st.sub}>메모를 남길 종목을 찾아 담아 두세요.</Text>
          </View>
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="닫기" style={({ hovered }: Hover) => [st.x, hovered && { backgroundColor: '#F2F3F4' }]}>
            <Svg width={20} height={20} viewBox="0 0 20 20" fill="none">
              <Path d="M5 5L15 15M15 5L5 15" stroke="#333" strokeWidth={1.8} strokeLinecap="round" />
            </Svg>
          </Pressable>
        </View>
        <View style={[st.search, focus && st.searchOn]}>
          <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
            <Circle cx={11} cy={11} r={6.2} stroke="#000" strokeWidth={1.6} />
            <Path d="M15.6 15.6L19.2 19.2" stroke="#000" strokeWidth={1.6} strokeLinecap="round" />
          </Svg>
          <TextInput
            autoFocus
            value={q}
            onChangeText={(v) => {
              setQ(v);
              setPick(null);
            }}
            onFocus={() => setFocus(true)}
            onBlur={() => setFocus(false)}
            onSubmitEditing={ok}
            placeholder="종목명 또는 코드"
            placeholderTextColor="#9A9EA7"
            accessibilityLabel="종목 검색"
            style={st.searchIn}
          />
        </View>
        {t ? <Text style={st.count}>검색 결과 {list.length}건</Text> : null}
        <ScrollView style={st.list} contentContainerStyle={{ gap: 2 }}>
          {list.length === 0 ? <Text style={st.none}>찾는 종목이 없어요</Text> : null}
          {list.map((s) => {
            const h = had(s.stock_code);
            const on = !h && s.stock_code === pick;
            return (
              <Pressable key={s.stock_code} disabled={!!h} onPress={() => setPick(on ? null : s.stock_code)} accessibilityState={{ selected: on, disabled: !!h }} style={({ hovered }: Hover) => [st.row, on ? st.rowOn : hovered && !h ? { backgroundColor: '#F9F9F9' } : null, h && { opacity: 0.5 }]}>
                <Keep style={[st.logo, { backgroundColor: s.logo_bg }]}>
                  <Text style={[st.logoT, { fontSize: s.logo.length > 2 ? 10 : s.logo.length > 1 ? 12 : 15, color: s.logo_ink ?? '#FFFFFF' }]}>{s.logo}</Text>
                </Keep>
                <View style={st.flexMin}>
                  <View style={st.nmRow}>
                    <Text style={st.nm}>{s.name}</Text>
                    <View style={st.sector}>
                      <Text style={st.sectorT}>{s.sector}</Text>
                    </View>
                  </View>
                  <Text style={st.meta}>
                    {s.stock_code} · {s.market}
                    {h ? ` · 이미 ${h.status === 'holding' ? '보유' : '관심'}에 있어요` : ''}
                  </Text>
                </View>
                {!h ? (
                  on ? (
                    <Svg width={22} height={22} viewBox="0 0 22 22" fill="none">
                      <Circle cx={11} cy={11} r={11} fill="#111111" />
                      <Path d="M6.8 11.2L9.6 14L15.2 8.2" stroke="white" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
                    </Svg>
                  ) : (
                    <Svg width={22} height={22} viewBox="0 0 22 22" fill="none">
                      <Circle cx={11} cy={11} r={10} stroke="#C9CCD2" strokeWidth={1.6} />
                    </Svg>
                  )
                ) : null}
              </Pressable>
            );
          })}
        </ScrollView>
        <Text style={st.q}>어떻게 담을까요?</Text>
        <View style={st.seg}>
          {(['holding', 'watching'] as const).map((h) => {
            const on = hold === h;
            return (
              <Pressable key={h} onPress={() => setHold(h)} accessibilityState={{ selected: on }} style={({ hovered }: Hover) => [st.segB, on ? st.segOn : hovered && { backgroundColor: '#F9F9F9' }]}>
                <Text style={[st.segT, on && { color: '#111111', fontWeight: '500' }]}>{h === 'holding' ? '보유' : '관심'}</Text>
              </Pressable>
            );
          })}
        </View>
        <Pressable disabled={!sel} onPress={ok} style={({ hovered }: Hover) => [st.cta, { backgroundColor: sel ? (hovered ? '#2A2A2A' : '#111111') : '#C9CCD2' }]}>
          <Text style={st.ctaT}>{sel ? `${holdKo} 종목으로 추가` : '종목을 골라 주세요'}</Text>
        </Pressable>
      </View>
    </Sheet>
  );
}

const st = StyleSheet.create({
  flexMin: { flex: 1, minWidth: 0 },
  box: { height: 660, maxHeight: '100%', width: 680, maxWidth: '100%', gap: 12, borderRadius: 20, borderWidth: 1, borderColor: '#E8EAED', backgroundColor: '#FFFFFF', padding: 23, shadowColor: '#1C2940', shadowOpacity: 0.08, shadowRadius: 32, shadowOffset: { width: 0, height: 12 }, elevation: 8 },
  head: { marginBottom: 4, height: 56, flexDirection: 'row', alignItems: 'center', gap: 16 },
  headL: { flex: 1, minWidth: 0, gap: 4 },
  title: { ...fpx(22, 31), fontWeight: '700', color: '#15171A' },
  sub: { ...fpx(17, 26), color: '#747D8D' },
  x: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  search: { height: 44, flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 12, borderWidth: 1, borderColor: 'transparent', backgroundColor: '#F3F4F6', paddingHorizontal: 12 },
  searchOn: { borderWidth: 1.5, borderColor: '#111111', backgroundColor: '#FFFFFF', paddingHorizontal: 10.5 },
  searchIn: { flex: 1, minWidth: 0, ...fpx(14, 21), color: '#16171A', paddingVertical: 0, outlineWidth: 0 },
  count: { ...fpx(13, 20), color: '#8A8F98' },
  list: { flex: 1, minHeight: 0 },
  none: { paddingVertical: 24, textAlign: 'center', ...fpx(13, 20), color: '#8A8F98' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 14, paddingVertical: 9, paddingLeft: 10, paddingRight: 12 },
  rowOn: { backgroundColor: '#F7F7F7', borderWidth: 1.5, borderColor: '#111111', paddingVertical: 7.5, paddingLeft: 8.5, paddingRight: 10.5 },
  logo: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  logoT: { lineHeight: 23, fontWeight: '700' },
  nmRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  nm: { ...fpx(15, 23), fontWeight: '700', color: '#16171A' },
  sector: { borderRadius: 6, backgroundColor: '#F2F3F4', paddingHorizontal: 6, paddingVertical: 2 },
  sectorT: { ...fpx(13, 20), fontWeight: '500', color: '#575B63' },
  meta: { ...fpx(13, 20), color: '#8A8F98' },
  q: { ...fpx(13, 20), color: '#575B63' },
  seg: { flexDirection: 'row', gap: 8 },
  segB: { flex: 1, height: 48, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E5E7EB' },
  segOn: { backgroundColor: '#F7F7F7', borderColor: '#111111' },
  segT: { ...fpx(15, 23), color: '#575B63' },
  cta: { height: 46, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  ctaT: { ...fpx(15, 23), fontWeight: '500', color: '#FFFFFF' },
});
