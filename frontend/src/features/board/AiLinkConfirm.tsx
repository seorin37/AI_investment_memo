/**
 * AI 연결 — ① 메모 저장 ✓ → ② 항목 확인 → ③ 연결 시작. 메모에서 찾은 항목 중 사용자가 고른 것만 연결.
 * 체험판 memo.html '12 · 12.1 AI 연결'. 상단 바(✕ · AI 연결)는 TopBar 로 따로.
 * 움직임: 단계 사이 선이 차오름(.5s) · 찾는 중 돌개 + 빛줄기 뼈대(#079) · 찾은 항목 카드가 차례로 튀어 오름(tipop .55s · 60ms)
 *         · 체크 상자 잉크(#014) · 완료 원이 0 → 1 로 튀고(.55s spring) 체크가 그려짐(.45s) · 버튼 누름 spring
 */
import { useEffect } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Appear } from '@/components/motion/Appear';
import { InkCheck } from '@/components/motion/InkCheck';
import { EASE, tween, useProgress, useValue } from '@/components/motion/motion';
import { Shimmer } from '@/components/motion/Skeleton';
import { Spinner, usePressScale } from '@/components/motion/StateMotion';
import { BOARD_C as C, MEMO_PAPER } from '@/features/board/boardTokens';
import type { AiLinkConfirmProps, TrackingCandidate } from '@/features/board/AiLinkConfirm.types';

const PAD = 16;
const R = { card: 18, btn: 14 };
const won = (n: number) => `${n.toLocaleString('ko-KR')}원`;

export function AiLinkConfirm({ step, stock_name, memo, candidates, onToggleCandidate, onConnect, onLater, onEditMemo }: AiLinkConfirmProps) {
  const picked = candidates.filter((c) => c.selected).length;
  const stepNo = step === 'done' ? 3 : 2;
  return (
    <View style={st.root}>
      <View style={st.steps}>
        {['메모 저장', '항목 확인', '연결 시작'].map((t, i) => (
          <View key={t} style={[st.stepItem, i < 2 && st.flexItem]}>
            <View style={[st.stepDot, i + 1 <= stepNo && st.stepDotOn]}>
              <Text style={[st.stepNum, i + 1 <= stepNo && st.stepNumOn]}>{i + 1 < stepNo ? '✓' : i + 1}</Text>
            </View>
            <Text style={[st.stepText, i + 1 <= stepNo && st.stepTextOn]}>{t}</Text>
            {i < 2 && <StepLine on={i + 1 < stepNo} />}
          </View>
        ))}
      </View>

      {step === 'done' ? (
        <View style={st.done}>
          <DoneCheck />
          <Appear kind="up" index={4}><Text style={st.doneTitle}>AI 연결을 켰어요</Text></Appear>
          <Appear kind="up" index={5}><Text style={st.doneText}>{picked}개 항목과 관련된 공시·뉴스·종가 변화가 생기면{'\n'}이 메모의 AI 업데이트에 모아 드려요.</Text></Appear>
        </View>
      ) : (
        <ScrollView contentContainerStyle={st.body}>
          <Text style={st.q}>무엇을 계속 확인할까요?</Text>
          <Text style={st.qd}>메모에서 찾은 항목이에요. 선택한 항목만 연결돼요.</Text>
          <View style={[st.memo, { backgroundColor: MEMO_PAPER[memo.color].bg }]}>
            <View style={st.memoTag}><Text style={st.memoTagText}>{stock_name} · 내 메모</Text></View>
            <Text style={st.memoTitle}>{memo.title}</Text>
            <Text style={st.memoBody}>{memo.body}</Text>
          </View>

          {step === 'scanning' && (
            <>
              <View style={st.scanRow}><Spinner color={C.accent} track={C.accentSoft} /><Text style={st.scan}>메모에서 계속 확인할 항목을 찾고 있어요</Text></View>
              <Shimmer style={st.skel} color={C.skeleton} offset_x={PAD} /><Shimmer style={st.skel} color={C.skeleton} offset_x={PAD} />
            </>
          )}

          {step === 'none' && (
            <Appear kind="up" style={st.none}>
              <Text style={st.noneTitle}>추적할 항목을 찾지 못했어요</Text>
              <Text style={st.noneText}>메모는 일반 메모로 그대로 저장돼요.{'\n'}확인할 사실이나 가격 조건을 구체적으로 적고{'\n'}다시 확인해 보세요.</Text>
              <View style={st.exBox}>
                <Text style={st.exHead}>이렇게 적으면 찾을 수 있어요</Text>
                <Text style={st.ex}>공시·뉴스 · "다음 정기보고서에서 HBM 매출 확인하기"</Text>
                <Text style={st.ex}>가격 조건 · "20만원 아래로 내려오면 다시 보기"</Text>
              </View>
            </Appear>
          )}

          {step === 'select' && (
            <>
              <Text style={st.found}>찾은 항목 <Text style={st.foundNum}>{candidates.length}</Text></Text>
              {candidates.map((c, i) => <Appear key={c.id} kind="pop" index={i}><Candidate c={c} onPress={() => onToggleCandidate(c.id)} /></Appear>)}
              <Text style={st.ainfo}>✦ AI는 메모를 수정하지 않아요. 선택한 항목과 관련된 사실과 출처만 연결해요.</Text>
            </>
          )}
        </ScrollView>
      )}

      {step === 'select' && (
        <Appear kind="rise" style={st.bar}>
          <Btn gray onPress={onLater} label="나중에" />
          <Btn onPress={onConnect} disabled={!picked} label={picked ? `✦ ${picked}개 항목으로 AI 연결` : '항목을 골라 주세요'} />
        </Appear>
      )}
      {step === 'none' && (
        <Appear kind="rise" style={st.bar}>
          <Btn onPress={onEditMemo} label="메모 수정" />
          <Btn gray onPress={onLater} label="메모로 돌아가기" />
        </Appear>
      )}
    </View>
  );
}

