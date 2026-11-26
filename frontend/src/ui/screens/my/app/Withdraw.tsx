import React, { useEffect, useState } from 'react';
import { BackHandler, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';
import { BottomBar } from '@/ui/shared/app/BottomBar';
import { MiniSpace } from '@/ui/screens/studio/app/MiniBar';
import { Text } from '@/components/ui/AppText';
import { WITHDRAW_REASONS, type WithdrawProps } from '../My.types';
import { ConfirmSheet, Head, Lb, MC, Rv } from './parts';

/**
 * 앱 회원 탈퇴 = 원본 app/my.html openLeave() (탭바 없음 .nt · 아래 고정 버튼 .bot)
 * 빨간 안내(.danger) · 떠나는 이유 (선택) 칩 · 동의 체크 → [탈퇴하기] 가 빨강 → 확인 시트 '정말 탈퇴할까요?'
 * 11.13: 앱은 '삭제되는 데이터' 목록을 뺐음 (counts 는 웹만 씀)
 */
export function AppWithdraw(p: WithdrawProps) {
  const insets = useSafeAreaInsets();
  const [why, setWhy] = useState<string[]>([]);
  const [ok, setOk] = useState(false);
  const [ask, setAsk] = useState(false);
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (ask) setAsk(false);
      else p.onBack();
      return true;
    });
    return () => sub.remove();
  }, [ask, p]);
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <Head title="회원 탈퇴" onBack={p.onBack} />
      <ScrollView contentContainerStyle={[st.w, { paddingBottom: 150 + insets.bottom }]} showsVerticalScrollIndicator={false}>
        <Rv i={0}>
          <View style={st.danger}>
            <Text style={st.dangerB}>탈퇴하면 되돌릴 수 없어요</Text>
            <Text keepAll style={st.dangerT}>계정과 함께 메모·투자 기록·내 종목·AI 연결 설정이 모두 삭제돼요. 카카오 로그인 연결도 함께 해제돼요.</Text>
          </View>
        </Rv>
        <Rv i={2}><Lb>떠나는 이유 (선택)</Lb></Rv>
        <Rv i={3}>
          <View style={st.tg2}>
            {WITHDRAW_REASONS.map((r) => {
              const on = why.includes(r);
              return (
                <Pressable key={r} onPress={() => setWhy((w) => (on ? w.filter((x) => x !== r) : [...w, r]))} style={[st.chip, on && st.chipOn]} accessibilityRole="checkbox" accessibilityState={{ checked: on }}>
                  <Text style={[st.chipT, on && { color: MC.a2 }]}>{r}</Text>
                </Pressable>
              );
            })}
          </View>
        </Rv>
        <Rv i={4}>
          <Pressable onPress={() => setOk((v) => !v)} style={st.agr} accessibilityRole="checkbox" accessibilityState={{ checked: ok }}>
            <View style={[st.cb, ok && st.cbOn]}>
              {ok ? <Svg width={13} height={13} viewBox="0 0 14 14" fill="none"><Path d="M3 7.3l2.6 2.6L11 4.4" stroke="#FFFFFF" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" /></Svg> : null}
            </View>
            <Text keepAll style={st.agrT}>안내를 모두 확인했고, 탈퇴에 동의해요</Text>
          </Pressable>
        </Rv>
        <MiniSpace />
      </ScrollView>
      {/* .bot: 위로 갈수록 투명해지는 바탕 · 안쪽 30 16 12 */}
      <BottomBar clear={30} style={[st.bot, { paddingBottom: 12 + insets.bottom }]}>
        <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" preserveAspectRatio="none">
          <Defs>
            <LinearGradient id="wdBot" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={MC.bg} stopOpacity={0} />
              <Stop offset="0.4" stopColor={MC.bg} stopOpacity={0.85} />
              <Stop offset="0.7" stopColor={MC.bg} stopOpacity={1} />
            </LinearGradient>
          </Defs>
          <Rect x="0" y="0" width="100%" height="100%" fill="url(#wdBot)" />
        </Svg>
        <Pressable disabled={!ok} onPress={() => setAsk(true)} style={({ pressed }) => [st.cta, !ok && st.ctaDis, ok && { backgroundColor: MC.red }, pressed && { opacity: 0.9 }]} accessibilityRole="button">
          <Text style={[st.ctaT, !ok && { color: '#6B7079' }]}>탈퇴하기</Text>
        </Pressable>
      </BottomBar>
      <ConfirmSheet
        open={ask}
        red
        title="정말 탈퇴할까요?"
        body="탈퇴하면 계정과 모든 데이터가 바로 삭제되고 되돌릴 수 없어요."
        ok="탈퇴"
        onCancel={() => setAsk(false)}
        onOk={() => { setAsk(false); p.onConfirm(why); }}
      />
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: MC.bg },
  w: { paddingHorizontal: 16 },
  danger: { backgroundColor: '#FFEEEE', borderWidth: 1, borderColor: '#F7C7C7', borderRadius: 16, paddingVertical: 14, paddingHorizontal: 16 },
  dangerB: { fontSize: 15.5, lineHeight: 22.7, fontWeight: '700', color: '#9A1C1C', marginBottom: 2 },
  dangerT: { fontSize: 13.5, lineHeight: 21.6, color: '#9A1C1C' },
  tg2: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { borderWidth: 1, borderColor: '#DADDE2', backgroundColor: '#FFFFFF', borderRadius: 999, paddingVertical: 8, paddingHorizontal: 13, minHeight: 36, justifyContent: 'center' },
  chipOn: { backgroundColor: MC.aSoft, borderColor: '#C9BCF4' },
  chipT: { fontSize: 14, lineHeight: 20.5, fontWeight: '600', color: MC.ink },
  agr: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 16, marginHorizontal: 4, minHeight: 44 },
  cb: { width: 22, height: 22, borderRadius: 6, borderWidth: 1.6, borderColor: '#C9CCD2', backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  cbOn: { backgroundColor: MC.ink, borderColor: MC.ink },
  agrT: { flex: 1, fontSize: 15, lineHeight: 21.4, color: MC.ink },
  bot: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingTop: 30, paddingHorizontal: 16 },
  cta: { borderRadius: 16, paddingVertical: 16, minHeight: 56, alignItems: 'center', justifyContent: 'center', backgroundColor: MC.ink },
  ctaDis: { backgroundColor: '#E3E5E9' },
  ctaT: { fontSize: 16, lineHeight: 23, fontWeight: '800', color: '#FFFFFF' },
});
