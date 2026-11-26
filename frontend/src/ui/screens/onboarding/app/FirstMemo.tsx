import React, { useEffect, useRef, useState } from 'react';
import { Animated, BackHandler, Easing, Keyboard, KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, View, type ScrollViewInstance } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Line, Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { splitMemo } from '@/lib/memoText';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { MemoEditor } from '@/ui/shared/MemoEditor';
import { PaperBox } from '@/ui/shared/PaperBox';
import { StockLogo } from '@/ui/shared/StockLogo';
import { Toggle } from '@/ui/shared/Toggle';
import type { AppFirstMemoProps } from '../FirstHome.types';
import { FirstStockSheet } from './FirstHome';

/**
 * 앱 첫 메모 = 원본 app/start.html #nm (흰 전체 화면)
 * 머리 56 (좌우 16 · 간격 8): [취소] 15.5 · 가운데 종목 칩(.stkb 34 · 로고 24 · '종목 · 새 메모' 14.5 700 · ▾) · [완료] 15.5 800 #7356D6
 * 노란 종이(최소 250 · 라운드 22 · 접힘 28) + 예시 글 · '빈 메모 · 예시 글은 저장되지 않아요' · [예시로 채워 보기]
 * AI 연결 칸 ('켜 두면 하루 한 번 공시·뉴스를 대신 확인해 여기에 붙여 드려요.') · 처음 쓰기 시작하면 0.6초 뒤 안내 말풍선(.tip)
 */
const C = { a2: '#7356D6', aa: '#6A42AB', ink: '#16171A', ink3: '#8A8F98' };
const Y = { bg: '#FCEAAA', accent: '#EFBF2A' };
/* 원본 #fill 이 차례로 치는 세 줄 (문구 규칙: 권유·전망 없음 — 확인할 것과 다시 볼 조건만) */
const EXAMPLE = ['HBM 실적 계속 보기', '다음 정기보고서에서 HBM 매출 비중 확인하기', '종가 20만 원 아래로 내려오면 다시 살펴보기'];