/** 단계 사이 선: 지나간 단계면 왼쪽부터 차오름 (.5s) */
function StepLine({ on }: { on: boolean }) {
  const t = useValue(on ? 1 : 0);
  useEffect(() => { tween(t, on ? 1 : 0, 500, EASE, false).start(); }, [on, t]);
  return (
    <View style={st.stepLine}>
      <Animated.View style={[st.stepLineFill, { width: t.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] }) }]} />
    </View>
  );
}

/** 완료: 원이 0 → 1 로 튀고(pop2 .55s spring) .3초 뒤 체크가 그려짐(.45s) */
function DoneCheck() {
  const draw = useProgress('done', 450, EASE, 300);
  const L = 30;
  return (
    <Appear kind="scale">
      <View style={st.doneCk}>
        <Svg width={40} height={40} viewBox="0 0 24 24">
          <Path d="M5 12.5l4.5 4.5L19 7.5" stroke={C.white} strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" fill="none" strokeDasharray={`${L} ${L}`} strokeDashoffset={L * (1 - draw)} />
        </Svg>
      </View>
    </Appear>
  );
}

function Btn({ label, onPress, gray, disabled }: { label: string; onPress: () => void; gray?: boolean; disabled?: boolean }) {
  const p = usePressScale(0.96);
  return (
    <Pressable style={[st.btnHit, gray && st.btnHitGray]} onPress={onPress} onPressIn={p.onPressIn} onPressOut={p.onPressOut} disabled={disabled} accessibilityRole="button" accessibilityState={{ disabled }}>
      <Animated.View style={[st.btn, gray ? st.btnGray : st.btnMain, disabled && st.btnDis, { transform: [{ scale: p.scale }] }]}>
        <Text style={gray ? st.btnGrayText : st.btnMainText} numberOfLines={1}>{label}</Text>
      </Animated.View>
    </Pressable>
  );
}

