import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { PaperBox } from '@/ui/shared/PaperBox';
import { Sheet } from '@/ui/shared/Sheet';
import { StockLogo } from '@/ui/shared/StockLogo';
import { appColor } from '@/ui/theme';
import type { AppFirstHomeProps, FirstMemoSummary, FirstStockSheetProps } from '../FirstHome.types';

/**
 * 앱 첫 홈 = 원본 app/start.html #scr (고른 종목만 있는 빈 홈).
 *  빈 상태: 인사 카드(.hero · 진행 막대 3칸) · 내 종목(.w · .sr · [+ 메모]) · 업데이트(빈 칸 점선)
 *  저장 후: 지켜보기 카드(.watch) · 내 메모(.mnote) · 진행 막대 · 내 종목 · [체험판 홈으로 이어서 보기 →] · 안내
 *  종목 시트(.sheet · .pk 라디오 · [이 종목에 메모 쓰기])
 * 색: start.html :root — --a #8569E3 · --aa #6A42AB · --ink3 #8A8F98 (login.html 과 다름)
 */
const C = { a: appColor.accent, aa: '#6A42AB', aSoft: '#EEE9FB', ink: '#16171A', ink2: '#575B63', ink3: '#8A8F98' };
const Y = { bg: '#FCEAAA', accent: '#EFBF2A' };

export function AppFirstHome(p: AppFirstHomeProps) {
  const m = p.memo;
  const first = () => {
    if (p.stocks.length) p.onOpenPicker();
    else p.onNoStocks();
  };
  return (
    <>
      {m ? (
        <>
          <Rv i={0}><Watch memo={m} /></Rv>
          <Rv i={1}><MemoNote memo={m} /></Rv>
          <Rv i={2}><Steps done={[true, true, m.ai]} /></Rv>
        </>
      ) : (
        <Rv i={0}>
          <Hero>
            <Text style={st.hg}>반가워요, {p.user_name}님</Text>
            <Text keepAll style={st.ht}>첫 메모를 남겨 보세요</Text>
            <Text keepAll style={st.hp}>{'왜 이 종목을 골랐는지, 무엇을 확인하고 싶은지\n한두 줄이면 충분해요.'}</Text>
            <Pressable onPress={first} style={({ pressed }) => [st.cta2, pressed && { transform: [{ scale: 0.95 }] }]} accessibilityRole="button">
              <Text style={st.cta2T}>첫 메모 쓰기</Text>
              <Svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth={2.4}><Path d="M9 6l6 6-6 6" /></Svg>
            </Pressable>
            <StepBar done={[true, false, false]} />
            <View style={st.stx}><Text style={[st.stxT, st.stxB]}>① 종목 고르기 ✓</Text><Text style={st.stxT}>② 첫 메모</Text><Text style={st.stxT}>③ AI 연결</Text></View>
          </Hero>
        </Rv>
      )}
      <Rv i={m ? 3 : 2}>
        <View style={st.w}>
          <View style={st.wh}><View style={st.whIc}><BagIcon /></View><Text style={st.whT}>내 종목</Text></View>
          {p.stocks.length ? null : <View style={st.emp}><View style={st.bx}><Text keepAll style={st.bxT}>{'고른 종목이 없어요\n내 종목 탭에서 종목을 추가해 보세요'}</Text></View></View>}
          {p.stocks.map((s, i) => {
            const has = s.memo_count > 0;
            return (
              <View key={s.stock_code} style={[st.sr, i > 0 && st.srLine]}>
                <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={36} radius={10} fontSize={14} variant="app" />
                <View style={st.flex}>
                  <Text style={st.srB} numberOfLines={1}>{s.name}</Text>
                  <Text style={st.srS}>{s.status === 'holding' ? '보유' : '관심'} · 메모 {s.memo_count}{s.ai_count ? ` · AI 연결 ${s.ai_count}` : ''}</Text>
                </View>
                {has ? null : (
                  <Pressable onPress={() => p.onPickStock(s)} style={({ pressed }) => [st.addm, pressed && { opacity: 0.8 }]} accessibilityRole="button" accessibilityLabel={`${s.name} 메모 쓰기`}>
                    <Text style={st.addmT}>+ 메모</Text>
                  </Pressable>
                )}
              </View>
            );
          })}
        </View>
      </Rv>
      {m ? (
        <Rv i={4}>
          <View style={st.next}>
            <Pressable onPress={p.onContinue} style={({ pressed }) => [st.nextB, pressed && { transform: [{ scale: 0.97 }] }]} accessibilityRole="button"><Text style={st.nextT}>체험판 홈으로 이어서 보기 →</Text></Pressable>
          </View>
          <Text style={st.disc}>여기부터는 예시 데이터가 채워진 홈이에요</Text>
        </Rv>
      ) : (
        <Rv i={3}>
          <View style={st.w}>
            <View style={st.wh}><View style={st.whIc}><RefreshIcon /></View><Text style={st.whT}>업데이트</Text></View>
            <View style={st.emp}><View style={st.bx}><Text keepAll style={st.bxT}>{'메모에 AI 연결을 켜면\n관련 공시·뉴스·종가 변화가 여기에 모여요'}</Text></View></View>
          </View>
        </Rv>
      )}
      <FirstStockSheet
        open={p.picker_open}
        stocks={p.stocks}
        selected={p.stocks[0]?.stock_code ?? null}
        button="이 종목에 메모 쓰기"
        onClose={p.onClosePicker}
        onConfirm={p.onPickStock}
      />
    </>
  );
}

