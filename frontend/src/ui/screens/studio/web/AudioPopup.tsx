import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { FeatIcon } from '@/ui/layout/web/StudioColumnFrame';
import { Sheet } from '@/ui/shared/Sheet';
import { CloseX } from '../../my/web/parts';
import type { AudioStock } from '../Studio.mock';
import { GBtn } from './Credit';

type Hover = { hovered?: boolean; pressed?: boolean };

/**
 * 웹 AI 오디오 만들기 창 = 원본 studio.tsx AudioPopup (468 · 라운드 28)
 * PopHead · 빠른 고르기(40 알약) · 종목 상자(줄 58 · 체크 24/8 · 새 업데이트 N건 · 보유/관심) · 증시 요약(+1) · 업데이트 기간 · (소식 없음 안내) · [취소][오디오 만들기]
 */
export function WebAudioPopup({ open, stocks, periods, lastClose, onClose, onMake, preset }: { open: boolean; stocks: AudioStock[]; periods: readonly string[]; lastClose: string; onClose: () => void; onMake: (p: { codes: string[]; period: string; market: boolean }) => void; /** 넛지에서 열 때 미리 고를 종목 (목록에 있는 것만 · 없거나 0개면 전체) */ preset?: string[] }) {
  const all = stocks.map((s) => s.stock_code);
  const [sel, setSel] = useState<string[]>(all);
  const [sum, setSum] = useState(true);
  const [per, setPer] = useState(0);
  const [prev, setPrev] = useState(open);
  /* 실제 모드는 종목 목록이 창을 연 뒤에 도착한다 (GET /studio/audio/options) → 도착하면 다시 고른다 */
  const key = all.join(',');
  const [prevKey, setPrevKey] = useState(key);
  const pickAll = () => {
    const pick = preset?.filter((c) => all.includes(c)) ?? [];
    setSel(pick.length ? pick : all);
  };
  if (open !== prev) {
    setPrev(open);
    if (open) {
      pickAll();
      setSum(true);
      setPer(0);
    }
  }
  if (key !== prevKey) {
    setPrevKey(key);
    pickAll();
  }
  const n = (s: AudioStock) => s.news[per] ?? 0;
  const total = stocks.filter((s) => sel.includes(s.stock_code)).reduce((a, s) => a + n(s), 0);
  const empty = total === 0 && !sum;
  const want = (q: 'all' | 'own' | 'watch') => stocks.filter((s) => q === 'all' || (q === 'own' ? s.hold === '보유' : s.hold === '관심')).map((s) => s.stock_code);
  const eq = (a: string[]) => a.length > 0 && a.length === sel.length && a.every((x) => sel.includes(x));
  return (
    <Sheet open={open} onClose={onClose} width={468} scrim="rgba(21,23,26,0.4)" label="AI 오디오 만들기">
      <View style={st.pop}>
        <View style={st.head}>
          <View style={st.ic}><FeatIcon f="audio" size={22} /></View>
          <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
            <Text style={st.h}>AI 오디오 만들기</Text>
            <Text style={st.hs}>들을 종목과 기간을 골라 주세요</Text>
          </View>
          <CloseX onPress={onClose} />
        </View>
        <View style={st.body}>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {([['all', '전체 종목'], ['own', '보유 종목 전체'], ['watch', '관심 종목 전체']] as const).map(([q, l]) => {
              const on = eq(want(q));
              return (
                <Pressable key={q} onPress={() => setSel(want(q))} accessibilityRole="button" accessibilityState={{ selected: on }} style={({ hovered }: Hover) => [st.pre, on ? st.preOn : hovered && { backgroundColor: '#F9F9F9' }]}>
                  <Text style={[st.preT, on && { color: '#FFFFFF' }]}>{l}</Text>
                </Pressable>
              );
            })}
          </View>
          <View style={st.box}>
            {stocks.map((s) => {
              const on = sel.includes(s.stock_code);
              return (
                <Pressable key={s.stock_code} onPress={() => setSel((a) => (on ? a.filter((x) => x !== s.stock_code) : [...a, s.stock_code]))} accessibilityRole="checkbox" accessibilityState={{ checked: on }} style={({ hovered }: Hover) => [st.row, hovered && { backgroundColor: '#F9F9F9' }]}>
                  <Check on={on} />
                  <Text style={st.name} numberOfLines={1}>{s.name}</Text>
                  <Text style={st.cnt}>{n(s) ? `새 업데이트 ${n(s)}건` : '새 업데이트 없음'}</Text>
                  <View style={st.chip}><Text style={st.chipT}>{s.hold}</Text></View>
                </Pressable>
              );
            })}
            <View style={st.hr} />
            <Pressable onPress={() => setSum(!sum)} accessibilityRole="checkbox" accessibilityState={{ checked: sum }} style={({ hovered }: Hover) => [st.row, { height: undefined, paddingVertical: 10 }, hovered && { backgroundColor: '#F9F9F9' }]}>
              <Check on={sum} />
              <View style={{ flex: 1, minWidth: 0, gap: 1 }}>
                <Text style={st.name}>직전 거래일 증시 요약</Text>
                <Text style={st.cnt}>{lastClose} 코스피·코스닥·원/달러</Text>
              </View>
              <View style={st.chip}><Text style={st.chipT}>+1</Text></View>
            </Pressable>
          </View>
          <Text style={st.lbl}>업데이트 기간</Text>
          <View style={st.seg}>
            {periods.map((l, i) => (
              <Pressable key={l} onPress={() => setPer(i)} accessibilityRole="tab" accessibilityState={{ selected: per === i }} style={[st.segB, per === i && st.segOn]}>
                <Text style={[st.segT, per === i && { color: '#15171A' }]}>{l}</Text>
              </Pressable>
            ))}
          </View>
          {empty ? (
            <View style={st.warn}>
              <Text style={st.warnB}>새로 들려줄 소식이 없어요</Text>
              <Text keepAll style={st.warnS}>고른 종목에 {per === 0 ? '전날' : '최근 3일 동안'} 생긴 업데이트가 없어요. 기간을 늘리거나 증시 요약을 넣으면 만들 수 있어요.</Text>
            </View>
          ) : null}
        </View>
        <View style={st.btns}>
          {empty ? <GBtn h={48} onPress={() => setPer(periods.length - 1)}>{`${periods[periods.length - 1]}로 늘리기`}</GBtn> : <GBtn h={48} onPress={onClose}>취소</GBtn>}
          <GBtn h={48} flex dark disabled={empty || (!sel.length && !sum)} onPress={() => onMake({ codes: sel, period: periods[per], market: sum })}>{empty ? '만들 소식이 없어요' : '오디오 만들기'}</GBtn>
        </View>
      </View>
    </Sheet>
  );
}

