import React, { useState } from 'react';
import { Image, ScrollView, View } from 'react-native';
import { Redirect } from 'expo-router';
import { GoogleLogo, KakaoLogo, NaverLogo } from '@/components/icons/Icon';
import { Hoverable } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { env } from '@/config/env';
import { startSocialLogin } from '@/lib/oauth';
import { useAuth } from '@/store/auth';
import { colors, shadow } from '@/theme/tokens';
import type { AuthProvider } from '@/types/models';

export default function LoginScreen() {
  const status = useAuth((s) => s.status);
  const acceptSession = useAuth((s) => s.acceptSession);
  const mockSignIn = useAuth((s) => s.mockSignIn);
  const [busy, setBusy] = useState<AuthProvider | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (status === 'signedIn') return <Redirect href="/" />;

  async function social(provider: AuthProvider) {
    setError(null);
    setBusy(provider);
    try {
      if (env.useMock) return await mockSignIn();
      const session = await startSocialLogin(provider);
      if (session) await acceptSession(session);
    } catch {
      setError('로그인하지 못했어요. 취소했거나 네트워크 연결을 확인해 주세요.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <ScrollView contentContainerStyle={{ flexGrow: 1, alignItems: 'center', justifyContent: 'center', padding: 20, backgroundColor: colors.page }}>
      <View style={{ width: '100%', maxWidth: 480, backgroundColor: colors.surface, borderRadius: 24, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 48, paddingVertical: 40, alignItems: 'center', ...shadow.card }}>
        <Image source={require('../../assets/images/logo-wordmark.png')} style={{ width: 150, height: 50 }} resizeMode="contain" accessibilityLabel="MEMO'S" />
        <T size={26} weight="bold" style={{ marginTop: 12 }}>투자 메모를 한 곳에서</T>
        <T size={14} color={colors.textSub} style={{ marginTop: 6 }}>소셜 계정으로 간편하게 시작하세요</T>
        <View style={{ alignSelf: 'stretch', gap: 12, marginTop: 30 }}>
          <SocialButton label="카카오로 로그인" bg="#FEE500" fg="#191919" logo={<KakaoLogo />} loading={busy === 'kakao'} onPress={() => social('kakao')} />
          <SocialButton label="네이버로 로그인" bg="#03A94D" fg="#FFFFFF" logo={<NaverLogo />} loading={busy === 'naver'} onPress={() => social('naver')} />
          <SocialButton label="구글로 로그인" bg="#FFFFFF" fg="#191919" border logo={<GoogleLogo />} loading={busy === 'google'} onPress={() => social('google')} />
        </View>
        {error && <T size={13} color={colors.danger} style={{ marginTop: 14 }} align="center">{error}</T>}
      </View>
      {env.useMock && <T size={12} color={colors.textMuted} style={{ marginTop: 16 }}>목업 모드 — 소셜 버튼으로 예시 계정에 들어가요</T>}
    </ScrollView>
  );
}

function SocialButton({ label, bg, fg, logo, border, onPress, loading }: { label: string; bg: string; fg: string; logo: React.ReactNode; border?: boolean; onPress: () => void; loading?: boolean }) {
  return (
    <Hoverable accessibilityRole="button" accessibilityLabel={label} onPress={loading ? undefined : onPress} style={{ height: 56, borderRadius: 10, backgroundColor: bg, borderWidth: border ? 1 : 0, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', opacity: loading ? 0.7 : 1 }} hoverStyle={{ opacity: 0.92 }}>
      <View style={{ position: 'absolute', left: 24 }}>{logo}</View>
      <T size={16} weight="bold" color={fg} lh={1.2}>{loading ? '연결 중…' : label}</T>
    </Hoverable>
  );
}
