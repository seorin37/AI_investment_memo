import React, { useCallback } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { AppNewMemo } from '@/ui/screens/memo/app/NewMemo';
import { mockDetailStockName } from '@/ui/screens/memo/MemoDetail.mock';

/**
 * 앱 새 메모 = UI v2 (아래에서 올라옴). 첫 줄 = 제목 (splitMemo). mock 단계: 저장하지 않고 알림만.
 * AI 연결을 켜고 저장하면 AI 연결 창으로 (원본 saveNew → openAIF(fromNew)).
 */
export default function NewMemoScreen() {
  const { name, first_line } = useLocalSearchParams<{ code?: string; name?: string; first_line?: string }>();
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const cancel = useCallback(() => router.back(), [router]);
  return (
    <AppNewMemo
      stockName={name || mockDetailStockName}
      initialText={first_line || undefined}
      onCancel={cancel}
      onSave={({ title, body, ai }) => {
        if (ai) {
          router.replace({ pathname: '/memo/link', params: { id: 'new', title, body, from: 'new' } });
          return;
        }
        toast('메모를 저장했어요');
        router.back();
      }}
    />
  );
}
