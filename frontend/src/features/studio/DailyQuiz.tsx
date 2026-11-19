/**
 * 오늘의 퀴즈 — 어제 증시 문제 1개(4지선다) · 제출(하루 한 번, 처음 제출한 답만) · 해설 · 이번 주 참여(연속 일수).
 * 체험판 studio.html 퀴즈. 보상 문구 없음(11.17). 상단 바(‹ 오늘의 퀴즈)는 TopBar 로 따로.
 * 움직임: 보기를 누르면 spring · 번호 원이 톡 · 제출하면 정답 체크가 튀고 틀린 보기는 흔들림
 *        · 해설이 펼쳐지며 떠오름 · "오늘도 참여했어요"가 튀어나옴 · 오늘 칸이 체크로 바뀌며 톡
 */
import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { Appear, PopWhen } from '@/components/motion/Appear';
import { Collapse } from '@/components/motion/Collapse';
import { LINEAR, ND, tween, useValue } from '@/components/motion/motion';
import { usePressScale } from '@/components/motion/StateMotion';
import type { DailyQuizProps, QuizDay } from '@/features/studio/DailyQuiz.types';

const C = {
  appBg: '#F3F4F6',
  card: '#FFFFFF',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  line: '#E3E5EA',
  white: '#FFFFFF',
  dark: '#16171A',
  accent: '#8569E3',
  accentSoft: '#EEE9FB',
  green: '#1F8A4C',
  greenSoft: '#E3F5EA',
  red: '#E5484D',
  redSoft: '#FFECEC',
  tag: '#D9F2E2',
} as const;
const PAD = 16;
const GAP = 14;
const R = { card: 20, opt: 14 };

export function DailyQuiz({ quiz, streak_days, week, submitted_index, onSubmit }: DailyQuizProps) {
  const [pick, setPick] = useState<number | null>(submitted_index);
  const done = submitted_index !== null;
  return (
    <ScrollView style={st.root} contentContainerStyle={st.body}>
      <View style={st.card}>
        <View style={st.tags}>
          <Text style={st.date}>{quiz.date_label}</Text>
          <View style={st.tag}><Text style={st.tagText}>4지선다</Text></View>
          <View style={st.tag}><Text style={st.tagText}>{streak_days}일 연속</Text></View>
        </View>
        <Text style={st.q}>{quiz.question}</Text>
        <Text style={st.rule}>하루 한 번, 처음 제출한 답만 인정돼요</Text>
        {quiz.options.map((o, i) => (
          <Option key={o} text={o} n={i + 1} on={pick === i && !done} done={done} ans={done && i === quiz.answer_index} wrong={done && i === submitted_index && i !== quiz.answer_index}
            onPress={() => !done && setPick(pick === i ? null : i)} />
        ))}
        <Collapse open={done} duration={450}>
          <Appear kind="up" replay={done} style={st.exp}>
            <Text style={st.expHead}>{submitted_index === quiz.answer_index ? '정답이에요' : `정답은 ${quiz.options[quiz.answer_index]}예요`}</Text>
            <Text style={st.expText}>{quiz.explanation}</Text>
            <Text style={st.conceptHead}>관련 개념</Text>
            <Text style={st.expText}>{quiz.concept}</Text>
            <Text style={st.src}>출처 · {quiz.source}</Text>
          </Appear>
        </Collapse>
        {!done && (
          <>
            <SubmitBtn disabled={pick === null} onPress={() => pick !== null && onSubmit(pick)} />
            <Text style={st.rule2}>제출하면 바꿀 수 없어요 · 다시 누르면 고른 것이 풀려요</Text>
          </>
        )}
      </View>

      {done && <Appear kind="pop" delay={250} style={st.joined}><Text style={st.joinedText}>오늘도 참여했어요 · {streak_days}일 연속 참여 중</Text></Appear>}

      <View style={st.card}>
        <View style={st.wkHead}><Text style={st.wkTitle}>이번 주 참여</Text><Text style={st.wkStreak}>{streak_days}일 연속 참여 중</Text></View>
        <View style={st.week}>{week.map((d) => <Day key={d.label} d={d} />)}</View>
        <Text style={st.wkNote}>하루라도 빠지면 연속 기록이 처음부터 다시 시작돼요</Text>
      </View>
      <Text style={st.next}>내일 오전 10시에 새 문제가 열려요</Text>
    </ScrollView>
  );
}

