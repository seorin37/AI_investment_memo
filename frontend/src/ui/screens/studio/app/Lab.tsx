import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { BottomBar } from '@/ui/shared/app/BottomBar';
import { MiniSpace } from '@/ui/screens/studio/app/MiniBar';
import { nf } from '@/ui/shared/app/nf';
import { Text } from '@/components/ui/AppText';
import { PressScale } from '@/ui/motion/PressScale';
import { SlidingPill } from '@/ui/motion/SlidingPill';
import { Sheet } from '@/ui/shared/Sheet';
import { Head } from '../../my/app/parts';
import type { LabDir, mockLabStocks, mockLabVars } from '../Studio.mock';
import { dirColor } from '../labParts';
import { Keep } from '@/ui/shared/Dark';

/**
 * 앱 투자 실험실 = 원본 studio.html #pgLab (17)
 * 설명 · 범위 안내 · 실험할 종목 줄(→ 시트) · 조건 카드 4(지금 값 · 상승/유지/하락 세그) · 선택한 실험 조건 · [초기화][실험 실행]
 * 실행하면 만드는 중 화면으로
 */
type Vars = typeof mockLabVars;
type Stocks = typeof mockLabStocks;
const C = { ink: '#16171A', ink2: '#575B63', ink3: '#9A9EA7' };

export function AppLab({ vars, stocks, code, dirs, note, onBack, onPick, onDir, onReset, onRun }: {
  vars: Vars; dirs: LabDir[]; stocks: Stocks; code: string; note: string;
  onBack: () => void; onPick: (code: string) => void; onDir: (i: number, d: LabDir) => void; onReset: () => void; onRun: () => void;
}) {
  const insets = useSafeAreaInsets();
  const [sheet, setSheet] = useState(false);
  const cur = stocks.find((s) => s.stock_code === code) ?? stocks[0];
  const picked = vars.map((v, i) => ({ v, i })).filter(({ i }) => dirs[i] !== '유지');
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <Head title="투자 실험실" onBack={onBack} />
      <ScrollView contentContainerStyle={{ paddingBottom: 12 }} showsVerticalScrollIndicator={false}>
        <Text style={st.lsub}>{'아직 일어나지 않은 시장 환경을 가정하고,\n고른 종목에 닿을 수 있는 경로를 살펴봐요'}</Text>
        <View style={st.lnote}><View style={st.lnoteI}><Text style={st.lnoteIT}>i</Text></View><Text keepAll style={st.lnoteT}>{note}</Text></View>
        <Pressable onPress={() => setSheet(true)} accessibilityRole="button" style={st.lrow}>
          <Text style={st.lrowL}>실험할 종목</Text>
          <Text style={st.lrowB}>{cur.name} </Text>
          <View style={[st.op, cur.hold === '관심' && { backgroundColor: '#F2F2F5' }]}><Text style={[st.opT, cur.hold === '관심' && { color: C.ink2 }]}>{cur.hold}</Text></View>
          <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="#575B63" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: 6 }}><Path d="M6 9l6 6 6-6" /></Svg>
        </Pressable>
        {vars.map((v, i) => <Ind key={v.name} name={v.name} now={v.now} d={dirs[i]} onDir={(d) => onDir(i, d)} />)}
        <View style={st.selc}>
          <Text style={st.selcB}>선택한 실험 조건</Text>
          <Text style={st.selcP}>{cur.name}에 아래 시장 환경을 가정해요</Text>
          <View style={st.cc}>
            {picked.length ? picked.map(({ v, i }) => <View key={v.name} style={st.cchip}><Text style={[st.cchipT, { color: dirColor(dirs[i]) }]}>{v.name} · {dirs[i]}</Text></View>)
              : <Text style={st.emp}>조건을 하나 이상 골라 주세요 (유지만으로는 실험할 수 없어요)</Text>}
          </View>
        </View>
        <MiniSpace />
      </ScrollView>
      <BottomBar style={[st.lfoot, { paddingBottom: 10 + insets.bottom }]}>
        <PressScale onPress={onReset} accessibilityRole="button" style={[st.cta, st.gray]}><Text style={[st.ctaT, { color: C.ink }]}>초기화</Text></PressScale>
        <View style={{ flex: 1 }}>
          <PressScale disabled={!picked.length} onPress={onRun} accessibilityRole="button" style={[st.cta, !picked.length && { backgroundColor: '#C9CDD4' }]}>
            <Text style={st.ctaT}>실험 실행</Text>
          </PressScale>
        </View>
      </BottomBar>
      <Sheet open={sheet} onClose={() => setSheet(false)} label="실험할 종목">
        <View style={{ paddingHorizontal: 18 }}>
          <Text style={st.shH}>실험할 종목</Text>
          <Text style={st.shD}>내 종목(보유·관심) 중 하나를 골라요</Text>
          {(['보유', '관심'] as const).map((h) => (
            <View key={h}>
              <Text style={st.rlab}>{h}</Text>
              {stocks.filter((s) => s.hold === h).map((s) => {
                const on = s.stock_code === code;
                return (
                  <Pressable key={s.stock_code} onPress={() => { onPick(s.stock_code); setTimeout(() => setSheet(false), 260); }} accessibilityRole="radio" accessibilityState={{ selected: on }} style={st.rs}>
                    <Keep style={[st.lo, { backgroundColor: s.logo_bg }]}><Text style={st.loT}>{s.logo}</Text></Keep>
                    <Text style={st.rsT}>{s.name}</Text>
                    <View style={[st.op, h === '관심' && { backgroundColor: '#F2F2F5' }]}><Text style={[st.opT, h === '관심' && { color: C.ink2 }]}>{h}</Text></View>
                    <View style={[st.rd, on && { borderColor: C.ink }]}>{on ? <View style={st.rdI} /> : null}</View>
                  </Pressable>
                );
              })}
            </View>
          ))}
          <Text style={st.note}>회사 공시(사업보고서)에 민감도가 나온 지표만 &quot;공시 근거&quot;로 표시돼요</Text>
        </View>
      </Sheet>
    </View>
  );
}

