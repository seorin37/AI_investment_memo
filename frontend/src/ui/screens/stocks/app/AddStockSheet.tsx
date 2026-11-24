import React, { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { Text, TextInput } from '@/components/ui/AppText';
import { Sheet } from '@/ui/shared/Sheet';
import { StockLogo } from '@/ui/shared/StockLogo';
import { appColor, ft } from '@/ui/theme';
import type { Hold, MyStock, StockCandidate } from '../MyStocks.types';
import { HoldIcon } from './stockGlyphs';

const CHK = (
  <Svg width={13} height={13} viewBox="0 0 14 14" fill="none">
    <Path d="M3 7.3l2.6 2.6L11 4.4" stroke="#FFFFFF" strokeWidth={2.3} strokeLinecap="round" strokeLinejoin="round" />
  </Svg>
);

/**
 * 앱 종목 추가 시트 (원본 stock.html 07 시트 · 11.11 사용자 선택)
 * 검색칸(46 · 포커스면 보라 테두리) · 많이 찾는 종목 · 검색 결과 · 이미 있는 종목은 흐리게 · 어떻게 담을까요? 보유/관심 · [관심 종목으로 추가]
 */
export function AddStockSheet({ open, mine, universe, popular, onClose, onAdd, remote, onQueryChange }: { open: boolean; mine: MyStock[]; universe: StockCandidate[]; popular: string[]; onClose: () => void; onAdd: (code: string, hold: Hold) => void; remote?: boolean; onQueryChange?: (q: string) => void }) {
  const [q, setQ] = useState('');
  const [pick, setPick] = useState<string | null>(null);
  const [hold, setHold] = useState<Hold>('watching');
  const [focus, setFocus] = useState(false);
  const t = q.trim();
  /* 실제 모드: 검색어를 호스트로 (GET /stocks/search) — 렌더 중이 아니라 effect 에서 */
  useEffect(() => {
    onQueryChange?.(t);
  }, [t, onQueryChange]);
  const list = t && remote ? universe.slice(0, 6) : t ? universe.filter((s) => s.name.toLowerCase().includes(t.toLowerCase()) || s.stock_code.includes(t)).slice(0, 6) : popular.map((c) => universe.find((s) => s.stock_code === c)).filter((s): s is StockCandidate => !!s);
  const close = () => {
    setQ('');
    setPick(null);
    setHold('watching');
    onClose();
  };
  const holdKo = hold === 'holding' ? '보유' : '관심';
  return (
    <Sheet open={open} onClose={close} label="종목 추가">
      <View style={st.shh}>
        <Text style={st.shhT}>종목 추가</Text>
        <Pressable onPress={close} accessibilityRole="button" accessibilityLabel="닫기" style={st.x}>
          <Svg width={13} height={13} viewBox="0 0 24 24" stroke="#16171A" strokeWidth={2.8} strokeLinecap="round">
            <Path d="M6 6l12 12M18 6 6 18" />
          </Svg>
        </Pressable>
      </View>
      <View style={[st.ssb, focus && st.ssbF]}>
        <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="#575B63" strokeWidth={2.2} strokeLinecap="round">
          <Circle cx={11} cy={11} r={7} />
          <Path d="M20 20l-4-4" />
        </Svg>
        <TextInput
          value={q}
          onChangeText={(v) => {
            setQ(v);
            if (pick && !universe.some((s) => s.stock_code === pick && (s.name.includes(v.trim()) || s.stock_code.includes(v.trim())))) setPick(null);
          }}
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          placeholder="종목명 또는 코드"
          placeholderTextColor={appColor.ink3}
          style={st.ssbIn}
        />
      </View>
      <ScrollView style={st.slist} keyboardShouldPersistTaps="handled">
        {!t ? <Text style={[st.slab, { paddingLeft: 2 }]}>많이 찾는 종목</Text> : list.length ? <Text style={st.slab}>검색 결과 {list.length}건</Text> : null}
        {t && !list.length ? (
          <View style={st.snores}>
            <Text style={st.snoresB}>‘{t}’ 종목을 찾지 못했어요</Text>
            <Text style={st.snoresT}>코스피 종목명이나 6자리 코드로 다시 찾아보세요</Text>
          </View>
        ) : null}
        {list.map((s) => {
          const had = mine.find((m) => m.stock_code === s.stock_code);
          const on = pick === s.stock_code;
          const i = t ? s.name.toLowerCase().indexOf(t.toLowerCase()) : -1;
          return (
            <Pressable key={s.stock_code} disabled={!!had} onPress={() => setPick(on ? null : s.stock_code)} accessibilityRole="radio" accessibilityState={{ checked: on, disabled: !!had }} style={({ pressed }) => [st.srw, on && st.srwOn, had && { opacity: 0.45 }, pressed && { transform: [{ scale: 0.98 }] }]}>
              <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={36} variant="app" />
              <View style={st.flexMin}>
                <View style={st.nmRow}>
                  <Text style={st.nm} numberOfLines={1}>
                    {i >= 0 ? (
                      <>
                        {s.name.slice(0, i)}
                        <Text style={st.mark}>{s.name.slice(i, i + t.length)}</Text>
                        {s.name.slice(i + t.length)}
                      </>
                    ) : (
                      s.name
                    )}
                  </Text>
                  {s.ai_ready ? (
                    <View style={st.tg}>
                      <Text style={st.tgT}>✦ AI 연결</Text>
                    </View>
                  ) : null}
                </View>
                <Text style={st.sm}>
                  {s.stock_code} · {s.market}
                  {had ? ` · 이미 ${had.status === 'holding' ? '보유' : '관심'}에 있어요` : ''}
                </Text>
              </View>
              {had ? null : <View style={[st.cck, on && st.cckOn]}>{on ? CHK : null}</View>}
            </Pressable>
          );
        })}
      </ScrollView>
      <View style={st.sfoot}>
        <Text style={st.q}>어떻게 담을까요?</Text>
        <View style={st.seg}>
          {(['holding', 'watching'] as const).map((h) => {
            const on = hold === h;
            return (
              <Pressable key={h} onPress={() => setHold(h)} accessibilityRole="radio" accessibilityState={{ checked: on }} style={[st.segB, on && st.segOn]}>
                <HoldIcon h={h} />
                <Text style={[st.segT, on && st.segTOn]}>{h === 'holding' ? '보유' : '관심'}</Text>
              </Pressable>
            );
          })}
        </View>
        <Pressable
          disabled={!pick}
          onPress={() => {
            if (!pick) return;
            const c = pick;
            close();
            onAdd(c, hold);
          }}
          accessibilityRole="button"
          style={({ pressed }) => [st.cta, !pick && st.ctaDis, pressed && { transform: [{ scale: 0.97 }] }]}
        >
          <Text style={st.ctaT}>{pick ? `${holdKo} 종목으로 추가` : '종목을 골라 주세요'}</Text>
        </Pressable>
      </View>
    </Sheet>
  );
}

const st = StyleSheet.create({
  flexMin: { flex: 1, minWidth: 0 },
  shh: { flexDirection: 'row', alignItems: 'center', paddingTop: 2, paddingHorizontal: 20, paddingBottom: 12 },
  shhT: { ...ft(17), fontWeight: '800', color: appColor.ink },
  x: { marginLeft: 'auto', width: 30, height: 30, borderRadius: 15, backgroundColor: '#F1F2F4', alignItems: 'center', justifyContent: 'center' },
  ssb: { marginHorizontal: 16, marginBottom: 4, minHeight: 46, borderRadius: 12, backgroundColor: '#F3F4F6', flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, borderWidth: 1.5, borderColor: 'transparent' },
  ssbF: { borderColor: appColor.accent, backgroundColor: '#FFFFFF' },
  ssbIn: { flex: 1, minWidth: 0, ...ft(15.5), color: appColor.ink, paddingVertical: 0 },
  slist: { maxHeight: 236, paddingHorizontal: 20 },
  slab: { ...ft(12), fontWeight: '600', color: appColor.ink3, paddingTop: 10, paddingBottom: 2 },
  snores: { paddingVertical: 22, alignItems: 'center' },
  snoresB: { ...ft(15), fontWeight: '700', color: appColor.ink, textAlign: 'center' },
  snoresT: { ...ft(13.5, 1.6), color: appColor.ink2, textAlign: 'center' },
  srw: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, paddingHorizontal: 12, borderRadius: 14, borderWidth: 1.5, borderColor: 'transparent', marginBottom: 6 },
  srwOn: { backgroundColor: '#F4F0FF', borderColor: appColor.accent },
  nmRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  nm: { flexShrink: 1, ...ft(15), fontWeight: '700', color: appColor.ink },
  mark: { color: appColor.tabPurple, fontWeight: '800' },
  tg: { borderRadius: 5, backgroundColor: '#EEE9FB', paddingHorizontal: 5, paddingVertical: 1 },
  tgT: { ...ft(10.5), fontWeight: '700', color: '#5B3BD1' },
  sm: { ...ft(12), color: appColor.ink3, marginTop: 1 },
  cck: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: '#D3D6DC', alignItems: 'center', justifyContent: 'center' },
  cckOn: { backgroundColor: appColor.accent, borderColor: appColor.accent },
  sfoot: { paddingHorizontal: 16 },
  q: { ...ft(13), fontWeight: '600', color: appColor.ink2, marginTop: 14, marginBottom: 8, marginHorizontal: 4 },
  seg: { flexDirection: 'row', gap: 8 },
  segB: { flex: 1, minHeight: 46, borderRadius: 12, borderWidth: 1, borderColor: '#DADDE2', backgroundColor: '#FFFFFF', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  segOn: { borderColor: appColor.accent, borderWidth: 1.5, backgroundColor: '#F7F4FF' },
  segT: { ...ft(15), color: appColor.ink },
  segTOn: { color: appColor.tabPurple, fontWeight: '700' },
  cta: { marginTop: 12, minHeight: 52, borderRadius: 14, backgroundColor: appColor.accent, alignItems: 'center', justifyContent: 'center' },
  ctaDis: { backgroundColor: '#C9CBD1' },
  ctaT: { ...ft(15.5), fontWeight: '700', color: '#FFFFFF' },
});