export function AppFirstMemo({ stocks, stock_code, onCancel, onEmpty, onSave }: AppFirstMemoProps) {
  const insets = useSafeAreaInsets();
  const k = useMotionK();
  const [code, setCode] = useState(stock_code);
  const stock = stocks.find((s) => s.stock_code === code) ?? stocks[0];
  const [text, setText] = useState('');
  const [ai, setAi] = useState(false);
  const [picker, setPicker] = useState(false);
  const [tip, setTip] = useState<'none' | 'open' | 'done'>('none');
  /* 키보드가 떠 있으면 말풍선을 AI 칸 위로 ('알겠어요'가 키보드에 가려지지 않게) */
  const [kb, setKb] = useState(false);
  useEffect(() => {
    const a = Keyboard.addListener('keyboardDidShow', () => setKb(true));
    const b = Keyboard.addListener('keyboardDidHide', () => setKb(false));
    return () => { a.remove(); b.remove(); };
  }, []);
  const [typing, setTyping] = useState(false);
  const ed = useRef<{ focus: () => void; blur: () => void }>(null);
  const scroll = useRef<ScrollViewInstance>(null);
  const empty = !text.trim();
  /* 원본: 열리고 0.4초 뒤 편집 시작 */
  useEffect(() => {
    const t = setTimeout(() => ed.current?.focus(), 400 * k);
    return () => clearTimeout(t);
  }, [k]);
  /* 안드로이드 뒤로: 시트 → 말풍선 → 취소 */
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (picker) setPicker(false);
      else if (tip === 'open') setTip('done');
      else onCancel();
      return true;
    });
    return () => sub.remove();
  }, [picker, tip, onCancel]);
  /* 원본 typeLine: 글자마다 26ms */
  useEffect(() => {
    if (!typing) return;
    const full = EXAMPLE.join('\n');
    let n = 0;
    const id = setInterval(() => {
      n += 1;
      setText(full.slice(0, n));
      if (n >= full.length) {
        clearInterval(id);
        setTyping(false);
        setTip((t) => (t === 'none' ? 'open' : t));
      }
    }, Math.max(4, 26 * k));
    return () => clearInterval(id);
  }, [typing, k]);

  const showTipLater = () => {
    if (tip !== 'none') return;
    setTimeout(() => setTip((t) => (t === 'none' ? 'open' : t)), 600 * k);
  };
  const save = () => {
    ed.current?.blur();
    if (empty || !stock) return onEmpty();
    const r = splitMemo(text);
    onSave({ stock, title: r.title, body: r.body, ai });
  };
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <View style={st.nmh}>
        <Pressable onPress={onCancel} accessibilityRole="button" style={st.hb}><Text style={st.hbT}>취소</Text></Pressable>
        <View style={st.ttl}>
          {stock ? (
            <Pressable onPress={() => setPicker(true)} style={st.stkb} accessibilityRole="button" accessibilityLabel={`${stock.name} · 새 메모, 종목 바꾸기`}>
              <StockLogo logo={stock.logo} bg={stock.logo_bg} ink={stock.logo_ink} size={24} radius={8} fontSize={11} variant="app" />
              <Text style={st.stkbT} numberOfLines={1}>{stock.name} · 새 메모</Text>
              <Svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke={C.ink3} strokeWidth={2.4} strokeLinecap="round"><Path d="M6 9l6 6 6-6" /></Svg>
            </Pressable>
          ) : null}
        </View>
        <Pressable onPress={save} accessibilityRole="button" style={st.hb}><Text style={[st.hbT, st.ok]}>완료</Text></Pressable>
      </View>
      <KeyboardAvoidingView style={st.flex} behavior="padding">
        <ScrollView ref={scroll} style={st.flex} contentContainerStyle={[st.nmb, { paddingBottom: 120 + insets.bottom }]} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
          <PaperBox bg={Y.bg} accent={Y.accent} radius={22} cut={28} style={st.paper}>
            {empty ? (
              <View pointerEvents="none" style={st.phd}>
                <Text style={st.phdB}>HBM 실적 계속 보기</Text>
                <Text style={st.phdP}>{'다음 정기보고서에서 HBM 매출 비중 확인하기\n종가 ○○만원 아래로 내려오면 다시 보기'}</Text>
                <View style={st.hn}>
                  {/* 원본 border-top 1px dashed (RN 은 한쪽만 점선이 안 되어 선을 그림) */}
                  <Svg width="100%" height={1} style={st.hnLine}>
                    <Line x1="0" y1="0.5" x2="100%" y2="0.5" stroke="rgba(22,22,28,0.18)" strokeWidth={1} strokeDasharray="3 3" />
                  </Svg>
                  <Text keepAll style={st.hnT}>{'첫 줄은 제목이 돼요.\n확인할 것·다시 볼 조건을 적어 두면 AI가 관련 소식을 더 잘 찾아요.'}</Text>
                </View>
              </View>
            ) : null}
            <MemoEditor variant="app" value={text} onChangeText={setText} editable autoFocus={false} onFocus={showTipLater} focusRef={ed} accessibilityLabel="새 메모 (첫 줄은 제목)" />
          </PaperBox>
          <Text style={st.ecap}>빈 메모 · 예시 글은 저장되지 않아요</Text>
          <Pressable onPress={() => { setText(''); setTyping(true); }} disabled={typing} style={st.fill} accessibilityRole="button" hitSlop={{ top: 8, bottom: 8 }}>
            <Text style={st.fillT}>예시로 채워 보기</Text>
          </Pressable>
          {/* 말풍선은 AI 칸 기준 absolute (원본 .tip top:calc(100% + 10px)) — 떠도 메모지·칸이 밀리지 않음 */}
          <View style={st.aiWrap}>
            <View style={st.aisw}>
              <View style={st.flex}>
                <Text style={st.aiswB}>AI 연결</Text>
                <Text keepAll style={st.aiswS}>켜 두면 하루 한 번 공시·뉴스를 대신 확인해 여기에 붙여 드려요.</Text>
              </View>
              <Toggle variant="app" on={ai} onChange={(v) => { setAi(v); setTip('done'); }} label="AI 연결" />
            </View>
            {tip === 'open' ? <Tip up={kb} onClose={() => setTip('done')} /> : null}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
      <FirstStockSheet
        open={picker}
        stocks={stocks}
        selected={code}
        button="이 종목으로 바꾸기"
        onClose={() => setPicker(false)}
        onConfirm={(s) => { setCode(s.stock_code); setPicker(false); }}
      />
    </View>
  );
}

