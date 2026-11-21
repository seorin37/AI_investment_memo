import React, { useEffect, useState } from 'react';
import { Animated, BackHandler, Easing, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { BackGlyph } from '@/ui/screens/auth/AuthGlyphs';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { Sheet } from '@/ui/shared/Sheet';
import { StockLogo } from '@/ui/shared/StockLogo';
import { appColor } from '@/ui/theme';
import type { OnboardingFlowProps, OnboardingStock, StockStatus } from '../Onboarding.types';

/**
 * 앱 온보딩 = 원본 app/login.html
 *  #stocks (종목 고르기 · '많이 찾는 종목' 12개 · 트레이 · 하단 버튼) · .ssheet (고른 종목 보유/관심)
 *  #setup (홈 화면 선택 카드 2장) · #done (준비됐어요)
 * 원본 최종판은 검색·분류(.srch .cats .leg)를 숨기고 아래 안내(.more5)로 대신한다 → 앱도 검색 없음.
 */
const C = { a: appColor.accent, a2: '#6A42AB', ink: '#16171A', ink2: '#575B63', ink3: '#9A9EA7', line: '#E6E8EC', sf: '#F2F2F5', bg: '#F3F4F6' };

export function AppOnboardingFlow(p: OnboardingFlowProps) {
  const insets = useSafeAreaInsets();
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (p.holding_open) p.onCloseHolding();
      else p.onBack();
      return true;
    });
    return () => sub.remove();
  }, [p]);
  if (p.step === 'setup') return <Setup top={insets.top} bottom={insets.bottom} onBack={p.onBack} onChoose={p.onChooseHome} />;
  if (p.step === 'ready') return <Ready top={insets.top} bottom={insets.bottom} onFinish={p.onFinish} />;
  return <Pick {...p} top={insets.top} bottom={insets.bottom} />;
}

/* .hd 56 · .ib 42 (왼쪽 6) · .prog margin-right 16 */
function Head({ step, onBack, onSkip }: { step: 1 | 2 | 3; onBack: () => void; onSkip?: () => void }) {
  return (
    <View style={st.hd}>
      <Pressable onPress={onBack} style={st.ib} accessibilityRole="button" accessibilityLabel="뒤로"><BackGlyph /></Pressable>
      <View style={st.prog}>{[1, 2, 3].map((n) => <View key={n} style={[st.progI, n === step && st.progOn]} />)}</View>
      {onSkip ? <Pressable onPress={onSkip} style={st.skip} accessibilityRole="button"><Text style={st.skipT}>건너뛰기</Text></Pressable> : null}
    </View>
  );
}

function Pick(p: OnboardingFlowProps & { top: number; bottom: number }) {
  const picked = p.stocks.filter((s) => p.selected[s.stock_code]);
  const n = picked.length;
  /* .g3 3열 · 간격 10 · .sgw 좌우 16 */
  const { width } = useWindowDimensions();
  /* 소수점 폭이면 합이 넘쳐 2열로 줄어듦 → 내림 */
  const cardW = Math.floor((width - 32 - 20) / 3);
  return (
    <View style={[st.white, { paddingTop: p.top }]}>
      <Head step={2} onBack={p.onBack} onSkip={p.onSkip} />
      <Text keepAll style={[st.tt, { marginTop: 2 }]}>{'어떤 종목의 메모를\n남기고 싶으세요?'}</Text>
      <Text keepAll style={[st.ts, { marginBottom: 14 }]}>여러 개 골라도 돼요. 나중에 내 종목에서 언제든 바꿀 수 있어요.</Text>
      <ScrollView style={st.flex} contentContainerStyle={st.sgw} showsVerticalScrollIndicator={false}>
        <Text style={st.sh5}>많이 찾는 종목</Text>
        <View style={st.g3}>
          {p.stocks.map((s) => <StockCard key={s.stock_code} stock={s} width={cardW} on={!!p.selected[s.stock_code]} onPress={() => p.onToggle(s.stock_code)} />)}
        </View>
        <View style={st.more5}>
          <SearchIcon />
          <Text keepAll style={st.more5T}>찾는 종목이 없나요? 시작한 뒤 <Text keepAll style={st.more5B}>내 종목 › 종목 추가</Text>에서 코스피 전체를 찾을 수 있어요</Text>
        </View>
      </ScrollView>
      <View style={[st.sfoot, { paddingBottom: Math.max(p.bottom, 30) }]}>
        {n ? (
          <Pressable onPress={p.onOpenHolding} style={st.tray} accessibilityRole="button" accessibilityLabel={`${n}개 선택 · 보유·관심 정하기`}>
            <View style={st.stack}>
              {picked.slice(-5).map((s, i) => (
                <View key={s.stock_code} style={[st.stackLo, i > 0 && { marginLeft: -10 }]}>
                  <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={28} radius={8} fontSize={12} variant="app" />
                </View>
              ))}
              {n > 5 ? <View style={[st.stackLo, { marginLeft: -10 }]}><StockLogo logo={`+${n - 5}`} bg="#E6E8EC" ink={C.ink2} size={28} radius={8} fontSize={11} variant="app" /></View> : null}
            </View>
            <Text style={st.tt2}>{n}개 선택</Text>
            <Text style={st.tr2}>보유·관심 정하기 ›</Text>
          </Pressable>
        ) : null}
        <Pressable disabled={!n} onPress={p.onContinue} style={({ pressed }) => [st.cta, !n && st.ctaDis, pressed && !!n && { transform: [{ scale: 0.97 }] }]} accessibilityRole="button">
          <Text style={st.ctaT}>{n ? `${n}개 종목으로 계속` : '종목을 골라 주세요'}</Text>
        </Pressable>
      </View>
      <HoldingSheet {...p} />
    </View>
  );
}

