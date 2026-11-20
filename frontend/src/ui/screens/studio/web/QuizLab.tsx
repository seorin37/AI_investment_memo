import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { FeatIcon } from '@/ui/layout/web/StudioColumnFrame';
import type { LabDir, mockLabStocks, mockLabVars, mockQuiz } from '../Studio.mock';
import { dirColor, type LabGroup } from '../labParts';
import { GBtn } from './Credit';
import { Keep } from '@/ui/shared/Dark';

type Hover = { hovered?: boolean; pressed?: boolean };
const TR = { letterSpacing: -0.2 };
const Back = ({ onPress }: { onPress: () => void }) => (
  <Pressable onPress={onPress} accessibilityRole="button" style={st.back}>
    <Svg width={18} height={18} viewBox="0 0 18 18" fill="none"><Path d="M11.25 4.5L6.75 9L11.25 13.5" stroke="#404752" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" /></Svg>
    <Text style={st.backT}>스튜디오</Text>
  </Pressable>
);
const Chip = ({ t, dark, color }: { t: string; dark?: boolean; color?: string }) => (
  <View style={[st.chip, dark && { backgroundColor: '#15171A' }]}><Text style={[st.chipT, dark && { color: '#FFFFFF' }, color ? { color } : null]}>{t}</Text></View>
);
function FeatHead({ f, title, sub, chips }: { f: 'quiz' | 'lab'; title: string; sub?: string; chips?: React.ReactNode }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
      <View style={st.fi}><FeatIcon f={f} size={23} /></View>
      <View style={{ flex: 1, minWidth: 0, gap: chips ? 4 : 2, alignItems: 'flex-start' }}>
        <Text style={st.fT}>{title}</Text>
        {sub ? <Text style={st.fS}>{sub}</Text> : null}
        {chips ? <View style={{ flexDirection: 'row', gap: 6 }}>{chips}</View> : null}
      </View>
    </View>
  );
}

/**
 * 웹 오늘의 퀴즈 = 원본 studio.tsx Quiz (4지선다 · 스튜디오 열 안)
 * 원본 웹의 '크레딧 +2 · 참여 +1' 보상 표기는 크레딧 연결 전이라 뺌 (크레딧 숫자는 My.mock 그대로)
 */
export function WebQuiz({ q, done, onBack, onSubmit }: { q: typeof mockQuiz; done: number | null; onBack: () => void; onSubmit: (i: number) => void }) {
  const [pick, setPick] = useState<number | null>(null);
  const shown = done != null;
  const p = shown ? done : pick;
  const ok = done === q.answer;
  const streak = shown ? q.streak + 1 : q.streak;
  return (
    <ScrollView contentContainerStyle={st.box} showsVerticalScrollIndicator={false}>
      <Back onPress={onBack} />
      <FeatHead f="quiz" title="오늘의 퀴즈" chips={<><Chip t={`${q.day} 증시`} /><Chip t={q.type} dark /></>} />
      <Text style={st.q}>{q.q}</Text>
      <View style={{ gap: 8 }}>
        {q.options.map((o, i) => {
          const isAns = i === q.answer, mine = p === i;
          return (
            <Pressable key={o} disabled={shown} onPress={() => setPick(i)} accessibilityRole="radio" accessibilityState={{ selected: mine }}
              style={({ hovered }: Hover) => [st.opt, shown ? (isAns ? st.optAns : mine ? st.optNo : { opacity: 0.5 }) : mine ? st.optMine : hovered && { backgroundColor: '#F9F9F9' }]}>
              <View style={st.optN}><Text style={st.optNT}>{i + 1}</Text></View>
              <Text style={[st.optT, shown && isAns && { fontWeight: '700' }]}>{o}</Text>
              {shown && mine && !isAns ? <Text style={[st.tag, { color: '#D93033' }]}>내 선택</Text> : null}
              {shown && isAns ? <Text style={[st.tag, { color: '#383B40' }]}>정답</Text> : null}
            </Pressable>
          );
        })}
      </View>
      {!shown ? (
        <>
          <GBtn dark disabled={pick == null} onPress={() => pick != null && onSubmit(pick)}>제출하기</GBtn>
          <Text style={st.cap}>하루 한 번, 처음 제출한 답만 인정돼요</Text>
        </>
      ) : (
        <>
          <View style={[st.res, ok ? { backgroundColor: '#15171A' } : { backgroundColor: '#F5F6F8' }]}>
            <Text style={[st.resT, ok && { color: '#FFFFFF' }]}>{ok ? '정답이에요!' : `아쉬워요, 정답은 ${q.options[q.answer]}`}</Text>
          </View>
          <View style={st.exp}>
            <Text style={st.lbl}>해설</Text>
            <Text keepAll style={st.expT}>{q.exp} {q.concept}</Text>
            <Text style={st.lblN}>{q.src}</Text>
          </View>
          <View style={st.week}>
            <Text style={st.weekH}>{streak}일 연속 참여 중</Text>
            <View style={{ flexDirection: 'row', gap: 6 }}>
              {q.week.map(([d, s]) => { const on = s === 1 || s === 2; return <View key={d} style={[st.wd, on && { backgroundColor: '#15171A' }]}><Text style={[st.wdT, on && { color: '#FFFFFF' }]}>{d === '오늘' ? '토' : d}</Text></View>; })}
            </View>
          </View>
          <Text style={st.cap}>내일 오전 10시에 새 문제가 열려요</Text>
        </>
      )}
    </ScrollView>
  );
}

