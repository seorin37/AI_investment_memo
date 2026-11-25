import React, { useEffect } from 'react';
import { BackHandler, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, G, Path } from 'react-native-svg';
import { MiniSpace } from '@/ui/screens/studio/app/MiniBar';
import { Text } from '@/components/ui/AppText';
import { Avatar } from '@/ui/shared/Avatar';
import { SkySwitch } from '@/ui/shared/SkySwitch';
import type { AppMyProps } from '../My.types';
import { Chev, Grp, Head, Item, MC, Rv, UsageBar } from './parts';
import { DARK_SUPPORTED } from '@/ui/shared/Dark';

/**
 * 앱 MY 본 화면 = 원본 app/my.html mainHTML() (11.13·11.17 반영판)
 * 프로필 묶음(50 아바타 · 18 이름 · 12.5 소개) · AI 사용량(원본 예시 배지는 뺌 · 자세히 › · 막대 6 · '이번 기간 N% 사용' · 'MM.DD 갱신')
 * 계정(알림) · 화면(다크 모드 · 낮밤 스위치) · 서비스(사용량 N%) · 기타(데이터 · 휴지통 · 정보) · 지원(피드백 보내기 · 도움말) · 버전
 */
const PROVIDER: Record<string, string> = { kakao: '카카오', naver: '네이버', google: '구글' };

export function AppMy(p: AppMyProps) {
  const insets = useSafeAreaInsets();
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      p.onBack();
      return true;
    });
    return () => sub.remove();
  }, [p]);
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <Head title="MY" onBack={p.onBack} />
      <ScrollView style={st.sc} contentContainerStyle={st.w} showsVerticalScrollIndicator={false}>
        <Rv i={0}>
          <Pressable onPress={p.onProfile} style={({ pressed }) => [st.prof, pressed && { backgroundColor: '#F7F7F9' }]} accessibilityRole="button" accessibilityLabel={`${p.profile.name} 내 프로필`}>
            <Avatar name={p.profile.name} photoUrl={p.profile.photoUrl} size={50} variant="app" boxStyle={st.avb} textStyle={st.avbT} />
            <View style={st.flex}>
              <Text style={st.profB} numberOfLines={1}>{p.profile.name}</Text>
              <Text style={st.profS} numberOfLines={1}>{p.profile.intro} · {PROVIDER[p.profile.provider] ?? ''}로 로그인 중</Text>
            </View>
            <Chev />
          </Pressable>
        </Rv>
        <Rv i={1}>
          <Pressable onPress={p.onUsage} style={({ pressed }) => [st.use, pressed && { backgroundColor: '#F7F7F9' }]} accessibilityRole="button" accessibilityLabel={`AI 사용량 ${p.usage_pct}%`}>
            <View style={st.useT}>
              <Text style={st.useTT}>AI 사용량</Text>
              <View style={st.more}><Text style={st.moreT}>자세히</Text><Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={MC.a2} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"><Path d="M9 5l7 7-7 7" /></Svg></View>
            </View>
            <UsageBar pct={p.usage_pct} />
            <View style={st.useM}>
              <Text style={st.useMT}>이번 기간 <Text style={[st.useMT, { fontWeight: '700', fontVariant: ['tabular-nums'] }]}>{p.usage_pct}</Text>% 사용</Text>
              <Text style={st.useMT}>{p.usage_renew} 갱신</Text>
            </View>
          </Pressable>
        </Rv>
        <Rv i={2}><Sec>계정</Sec></Rv>
        <Rv i={3}><Grp><Item title="알림" last onPress={() => p.onOpen('noti')} /></Grp></Rv>
        <Rv i={4}><Sec>화면</Sec></Rv>
        <Rv i={4}>
          <Grp>
            {DARK_SUPPORTED ? (
            <Pressable onPress={p.onToggleDark} style={st.dk} accessibilityRole="switch" accessibilityState={{ checked: p.dark }} accessibilityLabel="다크 모드">
              <View style={st.dki}>{p.dark ? <MoonIcon /> : <SunIcon />}</View>
              <Text style={st.dkT}>다크 모드</Text>
              <View style={st.dkSw} pointerEvents="none"><SkySwitch on={p.dark} width={64} /></View>
            </Pressable>
            ) : null}
          </Grp>
        </Rv>
        <Rv i={4}><Sec>서비스</Sec></Rv>
        <Rv i={5}><Grp><Item title="사용량" value={`${p.usage_pct}%`} last onPress={() => p.onOpen('usage')} /></Grp></Rv>
        <Rv i={6}><Sec>기타</Sec></Rv>
        <Rv i={7}>
          <Grp>
            <Item title="데이터" onPress={() => p.onOpen('data')} />
            <Item title="휴지통" onPress={() => p.onOpen('trash')} />
            <Item title="정보" last onPress={() => p.onOpen('info')} />
          </Grp>
        </Rv>
        <Rv i={8}><Sec>지원</Sec></Rv>
        <Rv i={9}>
          <Grp>
            <Item title="피드백 보내기" onPress={() => p.onOpen('fb')} />
            <Item title="도움말" last onPress={() => p.onOpen('help')} />
          </Grp>
        </Rv>
        <Rv i={10}><Text style={st.ver}>{p.version}</Text></Rv>
        <MiniSpace />
      </ScrollView>
    </View>
  );
}