/* .s3 112 · 라운드 18 · 안쪽 선 1.5 --line · 고르면 2.5 --a + 보라 그림자 · .ck 22 (오른쪽 위 10) · .lo 40 · b 13.5 · small 11.5 */
function StockCard({ stock, width, on, onPress }: { stock: OnboardingStock; width: number; on: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="checkbox"
      accessibilityState={{ checked: on }}
      accessibilityLabel={`${stock.name} ${stock.stock_code}`}
      style={({ pressed }) => [st.s3, { width }, on && st.s3On, pressed && { transform: [{ scale: 0.95 }] }]}
    >
      <View style={[st.ck, on && st.ckOn]}>{on ? <CheckSvg /> : null}</View>
      <StockLogo logo={stock.logo} bg={stock.logo_bg} ink={stock.logo_ink} size={40} variant="app" />
      <Text style={st.s3B} numberOfLines={1}>{stock.name}</Text>
      <Text style={st.s3S}>{stock.stock_code}</Text>
    </Pressable>
  );
}

function CheckSvg({ size = 14 }: { size?: number }) {
  return <Svg width={size} height={size} viewBox="0 0 14 14" fill="none"><Path d="M3 7.2l2.6 2.6L11 4.6" stroke="#FFFFFF" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" /></Svg>;
}

function SearchIcon() {
  return <Svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="#8A8F98" strokeWidth={2.2} strokeLinecap="round" style={{ marginTop: 2 }}><Circle cx={11} cy={11} r={7} /><Path d="M20 20l-4-4" /></Svg>;
}

/* .ssheet: 제목 '고른 종목' 17 · 설명 13 ink3 · 줄 60 (아래 선 --line) · .seg2 보유|관심 (52×30, 흰 알약) · × 32 · [확인] */
function HoldingSheet(p: OnboardingFlowProps) {
  const picked = p.stocks.filter((s) => p.selected[s.stock_code]);
  return (
    <Sheet open={p.holding_open} onClose={p.onCloseHolding} label="고른 종목 보유 관심 설정">
      <ScrollView style={{ maxHeight: 420 }} contentContainerStyle={st.ss}>
        <Text style={st.ssH}>고른 종목</Text>
        <Text keepAll style={st.ssP}>보유 중인 종목은 ‘보유’로 바꿔 주세요. 홈과 내 종목에서 나눠 보여 줘요.</Text>
        {picked.map((s) => <StatusRow key={s.stock_code} stock={s} value={p.selected[s.stock_code]} onChange={(v) => p.onStatusChange(s.stock_code, v)} onRemove={() => p.onRemove(s.stock_code)} />)}
        <Pressable onPress={p.onCloseHolding} style={[st.cta, { marginTop: 14 }]} accessibilityRole="button"><Text style={st.ctaT}>확인</Text></Pressable>
      </ScrollView>
    </Sheet>
  );
}