/* .rv: 아래에서 12 올라오며 나타남 .45s · 70ms 간격 */
function Rv({ i, children }: { i: number; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: 1, duration: 450 * k, delay: i * 70 * k, easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [i, k, v]);
  return <Animated.View style={{ opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }) }] }}>{children}</Animated.View>;
}

/* .hero: linear-gradient(165deg, #EFF0F3, #E3E5EA) · 라운드 22 · 안쪽 20 18 18 */
function Hero({ children }: { children: React.ReactNode }) {
  /* 크기를 재서 그라데이션을 깐다 (100% 로 주면 첫 그림에서 폭이 덜 잡힘) */
  const [box, setBox] = useState({ w: 0, h: 0 });
  return (
    <View style={st.hero} onLayout={(e) => setBox({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })}>
      <Svg style={StyleSheet.absoluteFill} width={box.w} height={box.h}>
        <Defs>
          <LinearGradient id="fhHero" x1="0.37" y1="0" x2="0.63" y2="1">
            <Stop offset="0" stopColor="#EFF0F3" />
            <Stop offset="1" stopColor="#E3E5EA" />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width={box.w} height={box.h} fill="url(#fhHero)" />
      </Svg>
      {children}
    </View>
  );
}

/* .steps: 3칸 · 높이 4 · 간격 6 · 켜진 칸은 왼쪽부터 자라남 .6s */
function StepBar({ done }: { done: boolean[] }) {
  return <View style={st.steps}>{done.map((on, i) => <StepSeg key={i} on={on} />)}</View>;
}
function StepSeg({ on }: { on: boolean }) {
  const k = useMotionK();
  const [w, setW] = useState(0);
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!on || !w) return;
    const a = Animated.timing(v, { toValue: 1, duration: 600 * k, easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [on, w, k, v]);
  return (
    <View style={st.seg} onLayout={(e) => setW(e.nativeEvent.layout.width)}>
      {on && w ? <Animated.View style={[st.segOn, { width: w, transform: [{ translateX: v.interpolate({ inputRange: [0, 1], outputRange: [-w / 2, 0] }) }, { scaleX: v }] }]} /> : null}
    </View>
  );
}

function Steps({ done }: { done: [boolean, boolean, boolean] }) {
  return (
    <Hero>
      <StepBar done={done} />
      <View style={st.stx}>
        <Text style={[st.stxT, st.stxB]}>① 종목 ✓</Text>
        <Text style={[st.stxT, st.stxB]}>② 첫 메모 ✓</Text>
        <Text style={[st.stxT, done[2] && st.stxB]}>{done[2] ? '③ AI 연결 ✓' : '③ AI 연결'}</Text>
      </View>
    </Hero>
  );
}

