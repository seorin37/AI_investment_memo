import React, { useEffect, useState } from 'react';
import { Animated, BackHandler, Easing, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { AppPlug } from '@/ui/icons/BoardGlyphs';
import { CloseX, DoneCheck, RevIcon, SearchGlass } from '@/ui/icons/MemoGlyphs';
import { Skeleton } from '@/ui/motion/Skeleton';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { PaperBox } from '@/ui/shared/PaperBox';
import { appColor, curve, ft } from '@/ui/theme';
import type { AiLinkProps, AiTrackItem } from '../MemoDetail.types';
import { won } from '../memoTimeline';
import { CHIP } from './MemoFeed';
import { usePaper } from '@/ui/shared/Dark';

/**
 * 앱 AI 연결 (원본 memo.html 12 · 12.1 · #aif: 아래에서 올라오는 회색 #F3F4F6 전체 화면)
 * 머리 56: × + 'AI 연결' 18px 700 · 단계 ① 메모 저장 ② 항목 확인 ③ 연결 시작 (동그라미 22 · 선 2)
 * 분석 중: 질문 21px 800 + 메모지 + '항목을 찾고 있어요' 도는 고리 + 뼈대 2개
 * 항목 있음 (8. 읽기 전용 — 서버가 정함): 찾은 항목 카드 (테두리 1.5 #16171A · 라운드 18) + 안내 2개 · [나중에] [AI 연결 시작]
 * 항목 없음 (12.1): 돋보기 카드 + 적는 예시 · [메모 수정] [메모로 돌아가기] / 분석 실패: 같은 모양 안내 · [다시 시도] [일반 메모로 두기]
 * 연결 시작을 누르면 체크가 튀어나오고 1.6초 뒤 onConfirm.
 */
export function AppAiLink({ stockName, memo, state, items, fromNew, onConfirm, onCancel, onEditMemo, onRetry }: AiLinkProps) {
  const paper = usePaper();
  const insets = useSafeAreaInsets();
  const [step, setStep] = useState(fromNew ? 1 : 2);
  const [done, setDone] = useState(false);
  const pc = paper[memo.color];
  useEffect(() => {
    if (!fromNew) return;
    const t = setTimeout(() => setStep(2), 600);
    return () => clearTimeout(t);
  }, [fromNew]);
  useEffect(() => {
    if (!done) return;
    const t = setTimeout(onConfirm, 1600);
    return () => clearTimeout(t);
  }, [done, onConfirm]);
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      onCancel();
      return true;
    });
    return () => sub.remove();
  }, [onCancel]);

  const note = (
    <PaperBox bg={pc.bg} accent={pc.accent} radius={14} cut={18} style={st.mnote}>
      <View style={st.mchip}>
        <Text style={st.mchipT}>{stockName} · 내 메모</Text>
      </View>
      <Text style={st.mnoteB}>{memo.title}</Text>
      {memo.body ? <Text style={st.mnoteP}>{memo.body}</Text> : null}
    </PaperBox>
  );

  let body: React.ReactNode;
  let bar: React.ReactNode = null;
  if (done) {
    body = <Done />;
  } else if (state === 'loading') {
    body = (
      <>
        <Text style={st.aq}>무엇을 계속 확인할까요?</Text>
        {/* ④ 결정: 원본 '선택한 항목만 연결돼요' → 항목 화면과 같은 문구 (항목은 읽기 전용) */}
        <Text style={st.ad}>메모에서 찾은 항목이에요. 항목을 골라 받을 수는 없고, 연결하면 이 항목 모두와 관련된 소식을 모아 드려요.</Text>
        {note}
        <View style={st.scan}>
          <Spinner />
          <Text style={st.scanT}>메모에서 계속 확인할 항목을 찾고 있어요</Text>
        </View>
        <Skeleton radius={18} style={st.sk} />
        <Skeleton radius={18} style={st.sk} />
      </>
    );
  } else if (state === 'items') {
    body = (
      <>
        <Text style={st.aq}>AI가 이 메모에서 확인할 것</Text>
        <Text style={st.ad}>메모에서 찾은 항목이에요. 항목을 골라 받을 수는 없고, 연결하면 이 항목 모두와 관련된 소식을 모아 드려요.</Text>
        {note}
        <Text style={st.found}>
          찾은 항목 <Text style={{ color: appColor.deepPurple }}>{items.length}</Text>
        </Text>
        {items.map((x, i) => (
          <Pop key={i} i={i}>
            <TrackCard x={x} />
          </Pop>
        ))}
        <View style={st.wait}>
          <Text style={st.waitT}>⏳</Text>
          <Text style={[st.waitT, st.flex]}>소식은 바로 오지 않을 수 있어요. 관련 공시·뉴스·종가 변화가 새로 생길 때만 모아 드려요.</Text>
        </View>
        <Text style={st.ainfo}>✦ AI는 메모를 수정하지 않아요. 관련된 사실과 출처만 연결해요.</Text>
      </>
    );
    bar = (
      <>
        <Btn gray label="나중에" onPress={onCancel} />
        <Btn
          label="AI 연결 시작"
          icon={<AppPlug size={16} color="#FFFFFF" />}
          onPress={() => {
            setStep(3);
            setDone(true);
          }}
        />
      </>
    );
  } else {
    const fail = state === 'error';
    body = (
      <>
        <Pop i={0}>
          <View style={st.emp}>
            <View style={st.ic2}>
              <SearchGlass />
            </View>
            <Text style={st.empB}>{fail ? '메모를 확인하지 못했어요' : '추적할 항목을 찾지 못했어요'}</Text>
            <Text style={st.empP}>{fail ? '잠시 뒤 다시 시도해 주세요.\n메모는 일반 메모로 그대로 저장돼요.' : '메모는 일반 메모로 그대로 저장돼요.\n확인할 사실이나 가격 조건을 구체적으로 적고\n다시 확인해 보세요.'}</Text>
          </View>
        </Pop>
        {!fail ? (
          <Pop i={1}>
            <View style={st.ecd}>
              <Text style={st.ecdH}>이렇게 적으면 찾을 수 있어요</Text>
              <Example kind="fact" text={'"다음 정기보고서에서 HBM 매출 확인하기"'} />
              <Example kind="price" text={'"20만원 아래로 내려오면 다시 보기"'} />
            </View>
          </Pop>
        ) : null}
      </>
    );
    bar = fail ? (
      <>
        <Btn label="다시 시도" onPress={() => onRetry?.()} />
        <Btn gray wide label="일반 메모로 두기" onPress={onCancel} />
      </>
    ) : (
      <>
        <Btn label="메모 수정" icon={<RevIcon first={false} color="#FFFFFF" />} onPress={() => onEditMemo?.()} />
        <Btn gray wide label="메모로 돌아가기" onPress={onCancel} />
      </>
    );
  }

  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <View style={st.oh}>
        <Pressable onPress={onCancel} accessibilityRole="button" accessibilityLabel="닫기" style={st.iconbtn}>
          <CloseX />
        </Pressable>
        <Text style={st.ohT}>AI 연결</Text>
      </View>
      <Steps step={step} />
      <ScrollView style={st.flex} contentContainerStyle={[st.ob, { paddingBottom: 120 + insets.bottom }]} showsVerticalScrollIndicator={false}>
        {body}
      </ScrollView>
      {bar ? <View style={[st.obar, { paddingBottom: 18 + insets.bottom }]}>{bar}</View> : null}
    </View>
  );
}