function Candidate({ c, onPress }: { c: TrackingCandidate; onPress: () => void }) {
  const price = c.kind === 'price';
  return (
    <Pressable style={[st.cand, !c.selected && st.candOff]} onPress={onPress} accessibilityRole="checkbox" accessibilityState={{ checked: c.selected }}>
      <View style={st.cb}><InkCheck checked={c.selected} color={C.accent} lineColor={C.chipLine} size={22} radius={7} /></View>
      <View style={st.flex}>
        <View style={[st.chp, { backgroundColor: price ? C.greenSoft : C.blueSoft }]}>
          <Text style={[st.chpText, { color: price ? C.green : C.blue }]}>{price ? '가격 조건' : '공시·뉴스'}</Text>
        </View>
        <Text style={st.candTitle}>{c.label}</Text>
        {price && c.price ? (
          <>
            <View style={st.tb}>
              <View style={st.tbCol}><Text style={st.tbK}>판정 기준</Text><Text style={st.tbV}>전일 종가</Text></View>
              <View style={st.tbCol}><Text style={st.tbK}>조건</Text><Text style={st.tbV}>{won(c.price.condition)} {c.price.direction}</Text></View>
              <View style={st.tbCol}><Text style={st.tbK}>확인 시점</Text><Text style={st.tbV}>매 거래일 장 마감 후</Text></View>
            </View>
            <Text style={st.candSub}>ⓘ 실시간 알림이 아닌 종가 기준이에요.</Text>
          </>
        ) : (
          <>
            <Text style={st.candSub}>정기보고서와 뉴스에서 관련 사실을 찾아 연결해요.</Text>
            <Text style={st.quote}>메모 속 문장 · "{c.quote}"</Text>
          </>
        )}
      </View>
    </Pressable>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.appBg },
  flex: { flex: 1, minWidth: 0 },
  steps: { flexDirection: 'row', paddingHorizontal: PAD + 8, paddingVertical: 12 },
  stepItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  flexItem: { flex: 1 },
  stepLine: { flex: 1, height: 2, borderRadius: 1, backgroundColor: C.chipLine, marginHorizontal: 4, overflow: 'hidden' },
  stepLineFill: { height: 2, backgroundColor: C.accent },
  stepDot: { width: 22, height: 22, borderRadius: 11, backgroundColor: C.chipLine, alignItems: 'center', justifyContent: 'center' },
  stepDotOn: { backgroundColor: C.accent },
  stepNum: { fontSize: 11, fontWeight: '800', color: C.sub },
  stepNumOn: { color: C.white },
  stepText: { fontSize: 13, color: C.muted },
  stepTextOn: { color: C.text, fontWeight: '700' },
  body: { paddingHorizontal: PAD, paddingTop: 4, paddingBottom: 120 },
  q: { fontSize: 21, fontWeight: '800', color: C.text },
  qd: { fontSize: 13.5, color: C.sub, marginTop: 4, marginBottom: 14 },
  memo: { borderRadius: R.card, padding: 16 },
  memoTag: { alignSelf: 'flex-start', backgroundColor: C.card, borderRadius: 6, paddingHorizontal: 7, paddingVertical: 1 },
  memoTagText: { fontSize: 11, fontWeight: '700', color: C.text },
  memoTitle: { fontSize: 16, fontWeight: '800', color: C.text, marginTop: 6 },
  memoBody: { fontSize: 13.5, lineHeight: 21, color: C.body, marginTop: 4 },
  scanRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 16, marginBottom: 10 },
  scan: { flex: 1, fontSize: 13.5, color: C.sub },
  skel: { height: 110, borderRadius: R.card, backgroundColor: C.skeleton, marginBottom: 10 },
  found: { fontSize: 16, fontWeight: '800', color: C.text, marginTop: 18, marginBottom: 10 },
  foundNum: { color: C.accentDeep },
  cand: { flexDirection: 'row', gap: 12, backgroundColor: C.card, borderRadius: R.card, padding: 14, marginBottom: 10, borderWidth: 1.5, borderColor: C.accent },
  candOff: { borderColor: C.card, opacity: 0.6 },
  cb: { marginTop: 2 },
  chp: { alignSelf: 'flex-start', borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 },
  chpText: { fontSize: 11, fontWeight: '800' },
  candTitle: { fontSize: 15, fontWeight: '800', color: C.text, marginTop: 6 },
  candSub: { fontSize: 12.5, color: C.sub, marginTop: 6 },
  quote: { fontSize: 12.5, color: C.body, marginTop: 6, backgroundColor: C.appBg, borderRadius: 8, padding: 8 },
  tb: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 8 },
  tbCol: { minWidth: 80 },
  tbK: { fontSize: 11.5, color: C.muted },
  tbV: { fontSize: 13, fontWeight: '700', color: C.text, marginTop: 2 },
  ainfo: { fontSize: 12, lineHeight: 18, color: C.muted, marginTop: 6 },
  none: { marginTop: 16 },
  noneTitle: { fontSize: 16, fontWeight: '800', color: C.text, textAlign: 'center' },
  noneText: { fontSize: 13.5, lineHeight: 21, color: C.sub, textAlign: 'center', marginTop: 6 },
  exBox: { backgroundColor: C.card, borderRadius: R.card, padding: 14, marginTop: 14, gap: 6 },
  exHead: { fontSize: 14, fontWeight: '800', color: C.text },
  ex: { fontSize: 13, color: C.body },
  bar: { position: 'absolute', left: 0, right: 0, bottom: 0, flexDirection: 'row', gap: 8, padding: PAD, paddingBottom: 28, backgroundColor: C.appBg },
  btnHit: { flex: 1 },
  btnHitGray: { flex: 0, minWidth: 110 },
  btn: { height: 52, borderRadius: R.btn, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 10 },
  btnGray: { backgroundColor: C.chipLine },
  btnGrayText: { fontSize: 15, fontWeight: '700', color: C.text },
  btnMain: { backgroundColor: C.dark },
  btnMainText: { fontSize: 15, fontWeight: '800', color: C.white },
  btnDis: { opacity: 0.4 },
  done: { alignItems: 'center', paddingTop: 80, paddingHorizontal: PAD },
  doneCk: { width: 76, height: 76, borderRadius: 38, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center' },
  doneTitle: { fontSize: 21, fontWeight: '800', color: C.text, marginTop: 18 },
  doneText: { fontSize: 14, lineHeight: 22, color: C.sub, textAlign: 'center', marginTop: 8 },
});
