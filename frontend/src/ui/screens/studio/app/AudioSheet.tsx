import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { nf } from '@/ui/shared/app/nf';
import { Text } from '@/components/ui/AppText';
import { PressScale } from '@/ui/motion/PressScale';
import { SlidingPill } from '@/ui/motion/SlidingPill';
import { Sheet } from '@/ui/shared/Sheet';
import { Toggle } from '@/ui/shared/Toggle';
import type { AudioStock } from '../Studio.mock';

/**
 * 앱 AI 오디오 만들기 시트 = 원본 studio.html sheetHTML(audio) (04)
 * 빠른 고르기 칩(32) · 종목 줄(체크 24/7 · 새 소식 N건 · 보유/관심 태그) · 안내 · 직전 거래일 증시 요약 스위치 · 업데이트 기간 세그 · [오디오 만들기]
 * 원본 사용량 계산 칸(.calc)은 원본에서도 숨김이라 넣지 않음. 크레딧 차감 없음 (mock)
 */
const C = { a: '#8569E3', ink: '#16171A', ink2: '#575B63', ink3: '#9A9EA7' };

export function AppAudioSheet({ open, stocks, periods, lastClose, onClose, onMake }: { open: boolean; stocks: AudioStock[]; periods: readonly string[]; /** '11.06(금)' 직전 거래일 */ lastClose: string; onClose: () => void; onMake: (p: { codes: string[]; period: string; market: boolean }) => void }) {
  const [pick, setPick] = useState<string[]>(stocks.map((s) => s.stock_code));
  const [mkt, setMkt] = useState(true);
  const [per, setPer] = useState(0);
  const [lay, setLay] = useState<{ x: number; width: number }[]>([]);
  /* 실제 모드는 종목 목록이 시트를 연 뒤에 도착한다 (GET /studio/audio/options) → 도착하거나 다시 열면 전체를 고른다 */
  const key = stocks.map((s) => s.stock_code).join(',');
  const [prev, setPrev] = useState({ key, open });
  if (prev.key !== key || prev.open !== open) {
    setPrev({ key, open });
    if (open) {
      setPick(stocks.map((s) => s.stock_code));
      setMkt(true);
      setPer(0);
    }
  }
  const want = (q: 'all' | 'own' | 'watch') => stocks.filter((s) => q === 'all' || (q === 'own' ? s.hold === '보유' : s.hold === '관심')).map((s) => s.stock_code);
  const same = (a: string[]) => a.length === pick.length && a.every((c) => pick.includes(c));
  const n = pick.length;
  /* 고른 종목에 이 기간 소식이 없고 증시 요약도 안 넣음 → 만들 것이 없음 (웹과 같음) */
  const empty = !mkt && stocks.filter((s) => pick.includes(s.stock_code)).every((s) => !s.news[per]);
  const can = !empty && (n > 0 || mkt);
  return (
    <Sheet open={open} onClose={onClose} label="AI 오디오 만들기">
      <View style={{ paddingHorizontal: 18 }}>
        <Text style={st.h}>AI 오디오 만들기</Text>
        <Text numberOfLines={1} style={st.d}>들을 종목과 기간을 골라 주세요</Text>
        <View style={st.qc}>
          {([['all', '전체 종목'], ['own', '보유 종목 전체'], ['watch', '관심 종목 전체']] as const).map(([q, l]) => {
            const on = same(want(q));
            return (
              <PressScale key={q} scaleTo={0.94} onPress={() => setPick(want(q))} accessibilityRole="button" accessibilityState={{ selected: on }} style={[st.q, on && st.qOn]}>
                <Text style={[st.qT, on && { color: '#FFFFFF' }]}>{l}</Text>
              </PressScale>
            );
          })}
        </View>
        {stocks.map((s) => {
          const on = pick.includes(s.stock_code);
          const news = s.news[per] ?? 0;
          const none = !news;
          return (
            <Pressable key={s.stock_code} onPress={() => setPick((a) => (on ? a.filter((x) => x !== s.stock_code) : [...a, s.stock_code]))} accessibilityRole="checkbox" accessibilityState={{ checked: on }} style={st.sr}>
              <View style={[st.cb, on && { backgroundColor: C.a, borderColor: C.a }]}>
                {on ? <Svg width={14} height={14} viewBox="0 0 14 14" fill="none"><Path d="M3 7.3l2.6 2.6L11 4.4" stroke="#fff" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" /></Svg> : null}
              </View>
              <Text style={[st.srT, none && { color: '#B0B4BB' }]}>{s.name}</Text>
              <Text style={[st.nn, none && { color: '#B0B4BB' }]}>{news ? `새 소식 ${news}건` : '새 소식 없음'}</Text>
              <View style={[st.op, s.hold === '관심' && { backgroundColor: '#F2F2F5' }]}><Text style={[st.opT, s.hold === '관심' && { color: C.ink2 }]}>{s.hold}</Text></View>
            </Pressable>
          );
        })}
        <Text style={st.note}>새 소식이 없는 종목은 넣어도 &quot;새 소식 없음&quot;으로만 짧게 다뤄요</Text>
        <View style={st.swr}>
          <View style={{ flex: 1 }}><Text style={st.swB}>직전 거래일 증시 요약</Text><Text style={st.swS}>{lastClose} 코스피·코스닥·원/달러</Text></View>
          <View style={[st.op, { backgroundColor: '#F2F2F5', marginRight: 8 }]}><Text style={[st.opT, { color: C.ink2 }]}>+1</Text></View>
          <Toggle variant="app" on={mkt} onChange={setMkt} label="직전 거래일 증시 요약" />
        </View>
        <Text style={st.lbl}>업데이트 기간</Text>
        <View style={st.seg}>
          <SlidingPill target={lay[per] ?? null} style={st.pill} />
          {periods.map((l, i) => (
            <Pressable key={l} onPress={() => setPer(i)} onLayout={(e) => { const { x, width } = e.nativeEvent.layout; setLay((a) => { const b = [...a]; b[i] = { x, width }; return b; }); }} accessibilityRole="tab" accessibilityState={{ selected: per === i }} style={st.segB}>
              <Text style={[st.segT, per === i && { color: C.ink, fontWeight: '800' }]}>{l}</Text>
            </Pressable>
          ))}
        </View>
        {empty && n ? (
          <View style={st.warn}>
            <Text style={st.warnB}>새로 들려줄 소식이 없어요</Text>
            <Text keepAll style={st.warnS}>{`고른 종목에 ${per === 0 ? '전날' : `${periods[per]} 동안`} 생긴 업데이트가 없어요. 기간을 늘리거나 증시 요약을 넣으면 만들 수 있어요.`}</Text>
            {per < periods.length - 1 ? <Pressable onPress={() => setPer(periods.length - 1)} accessibilityRole="button"><Text style={st.warnL}>{periods[periods.length - 1]}로 늘리기</Text></Pressable> : null}
          </View>
        ) : null}
        <PressScale disabled={!can} onPress={() => onMake({ codes: pick, period: periods[per], market: mkt })} accessibilityRole="button" style={[st.cta, !can && { backgroundColor: '#C9CDD4' }]}>
          <Text style={st.ctaT}>{can ? '오디오 만들기' : n ? '만들 소식이 없어요' : '종목을 1개 이상 골라 주세요'}</Text>
        </PressScale>
      </View>
    </Sheet>
  );
}

const st = StyleSheet.create({
  warn: { borderRadius: 14, backgroundColor: '#FFF6E5', borderWidth: 1, borderColor: '#F6E2B8', paddingVertical: 12, paddingHorizontal: 14, marginTop: 12 },
  warnB: { ...nf(14), fontWeight: '800', color: '#5C3800' },
  warnS: { fontSize: 12.5, lineHeight: 19, color: '#7A4B00', marginTop: 3 },
  warnL: { ...nf(12.5), fontWeight: '800', color: '#8A5A00', marginTop: 8 },
  h: { ...nf(19), fontWeight: '700', color: C.ink, marginBottom: 4 },
  d: { ...nf(12.5), color: C.ink3, marginBottom: 12 },
  qc: { flexDirection: 'row', gap: 6, marginBottom: 6 },
  q: { height: 32, paddingHorizontal: 12, borderRadius: 16, borderWidth: 1, borderColor: '#DADDE2', justifyContent: 'center' },
  qOn: { backgroundColor: C.ink, borderColor: C.ink },
  qT: { ...nf(12.5), fontWeight: '600', color: C.ink },
  sr: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: '#F0F1F4' },
  cb: { width: 24, height: 24, borderRadius: 7, borderWidth: 2, borderColor: '#C9CDD4', alignItems: 'center', justifyContent: 'center' },
  srT: { ...nf(15), fontWeight: '600', color: C.ink },
  nn: { marginLeft: 'auto', ...nf(12.5), fontWeight: '500', color: C.ink2 },
  op: { borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2, backgroundColor: '#EEE9FB' },
  opT: { ...nf(11), fontWeight: '700', color: '#5B3BD1' },
  note: { ...nf(11.5), color: C.ink3, marginTop: 8, marginBottom: 10 },
  swr: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingTop: 4, paddingBottom: 12 },
  swB: { ...nf(15), fontWeight: '700', color: C.ink },
  swS: { ...nf(12), color: C.ink3 },
  lbl: { ...nf(13), fontWeight: '700', color: C.ink2, marginTop: 2, marginBottom: 8 },
  seg: { flexDirection: 'row', backgroundColor: '#F2F2F5', borderRadius: 13, padding: 4 },
  pill: { position: 'absolute', top: 4, bottom: 4, borderRadius: 10, backgroundColor: '#FFFFFF', shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  segB: { flex: 1, height: 38, alignItems: 'center', justifyContent: 'center' },
  segT: { ...nf(14), fontWeight: '600', color: C.ink3 },
  cta: { height: 54, borderRadius: 15, backgroundColor: C.ink, alignItems: 'center', justifyContent: 'center', marginTop: 20 },
  ctaT: { ...nf(16), fontWeight: '800', color: '#FFFFFF' },
});