function StatusRow({ stock, value, onChange, onRemove }: { stock: OnboardingStock; value: StockStatus; onChange: (v: StockStatus) => void; onRemove: () => void }) {
  const k = useMotionK();
  const holding = value === 'holding';
  const [x] = useState(() => new Animated.Value(holding ? 0 : 52));
  useEffect(() => {
    const a = Animated.timing(x, { toValue: holding ? 0 : 52, duration: 400 * k, easing: Easing.bezier(0.34, 1.45, 0.64, 1), useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [holding, k, x]);
  return (
    <View style={st.srow2}>
      <StockLogo logo={stock.logo} bg={stock.logo_bg} ink={stock.logo_ink} size={40} variant="app" />
      <Text style={st.srowB} numberOfLines={1}>{stock.name}</Text>
      {/* 원본: 칸 전체를 누르면 보유 ↔ 관심 */}
      <Pressable onPress={() => onChange(holding ? 'watching' : 'holding')} style={st.seg2} accessibilityRole="switch" accessibilityState={{ checked: holding }} accessibilityLabel={`${stock.name} 보유 관심`}>
        <Animated.View style={[st.seg2I, { transform: [{ translateX: x }] }]} />
        <Text style={[st.seg2T, holding && st.seg2On]}>보유</Text>
        <Text style={[st.seg2T, !holding && st.seg2On]}>관심</Text>
      </Pressable>
      <Pressable onPress={onRemove} style={st.rm} accessibilityRole="button" accessibilityLabel={`${stock.name} 빼기`}><Text style={st.rmT}>×</Text></Pressable>
    </View>
  );
}

/* .st.in > * : 아래에서 올라옴 .5s · 55ms 간격 */
function Up({ i, children }: { i: number; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: 1, duration: 500 * k, delay: i * 55 * k, easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [i, k, v]);
  return <Animated.View style={{ opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }) }] }}>{children}</Animated.View>;
}

function Setup({ top, bottom, onBack, onChoose }: { top: number; bottom: number; onBack: () => void; onChoose: OnboardingFlowProps['onChooseHome'] }) {
  return (
    <View style={[st.gray, { paddingTop: top }]}>
      <Head step={3} onBack={onBack} />
      <ScrollView style={st.flex} contentContainerStyle={{ paddingBottom: 20 + bottom }} showsVerticalScrollIndicator={false}>
        <Up i={0}><Text keepAll style={[st.tt, { marginTop: 0 }]}>{'나에게 맞는 홈 화면을\n선택해 주세요'}</Text></Up>
        <Up i={1}><Text keepAll style={[st.ts, { marginBottom: 16 }]}>추천 템플릿을 바로 적용하거나, 원하는 정보로 직접 구성할 수 있어요.</Text></Up>
        <Up i={2}>
          <HomeCard rec icon={<GridIcon />} title="기본 템플릿 적용" desc="시장 흐름과 내 종목 소식을 한눈에 보는 추천 구성이에요." items={['시장 지수와 환율', '관심 종목 업데이트', '주요 일정과 뉴스']} button="템플릿으로 시작" onPress={() => onChoose('template')} />
        </Up>
        <Up i={3}>
          <HomeCard icon={<SliderIcon />} title="직접 사용자화" desc="보고 싶은 정보만 골라 나만의 홈 화면을 구성해요." items={['원하는 위젯 선택', '위젯 순서 조정', '언제든 다시 변경']} button="직접 구성하기" onPress={() => onChoose('custom')} />
        </Up>
      </ScrollView>
    </View>
  );
}

/* .card 라운드 22 · 안쪽 18 · 선 1.5 --line (추천은 #16171A) · .ci 42 · h3 19 · .rb '추천' · p 13 ink3 · ul 14 줄 2 · .cb 50 라운드 13 */
function HomeCard({ rec, icon, title, desc, items, button, onPress }: { rec?: boolean; icon: React.ReactNode; title: string; desc: string; items: string[]; button: string; onPress: () => void }) {
  return (
    <View style={[st.card, rec && st.cardRec]}>
      <View style={st.ci}>{icon}</View>
      <View style={st.h3}>
        <Text style={st.h3T}>{title}</Text>
        {rec ? <View style={st.rb}><Text style={st.rbT}>추천</Text></View> : null}
      </View>
      <Text keepAll style={st.cardP}>{desc}</Text>
      <View style={st.ul}>{items.map((t) => <View key={t} style={st.li}><Text style={st.liCk}>✓</Text><Text style={st.liT}>{t}</Text></View>)}</View>
      <Pressable onPress={onPress} style={({ pressed }) => [st.cb, rec && st.cbRec, pressed && { transform: [{ scale: 0.97 }] }]} accessibilityRole="button"><Text style={[st.cbT, rec && { color: '#FFFFFF' }]}>{button}</Text></Pressable>
    </View>
  );
}

function GridIcon() {
  return <Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="#16171A" strokeWidth={1.8}><Rect x={4} y={4} width={7} height={7} rx={2} /><Rect x={13} y={4} width={7} height={7} rx={2} /><Rect x={4} y={13} width={7} height={7} rx={2} /><Rect x={13} y={13} width={7} height={7} rx={2} /></Svg>;
}
function SliderIcon() {
  return <Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="#16171A" strokeWidth={1.8} strokeLinecap="round"><Path d="M4 8h10M18 8h2M4 16h2M10 16h10" /><Circle cx={16} cy={8} r={2} /><Circle cx={8} cy={16} r={2} /></Svg>;
}