function Option({ text, n, on, done, ans, wrong, onPress }: { text: string; n: number; on: boolean; done: boolean; ans: boolean; wrong: boolean; onPress: () => void }) {
  const p = usePressScale(0.97);
  const shake = useValue(0);
  const was = useRef(wrong);
  useEffect(() => {
    if (wrong && !was.current) { shake.setValue(0); tween(shake, 1, 420, LINEAR, ND, 120).start(); }
    was.current = wrong;
  }, [wrong, shake]);
  const translateX = shake.interpolate({ inputRange: [0, 0.15, 0.35, 0.55, 0.75, 1], outputRange: [0, -6, 5, -3, 2, 0] });
  return (
    <Pressable onPress={onPress} onPressIn={done ? undefined : p.onPressIn} onPressOut={done ? undefined : p.onPressOut} disabled={done} accessibilityRole="radio" accessibilityState={{ selected: on || ans }}>
      <Animated.View style={[st.opt, on && st.optOn, ans && st.optAns, wrong && st.optWrong, { transform: [{ scale: p.scale }, { translateX }] }]}>
        <View style={[st.num, on && st.numOn, ans && st.numAns]}>
          {ans ? <Appear kind="scale" delay={150}><MobileIcon name="check" size={14} color={C.white} strokeWidth={2.6} /></Appear>
            : <PopWhen show replay={on}><Text style={[st.numText, on && st.numTextOn]}>{n}</Text></PopWhen>}
        </View>
        <Text style={st.optText}>{text}</Text>
      </Animated.View>
    </Pressable>
  );
}

function SubmitBtn({ disabled, onPress }: { disabled: boolean; onPress: () => void }) {
  const p = usePressScale(0.96);
  return (
    <Pressable onPress={onPress} onPressIn={p.onPressIn} onPressOut={p.onPressOut} disabled={disabled} accessibilityRole="button" accessibilityState={{ disabled }}>
      <Animated.View style={[st.submit, disabled && st.submitDis, { transform: [{ scale: p.scale }] }]}><Text style={st.submitText}>제출하기</Text></Animated.View>
    </Pressable>
  );
}

function Day({ d }: { d: QuizDay }) {
  return (
    <View style={st.day}>
      <View style={[st.dayDot, d.state === 'done' && st.dayDone, d.state === 'today' && st.dayToday]}>
        <PopWhen show={d.state === 'done'}><MobileIcon name="check" size={14} color={C.white} strokeWidth={2.6} /></PopWhen>
      </View>
      <Text style={[st.dayText, d.state === 'today' && st.dayTextToday]}>{d.label}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.appBg },
  body: { padding: PAD, gap: GAP, paddingBottom: 40 },
  card: { backgroundColor: C.card, borderRadius: R.card, padding: 18 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 },
  date: { fontSize: 13, color: C.sub, marginRight: 2 },
  tag: { backgroundColor: C.tag, borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 },
  tagText: { fontSize: 11.5, fontWeight: '700', color: C.green },
  q: { fontSize: 20, fontWeight: '800', color: C.text, lineHeight: 28, marginTop: 12 },
  rule: { fontSize: 12.5, color: C.muted, marginTop: 6, marginBottom: 12 },
  opt: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 52, borderRadius: R.opt, borderWidth: 1.5, borderColor: C.line, paddingHorizontal: 14, marginBottom: 8 },
  optOn: { borderColor: C.accent, backgroundColor: C.accentSoft },
  optAns: { borderColor: C.green, backgroundColor: C.greenSoft },
  optWrong: { borderColor: C.red, backgroundColor: C.redSoft },
  num: { width: 24, height: 24, borderRadius: 12, backgroundColor: C.appBg, alignItems: 'center', justifyContent: 'center' },
  numOn: { backgroundColor: C.accent },
  numAns: { backgroundColor: C.green },
  numText: { fontSize: 12.5, fontWeight: '800', color: C.sub },
  numTextOn: { color: C.white },
  optText: { flex: 1, fontSize: 15.5, fontWeight: '600', color: C.text },
  submit: { height: 52, borderRadius: 14, backgroundColor: C.dark, alignItems: 'center', justifyContent: 'center', marginTop: 6 },
  submitDis: { opacity: 0.35 },
  submitText: { fontSize: 16, fontWeight: '800', color: C.white },
  rule2: { fontSize: 12, color: C.muted, textAlign: 'center', marginTop: 8 },
  exp: { backgroundColor: C.appBg, borderRadius: R.opt, padding: 14, marginTop: 6, marginBottom: 2 },
  expHead: { fontSize: 15, fontWeight: '800', color: C.text },
  expText: { fontSize: 13.5, lineHeight: 21, color: C.sub, marginTop: 4 },
  conceptHead: { fontSize: 13, fontWeight: '800', color: C.text, marginTop: 10 },
  src: { fontSize: 12, color: C.muted, marginTop: 10 },
  joined: { backgroundColor: C.greenSoft, borderRadius: R.opt, padding: 14, alignItems: 'center' },
  joinedText: { fontSize: 14, fontWeight: '800', color: C.green },
  wkHead: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' },
  wkTitle: { fontSize: 16, fontWeight: '800', color: C.text },
  wkStreak: { fontSize: 13, fontWeight: '700', color: C.green },
  week: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 14 },
  day: { alignItems: 'center', gap: 6 },
  dayDot: { width: 30, height: 30, borderRadius: 15, backgroundColor: C.appBg, alignItems: 'center', justifyContent: 'center' },
  dayDone: { backgroundColor: C.green },
  dayToday: { borderWidth: 2, borderColor: C.green, backgroundColor: C.card },
  dayText: { fontSize: 12, color: C.muted },
  dayTextToday: { color: C.text, fontWeight: '800' },
  wkNote: { fontSize: 12, color: C.muted, marginTop: 12 },
  next: { textAlign: 'center', fontSize: 12.5, color: C.muted },
});
