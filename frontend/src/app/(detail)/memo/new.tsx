import React, { useCallback } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { AppNewMemo } from '@/ui/screens/memo/app/NewMemo';
import { mockDetailStockName } from '@/ui/screens/memo/MemoDetail.mock';

/**
 * 앱 새 메모 = UI v2. from_onboarding은 기존 저장 API를 바꾸지 않고 복귀 위치만 홈으로 지정한다.
 */
export default function NewMemoScreen() {
  const { code, name, first_line, from_onboarding } = useLocalSearchParams<{ code?: string; name?: string; first_line?: string; from_onboarding?: string }>();
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const cancel = useCallback(() => router.back(), [router]);
  const finishFirst = () => router.dismissTo({ pathname: '/', params: { onboarding: 'first_saved' } });
  return (
    <AppNewMemo
      stockName={name || mockDetailStockName}
      initialText={first_line || undefined}
      onCancel={cancel}
      onEmpty={() => from_onboarding === '1' ? router.dismissTo('/') : (code ? router.dismissTo({ pathname: '/stocks/[code]', params: { code, notice: 'empty', t: String(Date.now()) } }) : cancel())}
      onSave={({ title, body, ai }) => {
        if (ai) {
          router.replace({ pathname: '/memo/link', params: { id: 'new', title, body, from: 'new', from_onboarding } });
          return;
        }
        if (from_onboarding === '1') finishFirst();
        else if (code) router.dismissTo({ pathname: '/stocks/[code]', params: { code, notice: 'saved', t: String(Date.now()) } });
        else {
          toast('메모를 저장했어요');
          router.back();
        }
      }}
    />
  );
}