/** 웹 투자 실험실 = 원본 studio.tsx Lab (범위 안내 · 종목 고르기 · 조건 카드 · 가정 요약 · [초기화][실험 실행]) */
export function WebLab({ vars, stocks, code, dirs, note, onBack, onPick, onDir, onReset, onRun }: {
  vars: typeof mockLabVars; stocks: typeof mockLabStocks; code: string; dirs: LabDir[]; note: string;
  onBack: () => void; onPick: (code: string) => void; onDir: (i: number, d: LabDir) => void; onReset: () => void; onRun: () => void;
}) {
  const [open, setOpen] = useState(false);
  const cur = stocks.find((s) => s.stock_code === code) ?? stocks[0];
  const picked = vars.map((v, i) => ({ v, i })).filter(({ i }) => dirs[i] !== '유지');
  return (
    <ScrollView contentContainerStyle={st.box} showsVerticalScrollIndicator={false}>
      <Back onPress={onBack} />
      <FeatHead f="lab" title="투자 실험실" sub="시장 환경을 바꿔 보고, 내 종목에 닿는 경로를 살펴봐요" />
      <View style={st.limit}><View style={st.limitI}><Text style={st.limitIT}>i</Text></View><Text keepAll style={st.limitT}>{note}</Text></View>
      <Text style={st.lbl}>실험할 종목</Text>
      <View style={{ zIndex: 5 }}>
        <Pressable onPress={() => setOpen(!open)} accessibilityRole="button" accessibilityState={{ expanded: open }} style={st.dd}>
          <Text style={st.ddT}>{cur.name} <Text style={st.ddS}>· {cur.hold}</Text></Text>
          <Svg width={18} height={18} viewBox="0 0 18 18" fill="none" style={{ transform: [{ rotate: open ? '180deg' : '0deg' }] }}><Path d="M4.5 6.75L9 11.25L13.5 6.75" stroke="#404752" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" /></Svg>
        </Pressable>
        {open ? (
          <View style={st.menu}>
            {stocks.map((s) => (
              <Pressable key={s.stock_code} onPress={() => { onPick(s.stock_code); setOpen(false); }} style={({ hovered }: Hover) => [st.mi, s.stock_code === code ? { backgroundColor: '#F5F6F8' } : hovered && { backgroundColor: '#F9F9F9' }]}>
                <Text style={st.ddT}>{s.name} <Text style={st.ddS}>· {s.hold}</Text></Text>
              </Pressable>
            ))}
          </View>
        ) : null}
      </View>
      <Text style={st.lbl}>{picked.length ? '시장 환경 바꾸기' : '시장 환경 바꾸기 · 바꾸고 싶은 것만'}</Text>
      {vars.map((v, i) => (
        <View key={v.name} style={st.var}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <View><Text style={st.varN}>{v.name}</Text><Text style={st.varS}>{v.now}</Text></View>
            <Chip t={dirs[i]} color={dirs[i] === '유지' ? '#404752' : dirColor(dirs[i])} />
          </View>
          <View style={st.seg}>
            {(['상승', '유지', '하락'] as LabDir[]).map((d) => (
              <Pressable key={d} onPress={() => onDir(i, d)} accessibilityRole="tab" accessibilityState={{ selected: dirs[i] === d }} style={[st.segB, dirs[i] === d && st.segOn]}>
                <Text style={[st.segT, dirs[i] === d && { color: d === '유지' ? '#15171A' : dirColor(d) }]}>{d}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ))}
      <View style={st.sum}>
        {picked.length ? (
          <>
            <Text style={st.sumT}>{cur.name}에 아래 시장 환경을 가정해요</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{picked.map(({ v, i }) => <Chip key={v.name} t={`${v.name} · ${dirs[i]}`} color={dirColor(dirs[i])} />)}</View>
          </>
        ) : <Text style={[st.sumT, { color: '#8E8A97' }]}>바꾸고 싶은 시장 환경을 하나 이상 골라 주세요</Text>}
      </View>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <GBtn onPress={onReset}>초기화</GBtn>
        <GBtn flex dark disabled={!picked.length} onPress={onRun}>실험 실행</GBtn>
      </View>
    </ScrollView>
  );
}

/**
 * 웹 실험 결과 = 원본 studio.tsx LabResult + gen/LabResultBody
 * 원본의 '종합 방향 · 긍정/부정'(해석)은 넣지 않고, 경로 색도 방향 판단 없이 회색으로
 */
export function WebLabResult({ stock, vars, groups, disclaimer, onBack, onMemo, onAgain }: {
  stock: (typeof mockLabStocks)[number]; vars: typeof mockLabVars; groups: LabGroup[]; disclaimer: string;
  onBack: () => void; onMemo: () => void; onAgain: () => void;
}) {
  const all = groups.flatMap((g) => g.leaves.map((l) => ({ ...l, g })));
  return (
    <View style={{ flex: 1 }}>
      <ScrollView contentContainerStyle={{ paddingBottom: 12 }} showsVerticalScrollIndicator={false}>
        <View style={st.subHead}>
          <Pressable onPress={onBack} accessibilityRole="button" accessibilityLabel="뒤로" style={{ padding: 4, margin: -4 }}>
            <Svg width={24} height={24} viewBox="0 0 24 24" fill="none"><Path d="M19 12H5M12 5L5 12L12 19" stroke="black" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" /></Svg>
          </Pressable>
          <Text style={st.subHeadT}>실험 결과</Text>
        </View>
        <View style={{ gap: 16, paddingHorizontal: 16, paddingTop: 8 }}>
          <View style={{ gap: 8 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Keep style={[st.lo, { backgroundColor: stock.logo_bg }]}><Text style={st.loT}>{stock.logo}</Text></Keep>
              <Text style={st.name}>{stock.name}</Text>
            </View>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
              {groups.map((g) => <View key={g.i} style={st.pill}><Text style={st.pillT}>{vars[g.i].name} · <Text style={{ color: dirColor(g.d) }}>{g.d}</Text> 가정</Text></View>)}
            </View>
            <Text style={st.lead}>바꾼 가정이 회사의 어떤 항목에 닿는지 경로로 보여 드려요.</Text>
          </View>
          <View style={st.map}>
            <Text style={st.h}>영향 경로 지도</Text>
            {all.map((l) => (
              <View key={l.no} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <View style={st.from}><Text style={st.fromT}>{vars[l.g.i].name}</Text><Text style={[st.fromS, { color: dirColor(l.g.d) }]}>가정 · {l.g.d}</Text></View>
                <Svg width={22} height={10} viewBox="0 0 22 10" fill="none"><Path d="M1 5H20M16 1L20 5L16 9" stroke={l.ev ? '#575B63' : '#A9AFBA'} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={l.ev ? undefined : '3 3'} /></Svg>
                <View style={[st.to, l.ev && { backgroundColor: '#F3EEFF', borderColor: '#D9CCF7' }]}><Text style={st.no}>{l.no}</Text><Text style={st.toT}>{l.t}</Text></View>
              </View>
            ))}
            <Text style={st.note}>실선은 회사 공시에 근거 있음 · 점선은 일반적인 이론 경로예요.</Text>
            {groups.length > 1 ? <Text keepAll style={st.note}>조건끼리도 서로 영향을 주고받아요. 그래서 하나로 합치지 않고 조건별로 따로 그렸어요.</Text> : null}
          </View>
          <Text style={st.h}>항목별 설명</Text>
          {all.map((l) => (
            <View key={l.no} style={{ flexDirection: 'row', gap: 12 }}>
              <Text style={[st.no, { color: '#15171A' }]}>{l.no}</Text>
              <View style={{ flex: 1, minWidth: 0, gap: 4 }}>
                <Text style={st.exT}>{vars[l.g.i].name} {l.g.d} → {l.t}</Text>
                <Text keepAll style={st.exP}>{l.why}</Text>
                <Text keepAll style={st.note}>{l.ev ? '공시' : '이론'} · {l.base}</Text>
              </View>
            </View>
          ))}
          <View style={st.memo}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
              <Text style={st.memoH}>내 메모와 연결</Text>
              <Pressable onPress={onMemo} accessibilityRole="link">{({ hovered }: Hover) => <Text style={[st.memoL, hovered && { color: '#15171A' }]}>{stock.memo ? '원본 메모 보기 ›' : '메모 쓰기 ›'}</Text>}</Pressable>
            </View>
            <Text keepAll style={st.exP}>{stock.memo ? `“${stock.memo}” — ${stock.memo_text}` : `${stock.name}에 남긴 메모가 없어요. 실험에서 본 경로를 메모로 남겨 두면 관련 소식을 모아 드려요.`}</Text>
          </View>
          <Text keepAll style={st.note}>· {disclaimer}</Text>
        </View>
      </ScrollView>
      <View style={st.foot}>
        <Pressable onPress={onAgain} accessibilityRole="button" style={st.again}><Text style={st.againT}>조건 바꿔 다시 실험</Text></Pressable>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  box: { gap: 12, paddingHorizontal: 16, paddingBottom: 18, paddingTop: 6 },
  back: { flexDirection: 'row', alignItems: 'center', gap: 2, alignSelf: 'flex-start', paddingRight: 8 },
  backT: { fontSize: 15, lineHeight: 18, fontWeight: '700', color: '#404752', ...TR },
  fi: { width: 46, height: 46, borderRadius: 14, backgroundColor: '#F5F6F8', alignItems: 'center', justifyContent: 'center' },
  fT: { fontSize: 20, lineHeight: 26, fontWeight: '700', letterSpacing: -0.4, color: '#15171A' },
  fS: { fontSize: 15, lineHeight: 23, color: '#8E8A97', ...TR },
  chip: { height: 24, borderRadius: 999, paddingHorizontal: 9, justifyContent: 'center', backgroundColor: '#F5F6F8' },
  chipT: { fontSize: 13, lineHeight: 16, fontWeight: '700', color: '#404752' },
  q: { fontSize: 22, lineHeight: 32, fontWeight: '700', letterSpacing: -0.4, color: '#15171A' },
  opt: { flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 14, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF', paddingHorizontal: 14, paddingVertical: 12 },
  optMine: { borderWidth: 1.5, borderColor: '#15171A', backgroundColor: '#F5F6F8' },
  optAns: { borderWidth: 1.5, borderColor: '#6E6396', backgroundColor: '#F5F6F8' },
  optNo: { borderWidth: 1.5, borderColor: '#D93033', backgroundColor: '#F5F6F8' },
  optN: { width: 26, height: 26, borderRadius: 13, backgroundColor: '#F5F6F8', alignItems: 'center', justifyContent: 'center' },
  optNT: { fontSize: 13, lineHeight: 16, fontWeight: '700', color: '#15171A' },
  optT: { flex: 1, minWidth: 0, fontSize: 17, lineHeight: 20, fontWeight: '500', color: '#15171A', ...TR },
  tag: { fontSize: 14, lineHeight: 17, fontWeight: '700' },
  cap: { textAlign: 'center', fontSize: 14, lineHeight: 21, color: '#8E8A97', ...TR },
  res: { borderRadius: 18, paddingHorizontal: 16, paddingVertical: 14 },
  resT: { fontSize: 17, lineHeight: 20, fontWeight: '700', color: '#15171A' },
  exp: { gap: 6, borderRadius: 18, backgroundColor: '#F5F6F8', padding: 16 },
  lbl: { fontSize: 14, lineHeight: 21, fontWeight: '700', color: '#8E8A97', ...TR },
  lblN: { fontSize: 14, lineHeight: 21, color: '#8E8A97', ...TR },
  expT: { fontSize: 15, lineHeight: 24, color: '#15171A', ...TR },
  week: { gap: 10, borderRadius: 18, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF', padding: 16 },
  weekH: { fontSize: 17, lineHeight: 25, fontWeight: '700', color: '#15171A' },
  wd: { flex: 1, minWidth: 0, height: 36, borderRadius: 10, backgroundColor: '#F5F6F8', alignItems: 'center', justifyContent: 'center' },
  wdT: { fontSize: 14, lineHeight: 17, fontWeight: '700', color: '#8E8A97' },
  limit: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, borderRadius: 14, backgroundColor: '#F5F6F8', paddingHorizontal: 14, paddingVertical: 12 },
  limitI: { width: 18, height: 18, borderRadius: 9, borderWidth: 1, borderColor: '#9AA3B2', alignItems: 'center', justifyContent: 'center', marginTop: 2 },
  limitIT: { fontSize: 12, lineHeight: 14, fontWeight: '700', color: '#747D8D' },
  limitT: { flex: 1, minWidth: 0, fontSize: 14, lineHeight: 21, color: '#575B63', ...TR },
  dd: { height: 52, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderRadius: 14, borderWidth: 1, borderColor: '#D9D9D9', paddingHorizontal: 14 },
  ddT: { fontSize: 17, lineHeight: 20, fontWeight: '700', color: '#15171A', ...TR },
  ddS: { fontSize: 14, fontWeight: '400', color: '#8E8A97' },
  menu: { position: 'absolute', left: 0, right: 0, top: 56, zIndex: 20, borderRadius: 14, borderWidth: 1, borderColor: '#D9D9D9', backgroundColor: '#FFFFFF', padding: 4 },
  mi: { height: 48, borderRadius: 10, paddingHorizontal: 10, justifyContent: 'center' },
  var: { gap: 10, borderRadius: 16, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF', padding: 12, zIndex: -1 },
  varN: { fontSize: 17, lineHeight: 22, fontWeight: '700', color: '#15171A', ...TR },
  varS: { fontSize: 14, lineHeight: 18, color: '#8E8A97', ...TR },
  seg: { flexDirection: 'row', gap: 4, borderRadius: 12, backgroundColor: '#F5F6F8', padding: 4 },
  segB: { flex: 1, minWidth: 0, height: 40, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  segOn: { backgroundColor: '#FFFFFF', shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 3, shadowOffset: { width: 0, height: 1 } },
  segT: { fontSize: 15, lineHeight: 18, fontWeight: '700', color: '#8E8A97', ...TR },
  sum: { gap: 8, borderRadius: 18, backgroundColor: '#F5F6F8', padding: 14, zIndex: -1 },
  sumT: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: '#15171A', ...TR },
  subHead: { height: 48, flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16 },
  subHeadT: { fontSize: 20, lineHeight: 29, fontWeight: '700', color: '#16171A' },
  lo: { width: 26, height: 26, borderRadius: 7.8, alignItems: 'center', justifyContent: 'center' },
  loT: { fontSize: 15, lineHeight: 18, fontWeight: '700', color: '#FFFFFF' },
  name: { fontSize: 22, lineHeight: 30, fontWeight: '700', color: '#15171A' },
  pill: { borderRadius: 999, backgroundColor: '#F2F3F4', paddingHorizontal: 10, paddingVertical: 4 },
  pillT: { fontSize: 15, lineHeight: 21, fontWeight: '500', color: '#404752' },
  lead: { fontSize: 14, lineHeight: 21, color: '#747D8D' },
  map: { gap: 12, borderRadius: 12, borderWidth: 1, borderColor: '#E8ECF3', backgroundColor: '#FFFFFF', padding: 16 },
  h: { fontSize: 17, lineHeight: 24, fontWeight: '700', color: '#15171A' },
  from: { width: 118, borderRadius: 10, backgroundColor: '#F5F6F8', paddingHorizontal: 8, paddingVertical: 6 },
  fromT: { fontSize: 13, lineHeight: 18, fontWeight: '700', color: '#15171A' },
  fromS: { fontSize: 13, lineHeight: 18 },
  to: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 10, borderWidth: 1, borderColor: '#E3E6EB', backgroundColor: '#FFFFFF', padding: 8 },
  no: { fontSize: 14, lineHeight: 18, fontWeight: '700', color: '#575B63' },
  toT: { flex: 1, minWidth: 0, fontSize: 13, lineHeight: 18, fontWeight: '700', color: '#575B63' },
  note: { fontSize: 13, lineHeight: 20, color: '#8E8A97' },
  exT: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: '#15171A' },
  exP: { fontSize: 14, lineHeight: 21, color: '#575B63' },
  memo: { gap: 8, borderRadius: 12, backgroundColor: '#F7F8FA', padding: 16 },
  memoH: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: '#15171A' },
  memoL: { fontSize: 14, lineHeight: 20, fontWeight: '700', color: '#575B63' },
  foot: { flexDirection: 'row', borderTopWidth: 1, borderTopColor: '#E5E7EB', backgroundColor: '#FFFFFF', paddingHorizontal: 16, paddingVertical: 12 },
  again: { flex: 1, alignItems: 'center', justifyContent: 'center', borderRadius: 14, backgroundColor: '#16171A', paddingVertical: 14 },
  againT: { fontSize: 17, lineHeight: 22, fontWeight: '700', color: '#FFFFFF' },
});
