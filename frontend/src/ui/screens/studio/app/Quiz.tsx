import React, { useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Path } from 'react-native-svg';
import { MiniSpace } from '@/ui/screens/studio/app/MiniBar';
import { Text } from '@/components/ui/AppText';
import { FadeIn } from '@/ui/motion/Reveal';
import { PressScale } from '@/ui/motion/PressScale';
import { Head } from '../../my/app/parts';
import type { mockQuiz } from '../Studio.mock';
import { PopBurst } from '@/components/motion/Celebrate';

/* 원본 studio.html confetti 색 */
const QCONF = ['#8569E3', '#1F8A4C', '#FFC53D', '#E5484D', '#3D73F0'] as const;

/**
 * 앱 오늘의 퀴즈 = 원본 studio.html #pgQz (12 고름 · 13 정답)
 * 머리 줄(어제 증시 퀴즈 · 4지선다 · N일 연속) · 문제 카드(보기 50 · 고르면 보라 · 정답 초록 · 오답 빨강) · [제출하기] ·
 * 결과(정답이에요/아쉬워요 · 해설 · 관련 개념 · 출처) · 참여 · 이번 주 참여 · 다음 문제 안내
 * 제출은 화면 상태만. 원본의 색종이 효과는 생략
 */
type Q = typeof mockQuiz;
const C = { ink: '#16171A', ink2: '#575B63', ink3: '#9A9EA7' };
const CHK = <Svg width={14} height={14} viewBox="0 0 14 14" fill="none"><Path d="M3 7.3l2.6 2.6L11 4.4" stroke="#fff" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" /></Svg>;