/* .tip: AI 칸 아래 10 · 오른쪽 6 · 폭 258 · #1F2024 라운드 14 · 13px 줄 1.55 · 위쪽 꼬리(오른쪽 28) · [알겠어요] #CDBBFF 800 · 튀어나옴 .45s */
/* up: 키보드가 떠 있으면 아래 공간이 모자라 AI 칸 위로 띄움 (꼬리 아래쪽) — 메모지는 그대로 */
function Tip({ onClose, up }: { onClose: () => void; up: boolean }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: 1, duration: 450 * k, easing: Easing.bezier(0.34, 1.45, 0.64, 1), useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [k, v]);
  return (
    <Animated.View style={[st.tip, up && st.tipUp, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [up ? 6 : -6, 0] }) }, { scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.85, 1] }) }] }]}>
      <View style={up ? st.tipTailUp : st.tipTail} />
      <Text keepAll style={st.tipT}>AI 연결을 켜면 이 메모와 관련된 <Text keepAll style={st.tipB}>공시·뉴스·종가 변화</Text>를 찾아 원문 링크와 함께 보여 드려요.</Text>
      <Pressable onPress={onClose} style={st.tipBtn} accessibilityRole="button" hitSlop={8}><Text style={st.tipBtnT}>알겠어요</Text></Pressable>
    </Animated.View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#FFFFFF' },
  flex: { flex: 1, minWidth: 0 },
  nmh: { height: 56, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, gap: 8 },
  hb: { paddingVertical: 8, paddingHorizontal: 2, minHeight: 44, justifyContent: 'center' },
  hbT: { fontSize: 15.5, lineHeight: 22, color: C.ink },
  ok: { fontWeight: '800', color: C.a2 },
  ttl: { flex: 1, minWidth: 0, alignItems: 'center' },
  stkb: { maxWidth: '100%', flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 34, paddingLeft: 5, paddingRight: 10, borderRadius: 17, backgroundColor: '#F4F5F7' },
  stkbT: { flexShrink: 1, fontSize: 14.5, lineHeight: 21, fontWeight: '700', color: C.ink },
  nmb: { paddingTop: 4, paddingHorizontal: 16 },
  paper: { minHeight: 250, paddingTop: 26, paddingHorizontal: 20, paddingBottom: 34 },
  phd: { position: 'absolute', left: 20, right: 20, top: 26 },
  phdB: { fontSize: 21, lineHeight: 29.4, fontWeight: '700', color: 'rgba(22,22,28,0.3)', marginTop: 4, marginBottom: 8 },
  phdP: { fontSize: 15.5, lineHeight: 27.9, color: 'rgba(22,22,28,0.32)' },
  hn: { marginTop: 12, paddingTop: 10 },
  hnLine: { position: 'absolute', left: 0, right: 0, top: 0 },
  hnT: { fontSize: 12.5, lineHeight: 20, color: 'rgba(22,22,28,0.4)' },
  ecap: { textAlign: 'center', fontSize: 12.5, lineHeight: 18, color: C.ink3, marginTop: 12 },
  fill: { alignSelf: 'center', marginTop: 8, minHeight: 28, justifyContent: 'center' },
  fillT: { fontSize: 12.5, lineHeight: 18, fontWeight: '700', color: C.aa, textDecorationLine: 'underline' },
  aisw: { backgroundColor: '#F6F6F8', borderRadius: 16, paddingVertical: 14, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 14 },
  aiswB: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: C.ink },
  aiswS: { fontSize: 12, lineHeight: 17, color: C.ink3 },
  aiWrap: { zIndex: 3 },
  tip: { position: 'absolute', top: '100%', right: 6, marginTop: 10, width: 258, zIndex: 3, backgroundColor: '#1F2024', borderRadius: 14, paddingVertical: 12, paddingHorizontal: 14, shadowColor: '#000000', shadowOpacity: 0.4, shadowRadius: 12, shadowOffset: { width: 0, height: 12 }, elevation: 8 },
  tipTail: { position: 'absolute', right: 28, top: -16, width: 0, height: 0, borderWidth: 8, borderColor: 'transparent', borderBottomColor: '#1F2024' },
  tipUp: { top: undefined, bottom: '100%', marginTop: 0, marginBottom: 10 },
  tipTailUp: { position: 'absolute', right: 28, bottom: -16, width: 0, height: 0, borderWidth: 8, borderColor: 'transparent', borderTopColor: '#1F2024' },
  tipT: { fontSize: 13, lineHeight: 20.15, color: '#FFFFFF' },
  tipB: { fontWeight: '700', color: '#FFFFFF' },
  tipBtn: { alignSelf: 'flex-end', marginTop: 8 },
  tipBtnT: { fontSize: 12.5, lineHeight: 18, fontWeight: '800', color: '#CDBBFF' },
});
