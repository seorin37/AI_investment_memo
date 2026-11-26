import React, { useEffect, useState } from 'react';
import { Animated, Easing, KeyboardAvoidingView, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text, TextInput } from '@/components/ui/AppText';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import type { FeedbackProps } from '../My.types';
import { Lb, MC, Page } from './parts';

/**
 * 앱 피드백 보내기 = 원본 app/my.html openFb() (탭바 없음 · 아래 고정 [보내기])
 * 일반 피드백 | 오류 신고 (알약 .35s) · 별점 5개(고르면 #F5B800 · 톡) · 내용 500자 · 개인정보 안내
 * 오류 신고: 화면·기능(선택) · 신고 유형(여러 개) · 상세 내용. 보내기는 연결 안 됨 → onSend 에서 안내만.
 */
export function AppFeedback({ kinds, star_labels, onBack, onSend }: FeedbackProps) {
  const [mode, setMode] = useState<'general' | 'bug'>('general');
  const [star, setStar] = useState(0);
  const [text, setText] = useState('');
  const [where, setWhere] = useState('');
  const [picked, setPicked] = useState<string[]>([]);
  const [detail, setDetail] = useState('');
  const ok = mode === 'bug' || (star > 0 && !!text.trim());
  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior="padding">
      <Page
        title="피드백 보내기"
        lead={mode === 'bug' ? '서비스를 쓰다 생긴 문제를 알려 주세요. 남겨 주신 내용을 확인해서 고칠게요.' : "memo's를 쓰면서 느낀 점을 알려 주세요. 모아 주신 의견으로 더 나은 서비스를 만들게요."}
        onBack={onBack}
        bottom={
          <>
            <Pressable disabled={!ok} onPress={() => onSend({ mode, star, text, where, kinds: picked, detail })} style={({ pressed }) => [st.cta, !ok && st.ctaDis, pressed && { opacity: 0.9 }]} accessibilityRole="button">
              <Text style={[st.ctaT, !ok && { color: '#6B7079' }]}>보내기</Text>
            </Pressable>
            <Text style={[st.cap, ok && { opacity: 0 }]}>별점과 내용을 입력하면 버튼이 켜져요</Text>
          </>
        }
      >
        <Seg value={mode} onChange={setMode} />
        {mode === 'general' ? (
          <>
            <View style={st.rate}>
              <Text style={st.rateT}>얼마나 만족하셨나요?</Text>
              <View style={st.stars}>{[1, 2, 3, 4, 5].map((n) => <Star key={n} n={n} on={star >= n} onPress={() => setStar(n)} />)}</View>
              <Text style={st.rateS}>{star_labels[star]}</Text>
            </View>
            <Lb>피드백 내용</Lb>
            <TextInput value={text} onChangeText={(v) => setText(v.slice(0, 500))} placeholder="좋았던 점이나 개선이 필요한 점을 자유롭게 적어 주세요." placeholderTextColor={MC.ink3} multiline textAlignVertical="top" style={[st.inp, st.area]} accessibilityLabel="피드백 내용" maxLength={500} />
            <Text style={st.cnt}>{text.length} / 500 · 개인정보는 입력하지 말아 주세요</Text>
          </>
        ) : (
          <>
            <Lb style={{ marginTop: 0 }}>문제가 생긴 화면·기능 (선택)</Lb>
            <TextInput value={where} onChangeText={setWhere} placeholder="예: 로그인, 투자 기록, 최신 업데이트" placeholderTextColor={MC.ink3} style={st.inp} accessibilityLabel="문제가 생긴 화면·기능" />
            <Lb>신고 유형 · 여러 개 선택 가능</Lb>
            <View style={st.tg2}>
              {kinds.map((k) => {
                const on = picked.includes(k);
                return (
                  <Pressable key={k} onPress={() => setPicked((p) => (on ? p.filter((x) => x !== k) : [...p, k]))} style={[st.chip, on && st.chipOn]} accessibilityRole="checkbox" accessibilityState={{ checked: on }}>
                    <Text style={[st.chipT, on && { color: MC.a2 }]}>{k}</Text>
                  </Pressable>
                );
              })}
            </View>
            <Lb>상세 내용</Lb>
            <TextInput value={detail} onChangeText={(v) => setDetail(v.slice(0, 500))} placeholder="어떤 작업 중에 문제가 생겼나요? 생긴 상황과 기대했던 동작을 알려 주세요." placeholderTextColor={MC.ink3} multiline textAlignVertical="top" style={[st.inp, st.area]} accessibilityLabel="상세 내용" maxLength={500} />
          </>
        )}
      </Page>
    </KeyboardAvoidingView>
  );
}

