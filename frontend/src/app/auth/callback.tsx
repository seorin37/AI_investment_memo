import React, { useEffect, useState } from 'react';
import { View } from 'react-native';
import { Redirect, useLocalSearchParams, useRouter } from 'expo-router';
import { Button, Loading } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useAuth } from '@/store/auth';
import { colors } from '@/theme/tokens';

/**
 * 소셜 로그인 콜백 — FastAPI 가 `/auth/callback?token=<JWT>` 로 리다이렉트합니다.
 * (실패 시 `?error=메시지`)
 */
export default function AuthCallback() {
  const { token, error } = useLocalSearchParams<{ token?: string; error?: string }>();
  const router = useRouter();
  const signIn = useAuth((s) => s.signIn);
  const status = useAuth((s) => s.status);
  const [signInError, setSignInError] = useState<string | null>(null);
  const failed = error ?? (!token ? '로그인 토큰이 없어요.' : signInError);

  useEffect(() => {
    if (token && status !== 'signedIn') signIn(token).catch(() => setSignInError('로그인 정보를 확인하지 못했어요.'));
  }, [token, status, signIn]);

  if (status === 'signedIn') return <Redirect href="/" />;
  if (failed)
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: colors.page }}>
        <T size={16} weight="semibold">
          로그인하지 못했어요
        </T>
        <T size={13} color={colors.textSub}>
          {failed}
        </T>
        <Button label="로그인 화면으로" variant="outline" onPress={() => router.replace('/login')} />
      </View>
    );
  return <Loading height={400} />;
}