/* .watch: AI 연결이면 #FBF8FF · 선 #EEE7FB · 플러그 원 52 (퍼지는 링) · 칩 / 아니면 흰 바탕 · 선 #ECEDF1 */
function Watch({ memo }: { memo: FirstMemoSummary }) {
  return (
    <View style={[st.watch, !memo.ai && st.watchPlain]}>
      {memo.ai ? <Plug /> : null}
      <Text style={st.watchB}>{memo.ai ? 'AI가 이 메모를 지켜보고 있어요' : '첫 메모를 남겼어요'}</Text>
      <Text keepAll style={st.watchP}>
        {memo.ai ? '관련 소식이 생기면 업데이트 탭과 알림함에 알려 드려요.\n보통 공시·뉴스가 쌓이는 데 하루 이틀 걸려요.' : 'AI 연결은 메모를 열어 언제든 켤 수 있어요.\n켜면 관련 공시·뉴스·종가 변화를 찾아 드려요.'}
      </Text>
      {memo.ai && memo.chips.length ? <View style={st.chips}>{memo.chips.map((c) => <View key={c} style={st.chip}><Text style={st.chipT}>{c}</Text></View>)}</View> : null}
    </View>
  );
}

function Plug() {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.loop(Animated.timing(v, { toValue: 1, duration: 1800 * k, easing: Easing.out(Easing.ease), useNativeDriver: NATIVE }));
    a.start();
    return () => a.stop();
  }, [k, v]);
  return (
    <View style={st.pl}>
      <Animated.View pointerEvents="none" style={[st.ring, { opacity: v.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }), transform: [{ scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.8, 1.35] }) }] }]} />
      <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
        <Path d="M9 3v4M15 3v4" stroke="#6A42AB" strokeWidth={2} strokeLinecap="round" />
        <Path d="M6.5 7h11v4a5.5 5.5 0 0 1-11 0z" fill="#8569E3" />
        <Path d="M12 16.5V21" stroke="#6A42AB" strokeWidth={2} strokeLinecap="round" />
      </Svg>
    </View>
  );
}

/* .mnote: 라운드 14 14 0 14 · 오른쪽 아래 18 접힘 · 안쪽 12 14 16 · 태그 11 700 흰 바탕 · 제목 14.5 · 본문 13 줄 1.6 #2E2E38 */
function MemoNote({ memo }: { memo: FirstMemoSummary }) {
  return (
    <PaperBox bg={Y.bg} accent={Y.accent} radius={14} cut={18} style={st.mnote}>
      <View style={st.tg}><Text style={st.tgT}>{memo.stock_name} · 내 메모</Text></View>
      <Text style={st.mnB}>{memo.title}</Text>
      {memo.body ? <Text style={st.mnP}>{memo.body}</Text> : null}
    </PaperBox>
  );
}

/* .sheet (start.html): 제목 18 · 설명 13 · .pk 줄 (로고 36 · 이름 + 보유/관심 태그 · 메모 수 · 라디오 22) · [.bt 52 #16171A] */
export function FirstStockSheet({ open, stocks, selected, button, onClose, onConfirm }: FirstStockSheetProps) {
  const [cur, setCur] = useState(selected);
  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) setCur(selected);
  }
  const pick = stocks.find((s) => s.stock_code === cur) ?? stocks[0];
  return (
    <Sheet open={open} onClose={onClose} label="메모를 남길 종목 고르기">
      <Text style={st.h4}>어느 종목에 남길까요?</Text>
      <Text style={st.sd}>메모는 종목별 메모 보드에 저장돼요</Text>
      <ScrollView style={{ maxHeight: 360 }}>
        {stocks.map((s) => {
          const on = s.stock_code === pick?.stock_code;
          return (
            <Pressable key={s.stock_code} onPress={() => setCur(s.stock_code)} style={st.pk} accessibilityRole="radio" accessibilityState={{ checked: on }} accessibilityLabel={`${s.name} ${s.status === 'holding' ? '보유' : '관심'}`}>
              <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={36} radius={10} fontSize={14} variant="app" />
              <View style={st.flex}>
                <View style={st.pkRow}>
                  <Text style={st.pkB} numberOfLines={1}>{s.name}</Text>
                  <View style={[st.tg2, s.status === 'holding' && st.tg2H]}><Text style={[st.tg2T, s.status === 'holding' && st.tg2HT]}>{s.status === 'holding' ? '보유' : '관심'}</Text></View>
                </View>
                <Text style={st.pkS}>메모 {s.memo_count}</Text>
              </View>
              <View style={[st.rd, on && st.rdOn]}>{on ? <View style={st.rdI} /> : null}</View>
            </Pressable>
          );
        })}
      </ScrollView>
      <Pressable onPress={() => pick && onConfirm(pick)} style={({ pressed }) => [st.bt, pressed && { transform: [{ scale: 0.97 }] }]} accessibilityRole="button"><Text style={st.btT}>{button}</Text></Pressable>
    </Sheet>
  );
}

