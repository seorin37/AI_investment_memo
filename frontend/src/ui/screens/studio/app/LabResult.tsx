import React from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Path } from 'react-native-svg';
import { BottomBar } from '@/ui/shared/app/BottomBar';
import { Text } from '@/components/ui/AppText';
import { PressScale } from '@/ui/motion/PressScale';
import { Head } from '../../my/app/parts';
import type { mockLabStocks, mockLabVars } from '../Studio.mock';
import { dirColor, type LabGroup } from '../labParts';
import type { LabMemo } from '../useLabMemo';
import { labWatchItems } from '../useLabWatch';
import { Keep } from '@/ui/shared/Dark';

/**
 * 앱 실험 결과 = 원본 studio.html #pgLr renderLabRes (20)
 * 종목 · 가정 칩 · 영향 경로 지도(조건 → 중간 → 끝 항목 ①② · 공시 근거는 보라 · 이론은 점선) · 항목별 설명(공시/이론 근거) ·
 * 앞으로 지켜볼 것 · 내 메모와 연결 · 안내 · 아래 [조건 바꿔 다시 실험]
 */
type Stock = (typeof mockLabStocks)[number];
type Vars = typeof mockLabVars;
const C = { ink: '#16171A', ink2: '#575B63', ink3: '#9A9EA7' };