/* .seg: #ECEDF1 라운드 13 · 안쪽 3 · 흰 알약 .35s spring */
function Seg({ value, onChange }: { value: 'general' | 'bug'; onChange: (v: 'general' | 'bug') => void }) {
  const k = useMotionK();
  const [w, setW] = useState(0);
  const [x] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(x, { toValue: value === 'bug' ? 1 : 0, duration: 350 * k, easing: Easing.bezier(0.34, 1.45, 0.64, 1), useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [value, k, x]);
  const half = (w - 6) / 2;
  return (
    <View style={st.seg} onLayout={(e) => setW(e.nativeEvent.layout.width)}>
      {w ? <Animated.View style={[st.sl, { width: half, transform: [{ translateX: x.interpolate({ inputRange: [0, 1], outputRange: [0, half] }) }] }]} /> : null}
      {([['general', '일반 피드백'], ['bug', '오류 신고']] as const).map(([v, l]) => (
        <Pressable key={v} onPress={() => onChange(v)} style={st.segB} accessibilityRole="tab" accessibilityState={{ selected: value === v }}>
          <Text style={[st.segT, value === v && st.segTOn]}>{l}</Text>
        </Pressable>
      ))}
    </View>
  );
}

/* 별 30 · 고르면 #F5B800 · 누르면 1.25배 톡 */
function Star({ n, on, onPress }: { n: number; on: boolean; onPress: () => void }) {
  const k = useMotionK();
  const [s] = useState(() => new Animated.Value(1));
  const press = () => {
    onPress();
    Animated.sequence([
      Animated.timing(s, { toValue: 1.25, duration: 130 * k, delay: (n - 1) * 50 * k, useNativeDriver: NATIVE }),
      Animated.timing(s, { toValue: 1, duration: 130 * k, useNativeDriver: NATIVE }),
    ]).start();
  };
  return (
    <Pressable onPress={press} style={st.star} accessibilityRole="button" accessibilityLabel={`${n}점`}>
      <Animated.View style={{ transform: [{ scale: s }] }}>
        <Svg width={30} height={30} viewBox="0 0 24 24"><Path d="M12 3.5l2.6 5.3 5.8.8-4.2 4.1 1 5.8L12 16.8l-5.2 2.7 1-5.8-4.2-4.1 5.8-.8z" fill={on ? '#F5B800' : 'none'} stroke={on ? '#F5B800' : '#C9CCD2'} strokeWidth={1.6} strokeLinejoin="round" /></Svg>
      </Animated.View>
    </Pressable>
  );
}

const st = StyleSheet.create({
  seg: { flexDirection: 'row', backgroundColor: '#ECEDF1', borderRadius: 13, padding: 3, marginBottom: 12 },
  sl: { position: 'absolute', top: 3, bottom: 3, left: 3, borderRadius: 11, backgroundColor: '#FFFFFF', shadowColor: '#000000', shadowOpacity: 0.08, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  segB: { flex: 1, paddingVertical: 10, alignItems: 'center' },
  segT: { fontSize: 15, lineHeight: 21.4, fontWeight: '600', color: MC.ink2 },
  segTOn: { fontWeight: '800', color: MC.ink },
  rate: { backgroundColor: '#FFFFFF', borderRadius: 18, padding: 16, alignItems: 'center' },
  rateT: { fontSize: 15.5, lineHeight: 22.4, fontWeight: '700', color: MC.ink },
  stars: { flexDirection: 'row', gap: 10, marginTop: 10, marginBottom: 4 },
  star: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  rateS: { fontSize: 13, lineHeight: 18.4, fontWeight: '500', color: '#6B7079' },
  inp: { borderWidth: 1, borderColor: '#E2E4E8', borderRadius: 14, paddingVertical: 13, paddingHorizontal: 14, fontSize: 15.5, lineHeight: 21.7, color: MC.ink, backgroundColor: '#FFFFFF' },
  area: { height: 130, lineHeight: 23.25 },
  cnt: { textAlign: 'right', fontSize: 11.5, lineHeight: 16, color: '#6B7079', marginTop: 5 },
  tg2: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { borderWidth: 1, borderColor: '#DADDE2', backgroundColor: '#FFFFFF', borderRadius: 999, paddingVertical: 8, paddingHorizontal: 13, minHeight: 36, justifyContent: 'center' },
  chipOn: { backgroundColor: MC.aSoft, borderColor: '#C9BCF4' },
  chipT: { fontSize: 14, lineHeight: 20.5, fontWeight: '600', color: MC.ink },
  cta: { borderRadius: 16, paddingVertical: 16, minHeight: 56, alignItems: 'center', justifyContent: 'center', backgroundColor: MC.ink },
  ctaDis: { backgroundColor: '#E3E5E9' },
  ctaT: { fontSize: 16, lineHeight: 23, fontWeight: '800', color: '#FFFFFF' },
  cap: { textAlign: 'center', fontSize: 11.5, lineHeight: 16.1, color: '#6B7079', marginTop: 6 },
});
