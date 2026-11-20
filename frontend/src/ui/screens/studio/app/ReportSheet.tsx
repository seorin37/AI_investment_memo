import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { PressScale } from '@/ui/motion/PressScale';
import { Sheet } from '@/ui/shared/Sheet';
import type { ReportStock } from '../Studio.mock';

/**
 * 앱 AI 주간보고서 만들기 시트 = 원본 studio.html sheetHTML(report) (05)
 * 보고 기간 칸 · 빠른 고르기 · 종목 줄(이번 주 공시·뉴스 N건) · 국내 증시 흐름(고를 수 있음 · 처음엔 꺼짐) · 안내 · [보고서 만들기]
 * 크레딧 차감 없음 (mock)
 */
const C = { a: '#8569E3', ink: '#16171A', ink2: '#575B63', ink3: '#9A9EA7' };

export function AppReportSheet({ open, stocks, period, onClose, onMake }: { open: boolean; stocks: ReportStock[]; period: string; onClose: () => void; onMake: (p: { codes: string[]; market: boolean }) => void }) {
  const [pick, setPick] = useState<string[]>(stocks.map((s) => s.stock_code));
  const [mkt, setMkt] = useState(false);
  const want = (q: 'all' | 'own' | 'watch') => stocks.filter((s) => q === 'all' || (q === 'own' ? s.own === '보유' : s.own === '관심')).map((s) => s.stock_code);
  const same = (a: string[]) => a.length === pick.length && a.every((c) => pick.includes(c));
  const n = pick.length;
  return (
    <Sheet open={open} onClose={onClose} label="AI 주간보고서 만들기">
      <View style={{ paddingHorizontal: 18 }}>
        <Text style={st.h}>AI 주간보고서 만들기</Text>
        {/* 412 에서 한 줄 (원본 캡처 데모08 처럼 — 줄을 넘기지 않음) */}
        <Text numberOfLines={1} style={st.d}>고른 종목마다 시세·공시·재무·내 메모를 묶어 회사 보고서 형식으로 정리해요</Text>
        <View style={st.rper}><Text style={st.rperT}><Text style={st.rperB}>보고 기간  </Text>{period}</Text></View>
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
          const k = s.counts.공시 + s.counts.뉴스;
          return <Row key={s.stock_code} on={pick.includes(s.stock_code)} dim={!k} name={s.name} sub={k ? `이번 주 공시·뉴스 ${k}건` : '이번 주 공시·뉴스 없음'} tag={s.own} onPress={() => setPick((a) => (a.includes(s.stock_code) ? a.filter((x) => x !== s.stock_code) : [...a, s.stock_code]))} />;
        })}
        <Row on={mkt} name="국내 증시 흐름" sub="코스피·코스닥·원/달러" tag="선택" gray onPress={() => setMkt(!mkt)} />
        <Text style={st.note}>공시·뉴스가 없는 종목도 시세·재무·메모 추적 현황은 들어가요</Text>
        <PressScale disabled={!n} onPress={() => onMake({ codes: stocks.map((s) => s.stock_code).filter((c) => pick.includes(c)), market: mkt })} accessibilityRole="button" style={[st.cta, !n && { backgroundColor: '#C9CDD4' }]}>
          <Text style={st.ctaT}>{n ? '보고서 만들기' : '종목을 1개 이상 골라 주세요'}</Text>
        </PressScale>
      </View>
    </Sheet>
  );
}

function Row({ on, dim, name, sub, tag, gray, onPress }: { on: boolean; dim?: boolean; name: string; sub: string; tag: string; gray?: boolean; onPress: () => void }) {
  const w = gray || tag === '관심';
  return (
    <Pressable onPress={onPress} accessibilityRole="checkbox" accessibilityState={{ checked: on }} style={st.sr}>
      <View style={[st.cb, on && { backgroundColor: C.a, borderColor: C.a }]}>
        {on ? <Svg width={14} height={14} viewBox="0 0 14 14" fill="none"><Path d="M3 7.3l2.6 2.6L11 4.4" stroke="#fff" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" /></Svg> : null}
      </View>
      <Text style={[st.srT, dim && { color: '#B0B4BB' }]}>{name}</Text>
      <Text style={[st.nn, dim && { color: '#B0B4BB' }]}>{sub}</Text>
      <View style={[st.op, w && { backgroundColor: '#F2F2F5' }]}><Text style={[st.opT, w && { color: C.ink2 }]}>{tag}</Text></View>
    </Pressable>
  );
}

const st = StyleSheet.create({
  h: { fontSize: 19, lineHeight: 26, fontWeight: '700', color: C.ink, marginBottom: 4 },
  d: { fontSize: 12.5, lineHeight: 18, color: C.ink3, marginBottom: 12 },
  rper: { backgroundColor: '#F6F7F9', borderRadius: 12, paddingVertical: 9, paddingHorizontal: 12, marginBottom: 10 },
  rperT: { fontSize: 12.5, lineHeight: 18, color: C.ink2 },
  rperB: { fontWeight: '700', color: C.ink },
  qc: { flexDirection: 'row', gap: 6, marginBottom: 6 },
  q: { height: 32, paddingHorizontal: 12, borderRadius: 16, borderWidth: 1, borderColor: '#DADDE2', justifyContent: 'center' },
  qOn: { backgroundColor: C.ink, borderColor: C.ink },
  qT: { fontSize: 12.5, lineHeight: 17, fontWeight: '600', color: C.ink },
  sr: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: '#F0F1F4' },
  cb: { width: 24, height: 24, borderRadius: 7, borderWidth: 2, borderColor: '#C9CDD4', alignItems: 'center', justifyContent: 'center' },
  srT: { fontSize: 15, lineHeight: 21, fontWeight: '600', color: C.ink },
  nn: { marginLeft: 'auto', fontSize: 12.5, lineHeight: 18, fontWeight: '500', color: C.ink2 },
  op: { borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2, backgroundColor: '#EEE9FB' },
  opT: { fontSize: 11, lineHeight: 15, fontWeight: '700', color: '#5B3BD1' },
  note: { fontSize: 11.5, lineHeight: 16, color: C.ink3, marginTop: 8, marginBottom: 10 },
  cta: { height: 54, borderRadius: 15, backgroundColor: C.ink, alignItems: 'center', justifyContent: 'center', marginTop: 10 },
  ctaT: { fontSize: 16, lineHeight: 22, fontWeight: '800', color: '#FFFFFF' },
});