/** 단계 (원본 .stp: 동그라미 22 #E5E7EB → 켜면 #8569E3 · 지난 단계는 ✓ · 선은 .5s 왼쪽부터 채움) */
function Steps({ step }: { step: number }) {
  const S = ['메모 저장', '항목 확인', '연결 시작'];
  return (
    <View style={st.stp}>
      {S.map((label, i) => {
        const n = i + 1;
        const on = n <= step;
        return (
          <React.Fragment key={label}>
            {i > 0 ? <StepLine on={i < step} /> : null}
            <View style={st.s}>
              <View style={[st.d, on && st.dOn]}>
                <Text style={[st.dT, on && { color: '#FFFFFF' }]}>{n < step ? '✓' : n}</Text>
              </View>
              <Text style={[st.sT, on && st.sTOn]}>{label}</Text>
            </View>
          </React.Fragment>
        );
      })}
    </View>
  );
}
function StepLine({ on }: { on: boolean }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(on ? 1 : 0));
  const [w, setW] = useState(0);
  useEffect(() => {
    const a = Animated.timing(v, { toValue: on ? 1 : 0, duration: 500 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [on, v, k]);
  return (
    <View style={st.ln2} onLayout={(e) => setW(e.nativeEvent.layout.width)}>
      <Animated.View style={[st.ln2i, { width: v.interpolate({ inputRange: [0, 1], outputRange: [0, w] }) }]} />
    </View>
  );
}

/** 찾은 항목 카드 (원본 .ti.ro: 테두리 1.5 #16171A · 라운드 18 · 안쪽 14 · 아래 10) */
function TrackCard({ x }: { x: AiTrackItem }) {
  const c = CHIP[x.kind];
  return (
    <View style={st.ti}>
      <View style={[st.chp, { backgroundColor: c.bg }]}>
        <Text style={[st.chpT, { color: c.ink }]}>{c.label}</Text>
      </View>
      <Text style={st.tiB}>{x.label}</Text>
      {x.kind === 'price' ? (
        <>
          <View style={st.tb}>
            <Kv k="판정 기준" v="전일 종가" />
            <Kv k="조건" v={`${won(x.price)}원 ${x.direction}`} />
            <Kv k="확인 시점" v="매 거래일 장 마감 후" />
          </View>
          <Text style={[st.small, { marginTop: 6 }]}>ⓘ 실시간 알림이 아닌 종가 기준이에요.</Text>
        </>
      ) : x.kind === 'ask' ? (
        <Text style={st.small}>다음 날 아침, 공시·뉴스·재무 자료로 한 번 답해 드려요.</Text>
      ) : (
        <>
          <Text style={st.small}>정기보고서와 뉴스에서 관련 소식을 찾아 연결해요.</Text>
          <Text style={st.mq}>메모 속 문장 · &quot;{x.quote}&quot;</Text>
        </>
      )}
    </View>
  );
}
function Kv({ k, v }: { k: string; v: string }) {
  return (
    <View style={st.kv}>
      <Text style={st.kvK}>{k}</Text>
      <Text style={st.kvV}>{v}</Text>
    </View>
  );
}
function Example({ kind, text }: { kind: 'price' | 'fact'; text: string }) {
  const c = CHIP[kind];
  return (
    <View style={st.exm}>
      <View style={[st.exChip, { backgroundColor: c.bg }]}>
        <Text style={[st.exChipT, { color: c.ink }]}>{c.label}</Text>
      </View>
      <Text style={st.exT}>{text}</Text>
    </View>
  );
}

function Btn({ label, onPress, gray, wide, icon }: { label: string; onPress: () => void; gray?: boolean; wide?: boolean; icon?: React.ReactNode }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [st.bt, gray && (wide ? st.btGrayWide : st.btGray), pressed && st.press]}>
      {icon}
      <Text style={[st.btT, gray && { color: appColor.ink }]}>{label}</Text>
    </Pressable>
  );
}

