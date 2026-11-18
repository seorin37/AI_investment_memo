import React, { useEffect, useState } from 'react';
import { View } from 'react-native';
import { Redirect, useLocalSearchParams, useRouter } from 'expo-router';
import { Button, Loading } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useAuth } from '@/store/auth';
import { colors } from '@/theme/tokens';

/**
 * 웹 OAuth 콜백. 세션은 HttpOnly 쿠키에 있으므로 URL에는 토큰이 없습니다.
 */
export default function AuthCallback() {
  const { status: callbackStatus, error } = useLocalSearchParams<{ status?: string; error?: string }>();
  const router = useRouter();
  const completeWebLogin = useAuth((s) => s.completeWebLogin);
  const status = useAuth((s) => s.status);
  const [signInError, setSignInError] = useState<string | null>(null);
  const failed = error ?? (callbackStatus !== 'success' ? '로그인 결과를 확인할 수 없어요.' : signInError);

  useEffect(() => {
    if (callbackStatus === 'success' && status !== 'signedIn') completeWebLogin().catch(() => setSignInError('로그인 정보를 확인하지 못했어요.'));
  }, [callbackStatus, status, completeWebLogin]);

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