export function Check({ on }: { on: boolean }) {
  return (
    <View style={[st.cb, on ? { backgroundColor: '#15171A' } : { borderWidth: 1, borderColor: '#D9D9D9', backgroundColor: '#FFFFFF' }]}>
      {on ? <Svg width={14} height={14} viewBox="0 0 14 14" fill="none"><Path d="M2.91667 7.00065L5.54167 9.62565L11.0833 4.08398" stroke="white" strokeWidth={1.86667} strokeLinecap="round" strokeLinejoin="round" /></Svg> : null}
    </View>
  );
}

const st = StyleSheet.create({
  pop: { width: 468, maxWidth: '100%', overflow: 'hidden', borderRadius: 28, backgroundColor: '#FFFFFF', shadowColor: '#14171A', shadowOpacity: 0.22, shadowRadius: 80, shadowOffset: { width: 0, height: 30 } },
  head: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 22, paddingTop: 22, paddingBottom: 12 },
  ic: { width: 44, height: 44, borderRadius: 13, backgroundColor: '#F5F6F8', alignItems: 'center', justifyContent: 'center' },
  h: { fontSize: 22, lineHeight: 29, fontWeight: '700', letterSpacing: -0.4, color: '#15171A' },
  hs: { fontSize: 14, lineHeight: 18, letterSpacing: -0.2, color: '#8E8A97' },
  body: { gap: 14, paddingHorizontal: 22, paddingTop: 4, paddingBottom: 16 },
  pre: { height: 40, borderRadius: 999, paddingHorizontal: 16, justifyContent: 'center', borderWidth: 1, borderColor: '#D9D9D9', backgroundColor: '#FFFFFF' },
  preOn: { backgroundColor: '#15171A', borderColor: '#15171A' },
  preT: { fontSize: 15, lineHeight: 18, fontWeight: '700', letterSpacing: -0.2, color: '#404752' },
  box: { gap: 2, borderRadius: 18, borderWidth: 1, borderColor: '#E5E3E8', padding: 6 },
  row: { height: 58, flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 14, paddingHorizontal: 12 },
  name: { flex: 1, minWidth: 0, fontSize: 17, lineHeight: 22, fontWeight: '700', letterSpacing: -0.2, color: '#15171A' },
  cnt: { fontSize: 14, lineHeight: 18, letterSpacing: -0.2, color: '#8E8A97' },
  chip: { height: 24, borderRadius: 999, paddingHorizontal: 9, justifyContent: 'center', backgroundColor: '#F5F6F8' },
  chipT: { fontSize: 13, lineHeight: 16, fontWeight: '700', color: '#404752' },
  hr: { height: 1, backgroundColor: '#E8ECF3' },
  cb: { width: 24, height: 24, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  lbl: { fontSize: 14, lineHeight: 21, fontWeight: '700', letterSpacing: -0.2, color: '#8E8A97' },
  seg: { flexDirection: 'row', gap: 4, borderRadius: 12, backgroundColor: '#F5F6F8', padding: 4 },
  segB: { flex: 1, minWidth: 0, height: 40, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  segOn: { backgroundColor: '#FFFFFF', shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 3, shadowOffset: { width: 0, height: 1 } },
  segT: { fontSize: 15, lineHeight: 18, fontWeight: '700', letterSpacing: -0.2, color: '#8E8A97' },
  warn: { gap: 3, borderRadius: 18, backgroundColor: '#FFF4E5', paddingHorizontal: 16, paddingVertical: 14 },
  warnB: { fontSize: 15, lineHeight: 20, fontWeight: '700', color: '#7A4A00' },
  warnS: { fontSize: 14, lineHeight: 21, color: '#7A4A00' },
  btns: { flexDirection: 'row', gap: 8, paddingHorizontal: 22, paddingTop: 12, paddingBottom: 20 },
});