/** 원본 .ti.pop: 아래 16 · .96 에서 튀어 올라옴 (.55s spring · 차례로 .12s) */
function Pop({ i, children }: { i: number; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: 1, duration: 550 * k, delay: i * 120 * k, easing: curve.spring, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [v, k, i]);
  return <Animated.View style={{ opacity: v.interpolate({ inputRange: [0, 0.4, 1], outputRange: [0, 1, 1] }), transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [16, 0] }) }, { scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.96, 1] }) }] }}>{children}</Animated.View>;
}

/** 원본 .scan i: 16 고리 (테두리 2.5 #D9CEF7 · 위만 #8569E3) .8s 회전 */
function Spinner() {
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.loop(Animated.timing(v, { toValue: 1, duration: 800, easing: Easing.linear, useNativeDriver: NATIVE }));
    a.start();
    return () => a.stop();
  }, [v]);
  return <Animated.View style={[st.spin, { transform: [{ rotate: v.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }] }]} />;
}

/** 연결 완료 (원본 .done2: 동그라미 76 #8569E3 이 튀어나오고 체크 · 20px 제목 · 14px 안내) */
function Done() {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: 1, duration: 550 * k, easing: curve.spring, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [v, k]);
  return (
    <View style={st.done2}>
      <Animated.View style={[st.ck, { transform: [{ scale: v }] }]}>
        <DoneCheck />
      </Animated.View>
      <Text style={st.doneB}>AI 연결을 켰어요</Text>
      <Text style={st.doneP}>{'소식은 바로 오지 않을 수 있어요.\n관련 공시·뉴스·종가 변화가 생기면\n이 메모의 AI 업데이트에 모아 드려요.'}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: appColor.bg },
  flex: { flex: 1 },
  oh: { height: 56, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 6 },
  iconbtn: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  ohT: { ...ft(18), fontWeight: '700', color: appColor.ink },
  stp: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingTop: 4, paddingHorizontal: 18, paddingBottom: 14 },
  s: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  d: { width: 22, height: 22, borderRadius: 11, backgroundColor: '#E5E7EB', alignItems: 'center', justifyContent: 'center' },
  dOn: { backgroundColor: appColor.accent },
  dT: { ...ft(11.5, 1), fontWeight: '800', color: appColor.ink3 },
  sT: { ...ft(12.5), color: appColor.ink3 },
  sTOn: { color: appColor.ink, fontWeight: '700' },
  ln2: { flex: 1, height: 2, borderRadius: 1, backgroundColor: '#E5E7EB', overflow: 'hidden' },
  ln2i: { position: 'absolute', left: 0, top: 0, bottom: 0, backgroundColor: appColor.accent },
  ob: { paddingTop: 4, paddingHorizontal: 16 },
  aq: { ...ft(21), fontWeight: '800', color: appColor.ink, marginTop: 2, marginHorizontal: 2, marginBottom: 4 },
  ad: { ...ft(13), color: appColor.ink2, marginHorizontal: 2, marginBottom: 12 },
  mnote: { paddingTop: 12, paddingHorizontal: 14, paddingBottom: 16 },
  mchip: { alignSelf: 'flex-start', backgroundColor: '#FFFFFF', borderRadius: 6, paddingHorizontal: 7, paddingVertical: 1 },
  mchipT: { ...ft(11), fontWeight: '700', color: appColor.ink },
  mnoteB: { ...ft(14.5), fontWeight: '700', color: appColor.ink, marginTop: 6 },
  mnoteP: { ...ft(12.5, 1.5), color: '#2E2E38', marginTop: 2 },
  scan: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 16, marginHorizontal: 2, marginBottom: 10 },
  scanT: { ...ft(13.5), fontWeight: '600', color: appColor.deepPurple },
  spin: { width: 16, height: 16, borderRadius: 8, borderWidth: 2.5, borderColor: '#D9CEF7', borderTopColor: appColor.accent },
  sk: { height: 110, marginBottom: 10 },
  found: { ...ft(16), fontWeight: '800', color: appColor.ink, marginTop: 18, marginHorizontal: 2, marginBottom: 10 },
  ti: { borderWidth: 1.5, borderColor: appColor.ink, borderRadius: 18, padding: 14, marginBottom: 10, backgroundColor: '#FFFFFF' },
  chp: { alignSelf: 'flex-start', borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 },
  chpT: { ...ft(11.5), fontWeight: '800' },
  tiB: { ...ft(16.5), fontWeight: '700', color: appColor.ink, marginTop: 10, marginBottom: 4 },
  small: { ...ft(12.5, 1.6), color: appColor.ink2 },
  mq: { backgroundColor: '#F5F6F8', borderRadius: 10, paddingVertical: 8, paddingHorizontal: 12, marginTop: 8, ...ft(12.5), color: appColor.ink2, borderLeftWidth: 3, borderLeftColor: appColor.accent, overflow: 'hidden' },
  tb: { backgroundColor: '#F5F6F8', borderRadius: 10, paddingVertical: 4, paddingHorizontal: 12, marginTop: 8 },
  kv: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6 },
  kvK: { ...ft(13), color: appColor.ink2 },
  kvV: { ...ft(13), fontWeight: '700', color: appColor.ink },
  wait: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', backgroundColor: '#FFF7E6', borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12, marginTop: 8 },
  waitT: { ...ft(12.5, 1.6), color: '#8A5D00' },
  ainfo: { backgroundColor: '#F3EFFD', borderRadius: 14, paddingVertical: 12, paddingHorizontal: 14, ...ft(12.5, 1.6), color: '#4B2D93', marginTop: 6, overflow: 'hidden' },
  emp: { backgroundColor: '#FFFFFF', borderRadius: 20, paddingVertical: 26, paddingHorizontal: 18, alignItems: 'center', marginTop: 4, marginBottom: 12 },
  ic2: { width: 52, height: 52, borderRadius: 26, backgroundColor: '#F1F2F5', alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  empB: { ...ft(17), fontWeight: '700', color: appColor.ink, marginBottom: 6, textAlign: 'center' },
  empP: { ...ft(13.5, 1.6), color: appColor.ink2, textAlign: 'center' },
  ecd: { backgroundColor: '#FFFFFF', borderRadius: 20, padding: 16, marginBottom: 12 },
  ecdH: { ...ft(15.5), fontWeight: '700', color: appColor.ink, marginBottom: 8 },
  exm: { backgroundColor: '#F5F6F8', borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12, marginTop: 8 },
  exChip: { alignSelf: 'flex-start', borderRadius: 5, paddingHorizontal: 6, paddingVertical: 1, marginBottom: 4 },
  exChipT: { ...ft(11), fontWeight: '800' },
  exT: { ...ft(13.5), color: appColor.ink },
  obar: { position: 'absolute', left: 0, right: 0, bottom: 0, flexDirection: 'row', gap: 8, paddingTop: 12, paddingHorizontal: 16, backgroundColor: '#FFFFFF', borderTopWidth: 1, borderTopColor: appColor.line },
  bt: { flex: 1, minHeight: 52, borderRadius: 14, backgroundColor: appColor.ink, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 14 },
  btGray: { flexGrow: 0, flexBasis: 108, backgroundColor: '#ECEDF1' },
  btGrayWide: { flexGrow: 0, flexBasis: 150, backgroundColor: '#ECEDF1' },
  press: { transform: [{ scale: 0.97 }] },
  btT: { ...ft(15.5), fontWeight: '700', color: '#FFFFFF' },
  done2: { alignItems: 'center', paddingTop: 60, paddingHorizontal: 20 },
  ck: { width: 76, height: 76, borderRadius: 38, backgroundColor: appColor.accent, alignItems: 'center', justifyContent: 'center' },
  doneB: { ...ft(20), fontWeight: '700', color: appColor.ink, marginTop: 18, marginBottom: 6 },
  doneP: { ...ft(14, 1.65), color: appColor.ink2, textAlign: 'center' },
});
