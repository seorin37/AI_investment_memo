import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { Logo } from '@/ui/icons/Icon';
import { GoogleGlyph, KakaoGlyph, NaverGlyph } from '@/ui/screens/auth/AuthGlyphs';
import type { LoginProps } from '@/ui/screens/auth/Auth.types';
import { fpx, webTracking } from '@/ui/theme';
import type { AuthProvider } from '@/types/models';

const BUTTONS: { provider: AuthProvider; label: string; bg: string; fg: string; border?: boolean }[] = [
  { provider: 'kakao', label: '카카오로 로그인', bg: '#FEE500', fg: '#191919' },
  { provider: 'naver', label: '네이버로 로그인', bg: '#03A94D', fg: '#FFFFFF' },
  { provider: 'google', label: '구글로 로그인', bg: '#FFFFFF', fg: '#191919', border: true },
];

function ProviderIcon({ provider }: { provider: AuthProvider }) {
  if (provider === 'kakao') return <KakaoGlyph />;
  if (provider === 'naver') return <NaverGlyph />;
  return <GoogleGlyph />;
}

export function WebLogin(p: LoginProps) {
  const notice = p.error === 'network' ? '인터넷에 연결되어 있지 않아요' : p.error === 'login' ? '로그인을 마치지 못했어요. 다시 시도해 주세요.' : null;
  return (
    <View style={st.screen}>
      <View style={st.card}>
        {notice ? (
          <View style={st.notice}>
            <Text style={st.noticeText}>{notice}</Text>
            {p.error === 'network' ? <Pressable onPress={p.onRetry}><Text style={st.noticeAction}>다시 시도</Text></Pressable> : null}
          </View>
        ) : null}
        <Logo kind="web" size={150} height={50} color="#111111" />
        <Text style={st.title}>내 생각에서 시작하는 투자 소식</Text>
        <Text style={st.sub}>소셜 계정으로 간편하게 시작하세요</Text>
        <View style={st.buttons}>
          {BUTTONS.map((button) => {
            const loading = p.busy === button.provider;
            return (
              <View key={button.provider}>
                <Pressable
                  onPress={() => p.onLogin(button.provider)}
                  disabled={!!p.busy}
                  style={({ hovered }: { hovered?: boolean }) => [st.button, { backgroundColor: button.bg, borderWidth: button.border ? 1 : 0, borderColor: '#E8ECF3', opacity: hovered ? 0.92 : p.busy && !loading ? 0.62 : 1 }]}
                >
                  <View style={st.buttonIcon}>{loading ? <ActivityIndicator size={24} color={button.fg} /> : <ProviderIcon provider={button.provider} />}</View>
                  <Text style={[st.buttonText, { color: button.fg }]}>{button.label}</Text>
                  <View style={st.buttonSpacer} />
                </Pressable>
                {p.recent_provider === button.provider ? <View style={st.recent}><Text style={st.recentText}>최근 로그인</Text></View> : null}
              </View>
            );
          })}
        </View>
        <Pressable onPress={p.onIntro} accessibilityRole="button" style={st.introLink}>
          <Text style={st.introText}>MEMO&apos;S가 처음이라면 · 서비스 소개 보기</Text>
        </Pressable>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  screen: { flex: 1, minHeight: 600, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FDFDFD', padding: 16 },
  card: { width: 480, maxWidth: '100%', alignItems: 'center', overflow: 'hidden', borderRadius: 24, borderWidth: 1, borderColor: '#E5E8EB', backgroundColor: '#FFFFFF', paddingHorizontal: 48, paddingVertical: 40 },
  notice: { alignSelf: 'stretch', marginBottom: 20, minHeight: 46, borderRadius: 12, backgroundColor: '#FDF0F1', paddingHorizontal: 16, paddingVertical: 12, flexDirection: 'row', alignItems: 'center', gap: 8 },
  noticeText: { ...fpx(14, 21), flex: 1, color: '#C0392B', fontWeight: '700' },
  noticeAction: { ...fpx(14, 21), color: '#C0392B', fontWeight: '700' },
  title: { ...fpx(26, 35), marginTop: 12, color: '#191F28', fontWeight: '700', textAlign: 'center', letterSpacing: webTracking(26) },
  sub: { ...fpx(14, 21), marginTop: 6, color: '#8F8F8F', textAlign: 'center', letterSpacing: webTracking(14) },
  buttons: { alignSelf: 'stretch', marginTop: 28, gap: 12 },
  button: { minHeight: 56, borderRadius: 12, paddingHorizontal: 24, paddingVertical: 15, flexDirection: 'row', alignItems: 'center' },
  buttonIcon: { width: 24, alignItems: 'center' },
  buttonSpacer: { width: 24 },
  buttonText: { ...fpx(17, 26), flex: 1, textAlign: 'center', fontWeight: '700', letterSpacing: webTracking(17) },
  recent: { position: 'absolute', right: 12, top: -8, borderRadius: 10, backgroundColor: '#15171A', paddingHorizontal: 8, paddingVertical: 2 },
  recentText: { ...fpx(12, 16), color: '#FFFFFF', fontWeight: '700' },
  introLink: { marginTop: 20 },
  introText: { ...fpx(14, 21), color: '#8F8F8F', letterSpacing: webTracking(14) },
});
