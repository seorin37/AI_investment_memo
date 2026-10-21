import React, { useState } from 'react';
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, View } from 'react-native';
import { Redirect } from 'expo-router';
import { api, ApiError } from '@/api';
import { env } from '@/config/env';
import { GoogleLogo, KakaoLogo, NaverLogo } from '@/components/icons/Icon';
import { Button, Hoverable, TextField } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { startSocialLogin } from '@/lib/oauth';
import { useAuth } from '@/store/auth';
import { colors, shadow } from '@/theme/tokens';
import type { AuthProvider } from '@/types/models';

type Mode = 'social' | 'emailLogin' | 'emailSignup';

/** 1. 로그인 — 카카오 · 네이버 · 구글 + 이메일 */
export default function LoginScreen() {
  const status = useAuth((s) => s.status);
  const signIn = useAuth((s) => s.signIn);
  const [mode, setMode] = useState<Mode>('social');
  const [busy, setBusy] = useState<AuthProvider | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  if (status === 'signedIn') return <Redirect href="/" />;

  async function social(provider: Exclude<AuthProvider, 'email'>) {
    setError(null);
    setBusy(provider);
    try {
      if (env.useMock) {
        const t = await api.loginEmail('mock@memos.example', 'mock');
        await signIn(t.access_token, t.user);
        return;
      }
      const token = await startSocialLogin(provider); // 웹은 페이지 이동
      if (token) await signIn(token);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '로그인하지 못했어요. 잠시 후 다시 시도해 주세요.');
    } finally {
      setBusy(null);
    }
  }

  async function emailSubmit() {
    setError(null);
    if (!email.includes('@') || password.length < 6) {
      setError('이메일과 6자 이상의 비밀번호를 입력해 주세요.');
      return;
    }
    setBusy('email');
    try {
      const t = mode === 'emailSignup' ? await api.signupEmail(name.trim(), email.trim(), password) : await api.loginEmail(email.trim(), password);
      await signIn(t.access_token, t.user);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '로그인하지 못했어요.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1, backgroundColor: colors.page }}>
      <ScrollView contentContainerStyle={{ flexGrow: 1, alignItems: 'center', justifyContent: 'center', padding: 20 }} keyboardShouldPersistTaps="handled">
        <View
          style={{
            width: '100%',
            maxWidth: 480,
            backgroundColor: colors.surface,
            borderRadius: 24,
            borderWidth: 1,
            borderColor: colors.border,
            paddingHorizontal: 48,
            paddingTop: 40,
            paddingBottom: 36,
            alignItems: 'center',
            ...shadow.card,
          }}
        >
          <Image source={require('../../assets/images/logo-wordmark.png')} style={{ width: 150, height: 50 }} resizeMode="contain" accessibilityLabel="MEMO'S" />
          <T size={26} weight="bold" style={{ marginTop: 12 }}>
            투자 메모를 한 곳에서
          </T>
          <T size={14} color={colors.textSub} style={{ marginTop: 6 }}>
            {mode === 'social' ? '소셜 계정으로 간편하게 시작하세요' : mode === 'emailLogin' ? '이메일로 로그인하세요' : '이메일로 새 계정을 만들어요'}
          </T>

          <View style={{ alignSelf: 'stretch', gap: 12, marginTop: 30 }}>
            {mode === 'social' ? (
              <>
                <SocialButton label="카카오로 로그인" bg="#FEE500" fg="#191919" logo={<KakaoLogo />} loading={busy === 'kakao'} onPress={() => social('kakao')} />
                <SocialButton label="네이버로 로그인" bg="#03A94D" fg="#FFFFFF" logo={<NaverLogo />} loading={busy === 'naver'} onPress={() => social('naver')} />
                <SocialButton label="구글로 로그인" bg="#FFFFFF" fg="#191919" border logo={<GoogleLogo />} loading={busy === 'google'} onPress={() => social('google')} />
              </>
            ) : (
              <>
                {mode === 'emailSignup' && <TextField placeholder="이름" value={name} onChangeText={setName} autoComplete="name" />}
                <TextField placeholder="이메일" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" autoComplete="email" />
                <TextField placeholder="비밀번호 (6자 이상)" value={password} onChangeText={setPassword} secureTextEntry onSubmitEditing={emailSubmit} autoComplete="password" />
                <Button label={mode === 'emailSignup' ? '가입하고 시작하기' : '로그인'} size="lg" onPress={emailSubmit} loading={busy === 'email'} />
              </>
            )}
          </View>

          {error && (
            <T size={13} color={colors.danger} style={{ marginTop: 14 }} align="center">
              {error}
            </T>
          )}

          <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 32, gap: 24 }}>
            {mode === 'social' ? (
              <>
                <TextLink label="이메일 가입" onPress={() => setMode('emailSignup')} />
                <View style={{ width: 1, height: 14, backgroundColor: colors.border }} />
                <TextLink label="이메일 로그인" onPress={() => setMode('emailLogin')} />
              </>
            ) : (
              <TextLink label="← 소셜 로그인으로" onPress={() => setMode('social')} />
            )}
          </View>
        </View>
        {env.useMock && (
          <T size={12} color={colors.textMuted} style={{ marginTop: 16 }}>
            목업 모드 — 아무 버튼이나 누르면 예시 계정(김나라)으로 들어가요
          </T>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function SocialButton({ label, bg, fg, logo, border, onPress, loading }: { label: string; bg: string; fg: string; logo: React.ReactNode; border?: boolean; onPress: () => void; loading?: boolean }) {
  return (
    <Hoverable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={loading ? undefined : onPress}
      style={{
        height: 56,
        borderRadius: 10,
        backgroundColor: bg,
        borderWidth: border ? 1 : 0,
        borderColor: colors.border,
        alignItems: 'center',
        justifyContent: 'center',
        opacity: loading ? 0.7 : 1,
      }}
      hoverStyle={{ opacity: 0.92 }}
    >
      <View style={{ position: 'absolute', left: 24 }}>{logo}</View>
      <T size={16} weight="bold" color={fg} lh={1.2}>
        {loading ? '연결 중…' : label}
      </T>
    </Hoverable>
  );
}

function TextLink({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} hitSlop={8}>
      <T size={14} color={colors.textBody}>
        {label}
      </T>
    </Pressable>
  );
}