export function AppLabResult({ stock, vars, groups, disclaimer, memo, onBack, onMemo, onAgain, onWatch, isAdded }: {
  stock: Stock; vars: Vars; groups: LabGroup[]; disclaimer: string;
  onBack: () => void; /** 그 종목의 내 메모 (없으면 메모 쓰기) */
  memo: LabMemo | null; onMemo: (id?: string) => void; onAgain: () => void;
  /** '메모에 추가' (2026-11-24, 주간보고서와 같게): i = 앞으로 지켜볼 것 순번 */
  onWatch?: (check: string, why: string, i: number) => void; isAdded?: (i: number) => boolean;
}) {
  const insets = useSafeAreaInsets();
  const all = groups.flatMap((g) => g.leaves);
  /* 웹과 같은 규칙 (같은 문장은 하나로 · 최대 3개) — '추가됨' 순번이 웹과 맞아야 함 */
  const chk = labWatchItems(groups);
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <Head title="실험 결과" onBack={onBack} />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 4, paddingBottom: 110 + insets.bottom }} showsVerticalScrollIndicator={false}>
        <View style={st.sh}><Keep style={[st.lo, { backgroundColor: stock.logo_bg }]}><Text style={st.loT}>{stock.logo}</Text></Keep><Text style={st.shT}>{stock.name}</Text></View>
        <View style={st.cds}>{groups.map((g) => <View key={g.i} style={st.cd}><Text style={st.cdT}>{vars[g.i].name} · <Text style={{ fontWeight: '600', color: dirColor(g.d) }}>{g.d}</Text> 가정</Text></View>)}</View>
        <Text style={st.lead}>바꾼 가정이 회사의 어떤 항목에 닿는지 경로로 보여 드려요.</Text>
        <View style={st.card}>
          <Text style={st.h4}>영향 경로 지도</Text>
          {groups.map((g) => {
            const n = g.leaves.length, H = n * 48 + (n - 1) * 8, cy = H / 2;
            return (
              <View key={g.i} style={st.mg}>
                <View style={st.mc}><Text style={st.mcT}>{vars[g.i].name}</Text><Text style={[st.mcS, { color: dirColor(g.d) }]}>가정 · {g.d}</Text></View>
                <View style={st.l1} />
                <View style={st.mm}><Text style={st.mmT}>{vars[g.i].mid}</Text></View>
                <Svg width={20} height={H} viewBox={`0 0 20 ${H}`}>
                  {g.leaves.map((l, k) => { const y = k * 56 + 24; return <Path key={l.no} d={`M0 ${cy} C10 ${cy} 10 ${y} 20 ${y}`} fill="none" stroke="#9A9EA7" strokeWidth={1.6} strokeDasharray={l.ev ? undefined : '2 3'} />; })}
                </Svg>
                <View style={st.lvs}>{g.leaves.map((l) => <View key={l.no} style={[st.lf, l.ev && st.lfEv]}><Text style={[st.lfT, l.ev && { color: '#4B2D93' }]}>{l.no} {l.t}</Text></View>)}</View>
              </View>
            );
          })}
          <View style={st.mlg}>
            <View style={st.mlgI}><View style={st.mlgL} /><Text style={st.mlgT}>회사 공시에 근거 있음</Text></View>
            <View style={st.mlgI}><View style={[st.mlgL, { borderStyle: 'dotted' }]} /><Text style={st.mlgT}>일반적인 이론 경로</Text></View>
          </View>
          {groups.length > 1 ? <Text keepAll style={st.mnote}>조건끼리도 서로 영향을 주고받아요. 그래서 하나로 합치지 않고 조건별로 따로 그렸어요.</Text> : null}
        </View>
        <View style={st.card}>
          <Text style={st.h4}>항목별 설명</Text>
          {all.map((l) => (
            <View key={l.no} style={st.ex}>
              <Text style={st.exT}>{l.no} {l.t}</Text>
              <Text keepAll style={st.exP}>{l.why}</Text>
              <View style={st.eb}>
                <View style={[st.em, l.ev ? { backgroundColor: '#EEE9FB' } : { backgroundColor: '#E9EAEE' }]}><Text style={[st.emT, { color: l.ev ? '#5B3BD1' : C.ink2 }]}>{l.ev ? '공시' : '이론'}</Text></View>
                <Text keepAll style={st.ebT}>{l.base}</Text>
              </View>
              {l.note ? <Text keepAll style={st.nb}>함께 볼 점 · {l.note}</Text> : null}
            </View>
          ))}
        </View>
        {chk.length ? (
          <View style={{ marginBottom: 12 }}>
            <View style={st.chkH}>
              <Svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="#5B3BD1" strokeWidth={2}><Path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><Circle cx={12} cy={12} r={3} /></Svg>
              <Text style={st.chkHT}>앞으로 지켜볼 것</Text>
            </View>
            {chk.map((w, i) => (
              <View key={w.check} style={[st.it, { flexDirection: 'row', alignItems: 'center', gap: 10 }]}>
                <View style={{ flex: 1, minWidth: 0 }}><Text keepAll style={st.itB}>{w.check}</Text>{w.why ? <Text keepAll style={st.itS}>{w.why}</Text> : null}</View>
                {isAdded?.(i) ? (
                  <View style={st.wDone}><Text style={st.wDoneT}>✓ 추가됨</Text></View>
                ) : onWatch ? (
                  <Pressable onPress={() => onWatch(w.check, w.why, i)} accessibilityRole="button" style={st.wBtn}><Text style={st.wBtnT}>메모에 추가</Text></Pressable>
                ) : null}
              </View>
            ))}
          </View>
        ) : null}
        <View style={st.ymemo}>
          <View style={st.yH}><Text style={st.yHT}>내 메모와 연결</Text><Pressable onPress={() => onMemo(memo?.id)} accessibilityRole="link" hitSlop={8}><Text style={[st.yHT, { fontWeight: '700', color: '#4A3800' }]}>{memo ? '원본 메모 보기 ›' : '메모 쓰기 ›'}</Text></Pressable></View>
          <Text keepAll style={st.yP}>{memo ? `“${memo.title}” — 이번 실험은 시장 환경 경로예요. 메모에서 지켜보는 항목과 나눠서 보면 좋아요.` : `${stock.name}에 남긴 메모가 없어요. 실험에서 본 경로를 메모로 남겨 두면 관련 소식을 모아 드려요.`}</Text>
        </View>
        <Text keepAll style={st.disc}>{disclaimer}</Text>
      </ScrollView>
      <BottomBar style={[st.bar, { paddingBottom: 26 + insets.bottom }]} pointerEvents="box-none">
        <PressScale onPress={onAgain} accessibilityRole="button" style={st.barB}><Text style={st.barT}>조건 바꿔 다시 실험</Text></PressScale>
      </BottomBar>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F3F4F6' },
  sh: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4, marginBottom: 10 },
  lo: { width: 28, height: 28, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  loT: { fontSize: 13, lineHeight: 17, fontWeight: '800', color: '#FFFFFF' },
  shT: { fontSize: 21, lineHeight: 28, fontWeight: '800', color: C.ink },
  cds: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  cd: { backgroundColor: '#EEF0F3', borderRadius: 10, paddingHorizontal: 10, paddingVertical: 5 },
  cdT: { fontSize: 12.5, lineHeight: 17, fontWeight: '600', color: '#3F434A' },
  lead: { fontSize: 13, lineHeight: 20, color: C.ink2, marginTop: 10, marginBottom: 14 },
  card: { backgroundColor: '#FFFFFF', borderRadius: 20, padding: 16, marginBottom: 12 },
  h4: { fontSize: 16, lineHeight: 22, fontWeight: '700', color: C.ink, marginBottom: 12 },
  mg: { flexDirection: 'row', alignItems: 'center', marginBottom: 14 },
  mc: { width: 86, backgroundColor: '#F6F6F8', borderRadius: 12, padding: 10 },
  mcT: { fontSize: 13, lineHeight: 18, fontWeight: '800', color: C.ink },
  mcS: { fontSize: 11.5, lineHeight: 16, color: C.ink3, marginTop: 3 },
  l1: { width: 12, height: 2, backgroundColor: '#C5C8CF' },
  mm: { width: 66, borderWidth: 1.5, borderColor: '#E2E4E8', borderRadius: 12, paddingVertical: 8, paddingHorizontal: 6, backgroundColor: '#FFFFFF' },
  mmT: { fontSize: 12, lineHeight: 16, fontWeight: '700', textAlign: 'center', color: C.ink },
  lvs: { flex: 1, minWidth: 0, gap: 8 },
  lf: { minHeight: 48, borderWidth: 1.5, borderColor: '#E2E4E8', borderRadius: 12, paddingVertical: 7, paddingHorizontal: 9, justifyContent: 'center', backgroundColor: '#FFFFFF' },
  lfEv: { backgroundColor: '#F3EEFF', borderColor: '#D9CCF7' },
  lfT: { fontSize: 12, lineHeight: 16, fontWeight: '700', color: C.ink },
  mlg: { flexDirection: 'row', gap: 14, marginTop: 6 },
  mlgI: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  mlgL: { width: 18, height: 0, borderTopWidth: 2, borderColor: '#8A8F98' },
  mlgT: { fontSize: 11.5, lineHeight: 16, color: C.ink3 },
  mnote: { fontSize: 12.5, lineHeight: 19, color: C.ink3, borderTopWidth: 1, borderTopColor: '#F0F1F4', marginTop: 12, paddingTop: 10 },
  ex: { borderWidth: 1, borderColor: '#ECEDF1', borderRadius: 16, padding: 14, marginBottom: 10 },
  exT: { fontSize: 15, lineHeight: 21, fontWeight: '800', color: C.ink },
  exP: { fontSize: 13.5, lineHeight: 21, color: '#3F434A', marginTop: 6, marginBottom: 10 },
  eb: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', backgroundColor: '#F6F6F8', borderRadius: 10, paddingVertical: 8, paddingHorizontal: 10 },
  em: { borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1 },
  emT: { fontSize: 11.5, lineHeight: 16, fontWeight: '800' },
  ebT: { flex: 1, fontSize: 12.5, lineHeight: 19, color: '#3F434A' },
  nb: { fontSize: 12.5, lineHeight: 19, color: C.ink3, marginTop: 8 },
  ymemo: { backgroundColor: '#FCEAAA', borderRadius: 16, padding: 14, marginBottom: 12 },
  yH: { flexDirection: 'row', justifyContent: 'space-between' },
  yHT: { fontSize: 12.5, lineHeight: 18, color: '#6B5200' },
  yP: { fontSize: 13, lineHeight: 21, color: '#3F3A2A', marginTop: 6 },
  chkH: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  chkHT: { fontSize: 14, lineHeight: 20, fontWeight: '800', color: '#5B3BD1' },
  it: { backgroundColor: '#FFFFFF', borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12, marginTop: 6 },
  itB: { fontSize: 13.5, lineHeight: 19, fontWeight: '700', color: C.ink },
  itS: { fontSize: 12, lineHeight: 17, color: C.ink3 },
  disc: { fontSize: 12, lineHeight: 17, color: C.ink3, textAlign: 'center', marginTop: 4 },
  wBtn: { height: 32, paddingHorizontal: 12, borderRadius: 10, backgroundColor: C.ink, justifyContent: 'center' },
  wBtnT: { fontSize: 12.5, lineHeight: 17, fontWeight: '700', color: '#FFFFFF' },
  wDone: { height: 32, paddingHorizontal: 10, borderRadius: 10, borderWidth: 1, borderColor: '#E6E3F3', justifyContent: 'center' },
  wDoneT: { fontSize: 12.5, lineHeight: 17, fontWeight: '600', color: '#8B95A1' },
  bar: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingTop: 12, paddingHorizontal: 16, backgroundColor: 'rgba(243,244,246,0.96)' },
  barB: { height: 54, borderRadius: 16, backgroundColor: C.ink, alignItems: 'center', justifyContent: 'center' },
  barT: { fontSize: 16, lineHeight: 22, fontWeight: '800', color: '#FFFFFF' },
});