/* 구역 이름: 줄 15 → 앞 카드 끝에서 다음 카드까지 16 + 15 + 7 = 38 */
function Sec({ children }: { children: string }) {
  return <View style={st.sec}><Text keepAll style={st.secT}>{children}</Text></View>;
}

function SunIcon() {
  return (
    <Svg width={20} height={20} viewBox="0 0 16 16">
      <Circle cx={8} cy={8} r={3} fill="#333333" />
      <G stroke="#333333" strokeWidth={1.5} strokeLinecap="round"><Path d="M8 1.5v1.4M8 13.1v1.4M1.5 8h1.4M13.1 8h1.4M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" /></G>
    </Svg>
  );
}
function MoonIcon() {
  return <Svg width={20} height={20} viewBox="0 0 16 16"><Path d="M13.5 9.8A5.6 5.6 0 0 1 6.2 2.5a5.6 5.6 0 1 0 7.3 7.3z" fill="#333333" /></Svg>;
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: MC.bg },
  flex: { flex: 1, minWidth: 0 },
  /* 머리 58 중 4 만큼 올려 프로필 카드를 원본 위치로 */
  sc: { marginTop: -4 },
  w: { paddingHorizontal: 16, paddingBottom: 28 },
  sec: { paddingTop: 16, paddingLeft: 4, paddingBottom: 7 },
  secT: { fontSize: 12.5, lineHeight: 15, color: MC.ink3 },
  prof: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, backgroundColor: '#FFFFFF', borderRadius: 18 },
  avb: { width: 50, height: 50, borderRadius: 25, backgroundColor: MC.aSoft, alignItems: 'center', justifyContent: 'center' },
  avbT: { fontSize: 20, lineHeight: 26, fontWeight: '800', color: MC.a2 },
  profB: { fontSize: 18, lineHeight: 26, fontWeight: '700', color: MC.ink },
  profS: { fontSize: 12.5, lineHeight: 18, color: MC.ink3, flexShrink: 1 },
  /* 높이 84 = 14 + 18 + 막대 26 + 14 + 12 */
  use: { marginTop: 10, paddingTop: 14, paddingHorizontal: 16, paddingBottom: 12, backgroundColor: '#FFFFFF', borderRadius: 18 },
  useT: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  useTT: { fontSize: 14, lineHeight: 18, fontWeight: '700', color: MC.ink },
  more: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center' },
  moreT: { fontSize: 13, lineHeight: 18, fontWeight: '700', color: MC.a2 },
  useM: { flexDirection: 'row', justifyContent: 'space-between' },
  useMT: { fontSize: 12, lineHeight: 14, color: MC.ink2 },
  dk: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 52, paddingHorizontal: 16 },
  dki: { width: 22, height: 22, alignItems: 'center', justifyContent: 'center' },
  dkT: { fontSize: 15, lineHeight: 22, color: MC.ink },
  dkSw: { marginLeft: 'auto' },
  ver: { textAlign: 'center', fontSize: 12, lineHeight: 17, color: MC.ink3, marginTop: 18 },
});
