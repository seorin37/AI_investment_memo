import React, { useCallback, useMemo } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { NewMemoSheet } from '@/ui/screens/memo/app/NewMemoSheet';
import { mockBoardStock } from '@/ui/screens/board/MemoBoard.mock';
import { mockDetailStockName } from '@/ui/screens/memo/MemoDetail.mock';
import { mockFirstHomeStocks } from '@/ui/screens/onboarding/Onboarding.mock';
import { AppFirstMemo } from '@/ui/screens/onboarding/app/FirstMemo';

/**
 * 앱 새 메모 = UI v2. from_onboarding은 기존 저장 API를 바꾸지 않고 복귀 위치만 홈으로 지정한다.
 * 첫 메모(from_onboarding=1)는 원본 start.html #nm 화면(AppFirstMemo) — 머리 종목 칩으로 종목을 바꿀 수 있다.
 */
export default function NewMemoScreen() {
  const { code, name, first_line, from_onboarding, onboarding_selected } = useLocalSearchParams<{ code?: string; name?: string; first_line?: string; from_onboarding?: string; onboarding_selected?: string }>();
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const cancel = useCallback(() => router.back(), [router]);
  const firstStocks = useMemo(() => (from_onboarding === '1' ? mockFirstHomeStocks(onboarding_selected) : []), [from_onboarding, onboarding_selected]);

  const target = useMemo(() => ({ code: code || mockBoardStock.stock_code, name: name || mockDetailStockName, text: first_line || undefined }), [code, name, first_line]);

  if (from_onboarding === '1') {
    return (
      <AppFirstMemo
        stocks={firstStocks}
        stock_code={code ?? firstStocks[0]?.stock_code ?? ''}
        onCancel={cancel}
        onEmpty={() => {
          /* 원본: 빈 메모는 저장하지 않고 닫기 → 첫 홈(선택값 그대로)으로 */
          toast('빈 메모는 저장하지 않았어요');
          router.back();
        }}
        onSave={({ stock, title, body, ai }) => {
          const first = { first_code: stock.stock_code, first_title: title, first_body: body };
          if (ai) {
            router.replace({ pathname: '/memo/link', params: { id: 'new', title, body, from: 'new', from_onboarding, onboarding_selected, stock_name: stock.name, ...first } });
            return;
          }
          toast('메모를 저장했어요 · AI 연결은 나중에 켤 수 있어요');
          router.dismissTo({ pathname: '/', params: { onboarding: 'first_saved', selected: onboarding_selected ?? '', ...first, first_ai: '0' } });
        }}
      />
    );
  }

  /* 그 밖의 새 메모는 각 화면의 NewMemoSheet — 주소로 바로 들어온 경우 */
  return <NewMemoSheet target={target} onClose={cancel} />;
}