const AnimatedCircle = Animated.createAnimatedComponent(Circle);
const AnimatedPath = Animated.createAnimatedComponent(Path);

/* #done .dn: 가운데 · 원(84, r36, 선 5 --a)이 그려진 뒤 체크 · h2 24 · p 14.5 줄 1.7 ink2 · 아래 [memo's 시작하기] (바닥 30) */
function Ready({ top, bottom, onFinish }: { top: number; bottom: number; onFinish: () => void }) {
  const k = useMotionK();
  const [c] = useState(() => new Animated.Value(226));
  const [pth] = useState(() => new Animated.Value(60));
  useEffect(() => {
    const a = Animated.sequence([
      Animated.timing(c, { toValue: 0, duration: 600 * k, easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: false }),
      Animated.timing(pth, { toValue: 0, duration: 350 * k, easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: false }),
    ]);
    a.start();
    return () => a.stop();
  }, [c, pth, k]);
  return (
    <View style={[st.white, { paddingTop: top }]}>
      <View style={st.dn}>
        <Svg width={84} height={84} viewBox="0 0 84 84">
          <AnimatedCircle cx={42} cy={42} r={36} fill="none" stroke={C.a} strokeWidth={5} strokeLinecap="round" strokeDasharray={226} strokeDashoffset={c} transform="rotate(-90 42 42)" />
          <AnimatedPath d="M27 43l10 10 20-21" fill="none" stroke={C.a} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={60} strokeDashoffset={pth} />
        </Svg>
        <Text style={st.dnH}>준비됐어요</Text>
        <Text keepAll style={st.dnP}>{'이제 종목에 첫 메모를 남겨 보세요.\nAI 연결을 켜면 관련 소식을 원문 근거와 함께 모아 드려요.'}</Text>
      </View>
      <View style={[st.bottom, { paddingBottom: Math.max(bottom, 30) }]}>
        <Pressable onPress={onFinish} style={({ pressed }) => [st.cta, pressed && { transform: [{ scale: 0.97 }] }]} accessibilityRole="button"><Text style={st.ctaT}>memo&apos;s 시작하기</Text></Pressable>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  flex: { flex: 1 },
  white: { flex: 1, backgroundColor: '#FFFFFF' },
  gray: { flex: 1, backgroundColor: C.bg },
  hd: { height: 56, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 6 },
  ib: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  prog: { marginLeft: 'auto', marginRight: 16, flexDirection: 'row', alignItems: 'center', gap: 6 },
  progI: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D5D8DD' },
  progOn: { width: 18, backgroundColor: C.a },
  skip: { marginRight: 12, padding: 8, minHeight: 44, justifyContent: 'center' },
  skipT: { fontSize: 14, lineHeight: 20, color: C.ink2 },
  tt: { fontSize: 25, lineHeight: 35, fontWeight: '800', color: C.ink, marginHorizontal: 18, marginBottom: 6 },
  ts: { fontSize: 14, lineHeight: 22.4, color: C.ink3, marginHorizontal: 18 },
  sgw: { paddingTop: 4, paddingHorizontal: 16, paddingBottom: 16 },
  sh5: { fontSize: 15, lineHeight: 22, fontWeight: '800', color: C.ink, marginTop: 6, marginHorizontal: 2, marginBottom: 10 },
  g3: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  s3: { height: 112, borderRadius: 18, backgroundColor: '#FFFFFF', borderWidth: 1.5, borderColor: C.line, padding: 12 },
  s3On: { borderWidth: 2.5, borderColor: C.a, padding: 11, shadowColor: '#6A42AB', shadowOpacity: 0.35, shadowRadius: 10, shadowOffset: { width: 0, height: 10 }, elevation: 4 },
  ck: { position: 'absolute', right: 10, top: 10, width: 22, height: 22, borderRadius: 11, backgroundColor: '#FFFFFF', borderWidth: 2, borderColor: '#D5D8DD', alignItems: 'center', justifyContent: 'center', zIndex: 2 },
  ckOn: { backgroundColor: C.a, borderWidth: 0, transform: [{ scale: 1.08 }] },
  s3B: { fontSize: 13.5, lineHeight: 19, fontWeight: '700', color: C.ink, marginTop: 10, flexShrink: 1 },
  s3S: { fontSize: 11.5, lineHeight: 16, color: C.ink3 },
  more5: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginTop: 20, marginHorizontal: 2, marginBottom: 6, paddingVertical: 12, paddingHorizontal: 14, borderRadius: 14, backgroundColor: '#F6F6F8' },
  more5T: { flex: 1, fontSize: 12.5, lineHeight: 20, color: C.ink2 },
  more5B: { fontWeight: '700', color: C.ink },
  sfoot: { paddingTop: 8, paddingHorizontal: 16, backgroundColor: '#FFFFFF', shadowColor: '#000000', shadowOpacity: 0.06, shadowRadius: 7, shadowOffset: { width: 0, height: -6 }, elevation: 6 },
  tray: { height: 52, marginBottom: 10, borderRadius: 14, backgroundColor: '#F6F4FD', paddingHorizontal: 14, flexDirection: 'row', alignItems: 'center', gap: 10 },
  stack: { flexDirection: 'row' },
  stackLo: { borderRadius: 10, borderWidth: 2, borderColor: '#F6F4FD', margin: -2 },
  tt2: { fontSize: 14.5, lineHeight: 21, fontWeight: '800', color: C.ink },
  tr2: { marginLeft: 'auto', fontSize: 13, lineHeight: 19, fontWeight: '700', color: C.a2 },
  cta: { minHeight: 56, borderRadius: 16, backgroundColor: C.a, alignItems: 'center', justifyContent: 'center', paddingVertical: 14 },
  ctaDis: { backgroundColor: '#D5D8DD' },
  ctaT: { fontSize: 16.5, lineHeight: 24, fontWeight: '800', color: '#FFFFFF' },
  ss: { paddingHorizontal: 20, paddingBottom: 16 },
  ssH: { fontSize: 17, lineHeight: 25, fontWeight: '700', color: C.ink, marginBottom: 4 },
  ssP: { fontSize: 13, lineHeight: 20.8, color: C.ink3, marginBottom: 10 },
  srow2: { height: 60, flexDirection: 'row', alignItems: 'center', gap: 12, borderBottomWidth: 1, borderBottomColor: C.line },
  srowB: { flex: 1, fontSize: 15, lineHeight: 22, fontWeight: '700', color: C.ink },
  seg2: { flexDirection: 'row', backgroundColor: C.sf, borderRadius: 10, padding: 3 },
  seg2I: { position: 'absolute', top: 3, left: 3, width: 52, height: 30, borderRadius: 8, backgroundColor: '#FFFFFF', shadowColor: '#000000', shadowOpacity: 0.1, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  seg2T: { width: 52, height: 30, fontSize: 13, lineHeight: 30, textAlign: 'center', color: C.ink2 },
  seg2On: { color: C.ink, fontWeight: '700' },
  rm: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  rmT: { fontSize: 20, lineHeight: 24, color: C.ink3 },
  card: { marginHorizontal: 16, marginBottom: 14, backgroundColor: '#FFFFFF', borderRadius: 22, padding: 18, borderWidth: 1.5, borderColor: C.line },
  cardRec: { borderColor: '#16171A' },
  ci: { width: 42, height: 42, borderRadius: 12, backgroundColor: C.sf, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  h3: { flexDirection: 'row', alignItems: 'center' },
  h3T: { fontSize: 19, lineHeight: 27, fontWeight: '700', color: C.ink },
  rb: { marginLeft: 'auto', backgroundColor: '#16171A', borderRadius: 7, paddingVertical: 3, paddingHorizontal: 8 },
  rbT: { fontSize: 12, lineHeight: 16, fontWeight: '700', color: '#FFFFFF' },
  cardP: { fontSize: 13, lineHeight: 19, color: C.ink3, marginTop: 6, marginBottom: 10 },
  ul: { marginBottom: 14 },
  li: { flexDirection: 'row', alignItems: 'center' },
  liCk: { fontSize: 14, lineHeight: 28, color: '#3F434A', marginRight: 10 },
  liT: { fontSize: 14, lineHeight: 28, color: C.ink },
  cb: { minHeight: 50, borderRadius: 13, backgroundColor: C.sf, alignItems: 'center', justifyContent: 'center', paddingVertical: 12 },
  cbRec: { backgroundColor: '#16171A' },
  cbT: { fontSize: 15.5, lineHeight: 22, fontWeight: '700', color: C.ink },
  dn: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 30, paddingBottom: 80 },
  dnH: { fontSize: 24, lineHeight: 33, fontWeight: '700', color: C.ink, marginTop: 22, marginBottom: 8 },
  dnP: { fontSize: 14.5, lineHeight: 24.6, color: C.ink2, textAlign: 'center' },
  bottom: { paddingHorizontal: 16 },
});