export function AppQuiz({ q, done, locked = false, onBack, onSubmit }: { q: Q; done: number | null; /** 문제·기록을 읽는 중이면 보기·제출 막음 */ locked?: boolean; onBack: () => void; onSubmit: (i: number) => void }) {
  const insets = useSafeAreaInsets();
  const [sel, setSel] = useState<number | null>(null);
  const shown = done != null;
  const ok = done === q.answer;
  const streak = shown ? q.streak + 1 : q.streak;
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <Head title="오늘의 퀴즈" onBack={onBack} />
      <ScrollView contentContainerStyle={{ paddingBottom: 24 + insets.bottom }} showsVerticalScrollIndicator={false}>
        <View style={st.qm}>
          <Text style={st.qmT}>{q.label}</Text>
          <Text style={st.qmT}>{q.type}</Text>
          <View style={st.stk}><Text style={st.stkT}>{streak}일 연속</Text></View>
        </View>
        <View style={st.qcard}>
          <Text style={st.qH}>{q.q}</Text>
          {q.options.map((o, i) => {
            const isAns = shown && i === q.answer;
            const wrong = shown && i === done && !ok;
            const on = !shown && sel === i;
            return (
              <PressScale key={o} scaleTo={0.98} disabled={shown || locked} onPress={() => setSel(sel === i ? null : i)} accessibilityRole="radio" accessibilityState={{ selected: on }} style={[st.opt, on && st.optSel, isAns && st.optOk, wrong && st.optNo]}>
                <Text style={st.optN}>{i + 1}.</Text>
                <Text style={[st.optT, on && { color: '#4B2E9E' }, isAns && { color: '#14653A' }, wrong && { color: '#B42318' }]}>{o}</Text>
                {isAns ? <Svg width={20} height={20} viewBox="0 0 20 20" style={{ marginLeft: 'auto' }}><Circle cx={10} cy={10} r={10} fill="#1F8A4C" /><Path d="M5.5 10.3l3 3L14.5 7" fill="none" stroke="#fff" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" /></Svg> : null}
                {wrong ? <Svg width={20} height={20} viewBox="0 0 20 20" style={{ marginLeft: 'auto' }}><Circle cx={10} cy={10} r={10} fill="#E5484D" /><Path d="M6.5 6.5l7 7M13.5 6.5l-7 7" stroke="#fff" strokeWidth={2.2} strokeLinecap="round" /></Svg> : null}
                {/* 정답이면 그 보기 가운데서 26조각 (원본 studio.html confetti(os[ANS]) · .cf 7×11 · 1s) */}
                {isAns && ok ? <PopBurst fire={1} colors={QCONF} w={7} h={11} dur={1000} spin={540} /> : null}
              </PressScale>
            );
          })}
          {!shown ? <Text style={st.qhint}>하루 한 번, 처음 제출한 답만 인정돼요</Text> : (
            <FadeIn>
              <Text style={[st.verdict, { color: ok ? '#1F8A4C' : '#C2262E' }]}>{ok ? '정답이에요!' : `아쉬워요, 정답은 ${q.options[q.answer]}`}</Text>
              <View style={st.expl}>
                <Text keepAll style={st.explT}>{q.exp}</Text>
                <View style={st.cp}><Text style={st.cpT}>관련 개념</Text></View>
                <Text keepAll style={st.explT}>{q.concept}</Text>
                <Text style={st.src}>{q.src}</Text>
              </View>
            </FadeIn>
          )}
        </View>
        {!shown ? (
          <>
            <View style={{ marginTop: 12, marginHorizontal: 16 }}>
              <PressScale disabled={sel == null || locked} onPress={() => sel != null && !locked && onSubmit(sel)} accessibilityRole="button" style={[st.cta, (sel == null || locked) && { backgroundColor: '#C9CDD4' }]}><Text style={st.ctaT}>제출하기</Text></PressScale>
            </View>
            <Text style={st.qcap}>제출하면 바꿀 수 없어요 · 다시 누르면 고른 것이 풀려요</Text>
          </>
        ) : (
          <FadeIn>
            <View style={st.gain}>
              <Svg width={22} height={22} viewBox="0 0 22 22"><Circle cx={11} cy={11} r={9.5} fill="none" stroke="#1F8A4C" strokeWidth={1.8} /><Path d="M7.5 8h7M7.5 11h7M11 8v7" stroke="#1F8A4C" strokeWidth={1.8} strokeLinecap="round" /></Svg>
              <Text style={st.gainT}>오늘도 참여했어요 · {streak}일 연속 참여 중</Text>
            </View>
            <View style={st.week}>
              <View style={{ flexDirection: 'row' }}><Text style={st.weekH}>이번 주 참여</Text><Text style={st.weekS}>{streak}일 연속 참여 중</Text></View>
              <View style={st.days}>
                {q.week.map(([d, s]) => {
                  const on = s === 1 || s === 2;
                  return (
                    <View key={d} style={st.dy}>
                      <View style={[st.dyI, on && { backgroundColor: '#1F8A4C' }, s === 3 && st.dyFut, s === 2 && st.dyToday]}>{on ? CHK : null}</View>
                      <Text style={[st.dyT, s === 2 && { color: C.ink, fontWeight: '800' }]}>{d}</Text>
                    </View>
                  );
                })}
              </View>
              <Text style={st.weekP}>하루라도 빠지면 연속 기록이 처음부터 다시 시작돼요</Text>
            </View>
            <Text style={[st.qcap, { marginTop: 14 }]}>내일 오전 10시에 새 문제가 열려요</Text>
          </FadeIn>
        )}
        <MiniSpace />
      </ScrollView>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F3F4F6' },
  qm: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingHorizontal: 20, paddingBottom: 10 },
  qmT: { fontSize: 12, lineHeight: 17, color: C.ink2 },
  stk: { marginLeft: 'auto', backgroundColor: '#E4F5EA', borderRadius: 10, paddingHorizontal: 9, paddingVertical: 3 },
  stkT: { fontSize: 12, lineHeight: 17, fontWeight: '800', color: '#1B7A45' },
  qcard: { backgroundColor: '#FFFFFF', borderRadius: 22, marginHorizontal: 16, paddingTop: 18, paddingHorizontal: 14, paddingBottom: 14 },
  qH: { fontSize: 19, lineHeight: 27, fontWeight: '700', color: C.ink, marginBottom: 12, paddingHorizontal: 2 },
  opt: { flexDirection: 'row', alignItems: 'center', gap: 10, height: 50, borderRadius: 14, borderWidth: 1.5, borderColor: '#E2E4E8', marginBottom: 8, paddingHorizontal: 14 },
  optSel: { backgroundColor: '#F1ECFF', borderWidth: 2, borderColor: '#8569E3' },
  optOk: { backgroundColor: '#E9F7EE', borderWidth: 2, borderColor: '#1F8A4C' },
  optNo: { backgroundColor: '#FFF0F0', borderWidth: 2, borderColor: '#E5484D' },
  optN: { width: 18, fontSize: 15, lineHeight: 21, fontWeight: '600', color: C.ink3 },
  optT: { fontSize: 15, lineHeight: 21, fontWeight: '600', color: C.ink },
  qhint: { fontSize: 11.5, lineHeight: 16, color: C.ink3, paddingTop: 4, paddingHorizontal: 2 },
  verdict: { fontSize: 16, lineHeight: 22, fontWeight: '800', marginTop: 6, marginBottom: 8, marginHorizontal: 4 },
  expl: { backgroundColor: '#F6F7F9', borderRadius: 14, padding: 12 },
  explT: { fontSize: 13, lineHeight: 22, color: C.ink2 },
  cp: { alignSelf: 'flex-start', backgroundColor: '#FFFFFF', borderRadius: 7, paddingHorizontal: 8, paddingVertical: 1, marginTop: 6, marginBottom: 4 },
  cpT: { fontSize: 11.5, lineHeight: 16, fontWeight: '700', color: C.ink },
  src: { fontSize: 13, lineHeight: 20, color: C.ink3, marginTop: 4 },
  cta: { height: 54, borderRadius: 15, backgroundColor: C.ink, alignItems: 'center', justifyContent: 'center' },
  ctaT: { fontSize: 16, lineHeight: 22, fontWeight: '800', color: '#FFFFFF' },
  qcap: { textAlign: 'center', fontSize: 12, lineHeight: 17, color: C.ink3, marginTop: 8 },
  gain: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#E9F7EE', borderRadius: 16, marginTop: 10, marginHorizontal: 16, paddingVertical: 14, paddingHorizontal: 16 },
  gainT: { fontSize: 14.5, lineHeight: 20, fontWeight: '800', color: '#14653A' },
  week: { backgroundColor: '#FFFFFF', borderRadius: 20, marginTop: 10, marginHorizontal: 16, paddingVertical: 14, paddingHorizontal: 16 },
  weekH: { fontSize: 15, lineHeight: 21, fontWeight: '800', color: C.ink },
  weekS: { marginLeft: 'auto', fontSize: 13, lineHeight: 21, fontWeight: '800', color: '#1F8A4C' },
  days: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 12, marginBottom: 8 },
  dy: { alignItems: 'center', gap: 5 },
  dyI: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F0F1F4' },
  dyFut: { backgroundColor: 'transparent', borderWidth: 1.5, borderColor: '#D5D8DD', borderStyle: 'dashed' },
  /* 오늘: 흰 테두리 + 초록 고리 (원본 box-shadow 2겹 대신 테두리) */
  dyToday: { borderWidth: 2, borderColor: '#9ED8B4' },
  dyT: { fontSize: 11.5, lineHeight: 16, color: C.ink3 },
  weekP: { fontSize: 11.5, lineHeight: 16, color: C.ink3, marginTop: 2 },
});
