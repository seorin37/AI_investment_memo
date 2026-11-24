import React, { useState } from 'react';
import { Platform } from 'react-native';
import { Redirect, useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { api } from '@/api';
import { env } from '@/config/env';
import { routeAfterLogin, type AfterLoginRoute } from '@/lib/afterLogin';
import { startSocialLogin } from '@/lib/oauth';
import { useAuth } from '@/store/auth';
import type { LoginErrorKind } from '@/ui/screens/auth/Auth.types';
import { AppLogin } from '@/ui/screens/auth/app/Login';
import { WebLogin } from '@/ui/screens/auth/web/Login';
import type { AuthProvider } from '@/types/models';

function networkFailure(error: unknown): boolean {
  if (error instanceof TypeError) return true;
  const message = error instanceof Error ? error.message.toLowerCase() : '';
  return message.includes('network') || message.includes('internet') || message.includes('fetch');
}

export default function LoginScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ demo?: string; recent?: AuthProvider }>();
  const status = useAuth((s) => s.status);
  const acceptSession = useAuth((s) => s.acceptSession);
  const mockSignIn = useAuth((s) => s.mockSignIn);
  /* ?demo= 는 화면 상태 확인용 — 개발 빌드에서만 */
  const demo = __DEV__ ? params.demo : undefined;
  const [busy, setBusy] = useState<AuthProvider | null>(() => demo === 'loading' ? 'kakao' : null);
  const [error, setError] = useState<LoginErrorKind>(() => demo === 'offline' ? 'network' : demo === 'error' ? 'login' : null);
  const [recent, setRecent] = useState<AuthProvider | null>(params.recent ?? null);
  /* 버튼으로 로그인한 뒤 갈 곳: 약관 동의 판별(lib/afterLogin · GET /me/terms) 결과. 판별 중이면 'deciding' */
  const [next, setNext] = useState<AfterLoginRoute | 'deciding' | null>(null);

  if (status === 'signedIn') {
    if (next === 'deciding') return null;
    return <Redirect href={(next ?? '/') as Href} />;
  }

  async function social(provider: AuthProvider) {
    if (busy) return;
    setError(null);
    setBusy(provider);
    setRecent(provider);
    try {
      if (env.useMockAuth) {
        setNext('deciding');
        await mockSignIn();
        setNext(await routeAfterLogin(api.getTerms));
        return;
      }
      const session = await startSocialLogin(provider);
      if (session) {
        setNext('deciding');
        await acceptSession(session);
        setNext(await routeAfterLogin(api.getTerms));
      }
    } catch (cause) {
      setNext(null);
      setError(networkFailure(cause) ? 'network' : 'login');
    } finally {
      setBusy(null);
    }
  }

  const props = {
    busy,
    error,
    recent_provider: recent,
    onLogin: (provider: AuthProvider) => void social(provider),
    onRetry: () => setError(null),
    onIntro: () => router.replace('/intro'),
  };
  return Platform.OS === 'web' ? <WebLogin {...props} /> : <AppLogin {...props} />;
}