function BagIcon() {
  return <Svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="#6A42AB" strokeWidth={2}><Rect x={3} y={7} width={18} height={13} rx={2.5} /><Path d="M9 7V5h6v2" /></Svg>;
}
function RefreshIcon() {
  return <Svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="#6A42AB" strokeWidth={2} strokeLinecap="round"><Path d="M20 12a8 8 0 0 1-14 5.3M4 12a8 8 0 0 1 14-5.3M18 3v4h-4M6 21v-4h4" /></Svg>;
}

const st = StyleSheet.create({
  flex: { flex: 1, minWidth: 0 },
  hero: { borderRadius: 22, overflow: 'hidden', paddingTop: 20, paddingHorizontal: 18, paddingBottom: 18, backgroundColor: '#E9EAEE' },
  hg: { fontSize: 13, lineHeight: 19, color: C.ink2 },
  ht: { fontSize: 21, lineHeight: 29.4, fontWeight: '800', color: C.ink, marginTop: 4, marginBottom: 6 },
  hp: { fontSize: 13.5, lineHeight: 21.6, color: C.ink2, marginBottom: 14 },
  cta2: { alignSelf: 'flex-start', minHeight: 40, paddingHorizontal: 16, borderRadius: 20, backgroundColor: C.ink, flexDirection: 'row', alignItems: 'center', gap: 6 },
  cta2T: { fontSize: 14, lineHeight: 20, fontWeight: '700', color: '#FFFFFF' },
  steps: { flexDirection: 'row', gap: 6, marginTop: 16 },
  seg: { flex: 1, height: 4, borderRadius: 2, backgroundColor: '#D5D7DD', overflow: 'hidden' },
  segOn: { position: 'absolute', left: 0, top: 0, bottom: 0, backgroundColor: C.a },
  stx: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 6 },
  stxT: { fontSize: 11.5, lineHeight: 17, color: C.ink3 },
  stxB: { fontWeight: '700', color: C.aa },
  w: { backgroundColor: '#FFFFFF', borderRadius: 22 },
  wh: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingTop: 16, paddingHorizontal: 18, paddingBottom: 6 },
  whIc: { width: 30, height: 30, borderRadius: 10, backgroundColor: C.aSoft, alignItems: 'center', justifyContent: 'center' },
  whT: { fontSize: 16, lineHeight: 23, fontWeight: '800', color: C.ink },
  sr: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, paddingHorizontal: 18 },
  srLine: { borderTopWidth: 1, borderTopColor: '#F0F1F4' },
  srB: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: C.ink },
  srS: { fontSize: 12.5, lineHeight: 18, color: C.ink3 },
  addm: { minHeight: 32, paddingHorizontal: 12, borderRadius: 16, backgroundColor: C.aSoft, alignItems: 'center', justifyContent: 'center' },
  addmT: { fontSize: 13, lineHeight: 19, fontWeight: '700', color: C.aa },
  emp: { paddingTop: 6, paddingHorizontal: 18, paddingBottom: 18 },
  bx: { borderWidth: 1.5, borderStyle: 'dashed', borderColor: '#D9DBE1', borderRadius: 16, padding: 16 },
  bxT: { fontSize: 13.5, lineHeight: 21.6, color: C.ink3, textAlign: 'center' },
  watch: { alignItems: 'center', paddingTop: 22, paddingHorizontal: 16, paddingBottom: 18, backgroundColor: '#FBF8FF', borderRadius: 22, borderWidth: 1, borderColor: '#EEE7FB' },
  watchPlain: { backgroundColor: '#FFFFFF', borderColor: '#ECEDF1' },
  pl: { width: 52, height: 52, borderRadius: 26, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center', marginBottom: 12, shadowColor: '#6A42AB', shadowOpacity: 0.5, shadowRadius: 8, shadowOffset: { width: 0, height: 6 }, elevation: 3 },
  ring: { position: 'absolute', left: -6, top: -6, right: -6, bottom: -6, borderRadius: 32, borderWidth: 2, borderColor: '#CDBBFF' },
  watchB: { fontSize: 17, lineHeight: 24, fontWeight: '800', color: C.ink, textAlign: 'center' },
  watchP: { fontSize: 13, lineHeight: 20.8, color: '#6B7079', textAlign: 'center', marginTop: 6, marginBottom: 12 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, justifyContent: 'center' },
  chip: { minHeight: 30, paddingHorizontal: 12, borderRadius: 15, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E4DCF7', justifyContent: 'center' },
  chipT: { fontSize: 12.5, lineHeight: 18, fontWeight: '700', color: C.aa },
  /* 홈 목록 간격 14 기준: 원본 .watch 아래 14 → 위 0 · .mnote 아래 12 → -2 */
  mnote: { paddingTop: 12, paddingHorizontal: 14, paddingBottom: 16, marginBottom: -2 },
  tg: { alignSelf: 'flex-start', backgroundColor: '#FFFFFF', borderRadius: 6, paddingVertical: 1, paddingHorizontal: 7 },
  tgT: { fontSize: 11, lineHeight: 16, fontWeight: '700', color: C.ink },
  mnB: { fontSize: 14.5, lineHeight: 21, fontWeight: '700', color: C.ink, marginTop: 6 },
  mnP: { fontSize: 13, lineHeight: 20.8, color: '#2E2E38', marginTop: 2 },
  /* .w 아래 14 와 .next 위 4 는 겹침(margin collapse) → 목록 간격 14 그대로 */
  next: { alignItems: 'center' },
  nextB: { minHeight: 44, paddingHorizontal: 18, borderRadius: 14, backgroundColor: C.a, alignItems: 'center', justifyContent: 'center' },
  nextT: { fontSize: 14.5, lineHeight: 21, fontWeight: '800', color: '#FFFFFF' },
  disc: { fontSize: 12, lineHeight: 19.2, color: C.ink3, textAlign: 'center', marginTop: 12 },
  h4: { fontSize: 18, lineHeight: 26, fontWeight: '700', color: C.ink, marginHorizontal: 20, marginBottom: 2 },
  sd: { fontSize: 13, lineHeight: 19, color: C.ink3, marginHorizontal: 20, marginBottom: 10 },
  pk: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, paddingHorizontal: 20 },
  pkRow: { flexDirection: 'row', alignItems: 'center' },
  pkB: { flexShrink: 1, fontSize: 16, lineHeight: 23, fontWeight: '700', color: C.ink },
  tg2: { marginLeft: 6, borderRadius: 6, paddingVertical: 1, paddingHorizontal: 7, backgroundColor: '#F1F2F4' },
  tg2H: { backgroundColor: '#FFF1D6' },
  tg2T: { fontSize: 11.5, lineHeight: 17, fontWeight: '700', color: C.ink2 },
  tg2HT: { color: '#8A5A00' },
  pkS: { fontSize: 12.5, lineHeight: 18, color: C.ink3 },
  rd: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: '#C5C8CF', alignItems: 'center', justifyContent: 'center' },
  rdOn: { borderColor: C.a },
  rdI: { width: 12, height: 12, borderRadius: 6, backgroundColor: C.a },
  bt: { marginTop: 12, marginHorizontal: 16, minHeight: 52, borderRadius: 14, backgroundColor: '#16171A', alignItems: 'center', justifyContent: 'center', paddingVertical: 14 },
  btT: { fontSize: 15.5, lineHeight: 22, fontWeight: '700', color: '#FFFFFF' },
});