/* .ind: 이름 · 지금 값 · 오른쪽 방향 글 · 상승/유지/하락 세그 (알약 미끄러짐) */
function Ind({ name, now, d, onDir }: { name: string; now: string; d: LabDir; onDir: (d: LabDir) => void }) {
  const [lay, setLay] = useState<Record<string, { x: number; width: number }>>({});
  return (
    <View style={st.ind}>
      <View style={st.indH}>
        <View style={{ flex: 1 }}><Text style={st.indN}>{name}</Text><Text style={st.indNow}>{now}</Text></View>
        <Text style={[st.indD, { color: d === '유지' ? C.ink3 : dirColor(d) }]}>{d}</Text>
      </View>
      <View style={st.seg}>
        <SlidingPill target={lay[d] ?? null} style={st.pill} />
        {(['상승', '유지', '하락'] as LabDir[]).map((x) => (
          <Pressable key={x} onPress={() => onDir(x)} onLayout={(e) => { const { x: lx, width } = e.nativeEvent.layout; setLay((a) => ({ ...a, [x]: { x: lx, width } })); }} accessibilityRole="tab" accessibilityState={{ selected: d === x }} style={st.segB}>
            <Text style={[st.segT, d === x && { color: x === '유지' ? C.ink : dirColor(x), fontWeight: '800' }]}>{x}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F3F4F6' },
  lsub: { fontSize: 13, lineHeight: 21, color: C.ink3, paddingHorizontal: 20, paddingBottom: 10 },
  lnote: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', backgroundColor: '#FFFFFF', borderRadius: 14, marginHorizontal: 16, marginBottom: 10, paddingVertical: 12, paddingHorizontal: 14 },
  lnoteI: { width: 18, height: 18, borderRadius: 9, borderWidth: 1.4, borderColor: '#9AA3B2', alignItems: 'center', justifyContent: 'center', marginTop: 2 },
  lnoteIT: { fontSize: 11, lineHeight: 17.6, fontWeight: '700', color: '#747D8D' },
  lnoteT: { flex: 1, fontSize: 12.5, lineHeight: 20, color: C.ink2 },
  lrow: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFFFFF', borderRadius: 16, marginHorizontal: 16, marginBottom: 10, paddingVertical: 14, paddingHorizontal: 16 },
  lrowL: { ...nf(12.5), color: C.ink3, marginRight: 'auto' },
  lrowB: { ...nf(15), fontWeight: '700', color: C.ink },
  op: { borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2, backgroundColor: '#EEE9FB' },
  opT: { ...nf(11), fontWeight: '700', color: '#5B3BD1' },
  ind: { backgroundColor: '#FFFFFF', borderRadius: 18, marginHorizontal: 16, marginBottom: 10, paddingVertical: 13, paddingHorizontal: 14 },
  indH: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 9 },
  indN: { ...nf(15), fontWeight: '800', color: C.ink },
  indNow: { ...nf(12), color: C.ink3, marginTop: 1 },
  indD: { ...nf(12.5), fontWeight: '800' },
  seg: { flexDirection: 'row', backgroundColor: '#F2F2F5', borderRadius: 13, padding: 4 },
  pill: { position: 'absolute', top: 4, bottom: 4, borderRadius: 10, backgroundColor: '#FFFFFF', shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  segB: { flex: 1, height: 38, alignItems: 'center', justifyContent: 'center' },
  segT: { ...nf(14), fontWeight: '600', color: C.ink3 },
  selc: { backgroundColor: '#F4F0FF', borderRadius: 18, marginHorizontal: 16, marginBottom: 10, paddingVertical: 14, paddingHorizontal: 16 },
  selcB: { ...nf(15), fontWeight: '700', color: C.ink },
  selcP: { ...nf(12), color: C.ink3, marginTop: 3, marginBottom: 8 },
  cc: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, minHeight: 28 },
  cchip: { height: 28, paddingHorizontal: 10, borderRadius: 14, backgroundColor: '#FFFFFF', justifyContent: 'center' },
  cchipT: { ...nf(12), fontWeight: '800' },
  emp: { fontSize: 12, lineHeight: 28, color: C.ink3 },
  lfoot: { flexDirection: 'row', gap: 8, paddingTop: 6, paddingHorizontal: 16, backgroundColor: '#F3F4F6' },
  cta: { height: 52, borderRadius: 15, backgroundColor: C.ink, alignItems: 'center', justifyContent: 'center' },
  gray: { width: 112, backgroundColor: '#ECEDF1' },
  ctaT: { ...nf(16), fontWeight: '800', color: '#FFFFFF' },
  shH: { ...nf(19), fontWeight: '700', color: C.ink, marginBottom: 4 },
  shD: { ...nf(12.5), color: C.ink3, marginBottom: 6 },
  rlab: { ...nf(12), fontWeight: '800', color: C.ink3, marginTop: 6, marginBottom: 2 },
  rs: { flexDirection: 'row', alignItems: 'center', gap: 12, height: 56, borderBottomWidth: 1, borderBottomColor: '#F0F1F4' },
  lo: { width: 34, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  loT: { ...nf(14), fontWeight: '800', color: '#FFFFFF' },
  rsT: { ...nf(15), fontWeight: '700', color: C.ink },
  rd: { marginLeft: 'auto', width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: '#C9CDD4', alignItems: 'center', justifyContent: 'center' },
  rdI: { width: 12, height: 12, borderRadius: 6, backgroundColor: C.ink },
  note: { ...nf(11.5), color: C.ink3, marginTop: 8, marginBottom: 10 },
});
