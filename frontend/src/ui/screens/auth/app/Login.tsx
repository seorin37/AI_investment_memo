import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { Logo } from '@/ui/icons/Icon';
import { GoogleGlyph, KakaoGlyph, NaverGlyph, WifiOffGlyph } from '@/ui/screens/auth/AuthGlyphs';
import type { LoginProps } from '@/ui/screens/auth/Auth.types';
import { appColor, ft } from '@/ui/theme';
import type { AuthProvider } from '@/types/models';
import { Keep } from '@/ui/shared/Dark';

const BUTTONS: { provider: AuthProvider; label: string; bg: string; fg: string; border?: boolean }[] = [
  { provider: 'kakao', label: '카카오로 로그인', bg: '#FEE500', fg: '#191919' },
  { provider: 'naver', label: '네이버로 로그인', bg: '#03C75A', fg: '#FFFFFF' },
  { provider: 'google', label: '구글로 로그인', bg: '#FFFFFF', fg: '#191919', border: true },
];

function ProviderIcon({ provider }: { provider: AuthProvider }) {
  if (provider === 'kakao') return <KakaoGlyph />;
  if (provider === 'naver') return <NaverGlyph />;
  return <GoogleGlyph />;
}

export function AppLogin(p: LoginProps) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[st.screen, { paddingTop: insets.top, paddingBottom: Math.max(insets.bottom, 24) }]}>
      {p.error === 'network' ? (
        <View style={[st.offline, { top: insets.top }]}>
          <View style={st.offlineCopy}><WifiOffGlyph /><Text style={st.offlineText}>인터넷에 연결되어 있지 않아요</Text></View>
          <Pressable onPress={p.onRetry} hitSlop={8}><Text style={st.retry}>다시 시도</Text></Pressable>
        </View>
      ) : null}
      <View style={st.main}>
        <Logo kind="app" size={171} height={54} color="#16171A" />
        <Text style={st.title}>내 생각에서 시작하는 투자 소식</Text>
        <Text style={st.sub}>소셜 계정으로 간편하게 시작하세요</Text>
        <View style={st.buttons}>
          {BUTTONS.map((button) => {
            const loading = p.busy === button.provider;
            /* 원본 앱 다크: 카카오·네이버 버튼은 원래 색 (.btn.k · .btn.n) */
            const Wrap = button.provider === 'kakao' || button.provider === 'naver' ? Keep : View;
            return (
              <Wrap key={button.provider}>
                <Pressable
                  onPress={() => p.onLogin(button.provider)}
                  disabled={!!p.busy}
                  accessibilityRole="button"
                  accessibilityLabel={button.label}
                  style={[st.button, { backgroundColor: button.bg, borderWidth: button.border ? 1 : 0, borderColor: '#D7DBE2', opacity: p.busy && !loading ? 0.62 : 1 }]}
                >
                  <View style={st.buttonIcon}>{loading ? <ActivityIndicator size={24} color={button.fg} /> : <ProviderIcon provider={button.provider} />}</View>
                  <Text style={[st.buttonText, { color: button.fg }]}>{button.label}</Text>
                  <View style={st.buttonSpacer} />
                </Pressable>
                {p.recent_provider === button.provider ? <View style={st.recent}><Text style={st.recentText}>최근 로그인</Text></View> : null}
              </Wrap>
            );
          })}
        </View>
        {p.error === 'login' ? <View style={st.errorToast}><Text style={st.errorText}>로그인을 마치지 못했어요. 다시 시도해 주세요.</Text></View> : null}
      </View>
      <Text style={st.foot}>가입하면 다음 화면에서 약관 동의를 받아요</Text>
    </View>
  );
}

const st = StyleSheet.create({
  screen: { flex: 1, backgroundColor: appColor.bg, alignItems: 'center', paddingHorizontal: 24 },
  main: { position: 'absolute', top: 300, left: 24, right: 24, alignItems: 'center' },
  title: { ...ft(24, 1.45), marginTop: 18, color: '#191F28', fontWeight: '700', textAlign: 'center' },
  sub: { ...ft(15, 1.5), marginTop: 5, color: '#6B7079', textAlign: 'center' },
  buttons: { alignSelf: 'stretch', marginTop: 34, gap: 10 },
  button: { minHeight: 54, borderRadius: 12, paddingHorizontal: 22, paddingVertical: 15, flexDirection: 'row', alignItems: 'center' },
  buttonIcon: { width: 28, alignItems: 'center' },
  buttonSpacer: { width: 28 },
  buttonText: { ...ft(17), flex: 1, textAlign: 'center', fontWeight: '700' },
  recent: { position: 'absolute', right: 12, top: -10, borderRadius: 8, backgroundColor: '#15171A', paddingHorizontal: 8, paddingVertical: 3 },
  recentText: { ...ft(13), color: '#FFFFFF', fontWeight: '700' },
  errorToast: { alignSelf: 'center', marginTop: 14, borderRadius: 12, backgroundColor: '#303139', paddingHorizontal: 16, paddingVertical: 10 },
  errorText: { ...ft(14), color: '#FFFFFF', fontWeight: '600' },
  foot: { ...ft(14), position: 'absolute', bottom: 42, color: '#6B7079', textAlign: 'center' },
  offline: { position: 'absolute', zIndex: 4, left: 0, right: 0, minHeight: 48, backgroundColor: '#2F3037', paddingHorizontal: 20, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  offlineCopy: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  offlineText: { ...ft(15), color: '#FFFFFF', fontWeight: '600' },
  retry: { ...ft(15), color: '#D7C8FF', fontWeight: '700' },
});
