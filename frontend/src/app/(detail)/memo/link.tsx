import React, { useCallback, useEffect, useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import type { MemoColor } from '@/types/models';
import { AppAiLink } from '@/ui/screens/memo/app/AiLink';
import type { AiLinkState } from '@/ui/screens/memo/MemoDetail.types';
import { mockDetailStockName, mockExtract, mockMemoById, mockTrackItems } from '@/ui/screens/memo/MemoDetail.mock';

/**
 * 앱 AI 연결 창 = UI v2 (아래에서 올라옴). mock 단계: 분석 중 1.2초 (새 메모면 1.7초) → 항목 있음 / 항목 없음.
 * ?fail=1 이면 분석 실패 화면 (다시 시도 → 분석 중 → 항목). 항목은 서버가 정함 (읽기 전용) — 다음 단계: PUT /memos/{id}/ai-link 의 analysis.items.
 */
export default function AiLinkScreen() {
  const { id, title, body, from, fail, from_onboarding, onboarding_selected } = useLocalSearchParams<{ id?: string; title?: string; body?: string; from?: string; fail?: string; from_onboarding?: string; onboarding_selected?: string }>();
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const isNew = !id || id === 'new';
  const base = isNew ? null : mockMemoById(id);
  const memo = { title: base?.title ?? title ?? '', body: base?.body ?? body ?? '', color: (base?.color ?? 'yellow') as MemoColor };
  const items = isNew ? mockExtract(memo.title, memo.body) : (mockTrackItems[id] ?? []);
  const [state, setState] = useState<AiLinkState>('loading');
  const [failed, setFailed] = useState(fail === '1');
  useEffect(() => {
    if (state !== 'loading') return;
    const t = setTimeout(() => setState(failed ? 'error' : items.length ? 'items' : 'empty'), from === 'new' ? 1700 : 1200);
    return () => clearTimeout(t);
  }, [state, failed, items.length, from]);
  const cancel = useCallback(() => {
    if (from === 'new') toast('일반 메모로 저장했어요 · AI 연결은 나중에 켤 수 있어요');
    if (from_onboarding === '1') { router.dismissTo({ pathname: '/', params: { onboarding: 'first_saved', selected: onboarding_selected ?? '' } }); return; }
    router.back();
  }, [from, from_onboarding, onboarding_selected, router, toast]);
  const confirm = useCallback(() => {
    toast('이제 AI가 이 메모를 지켜봐요');
    if (from_onboarding === '1') { router.dismissTo({ pathname: '/', params: { onboarding: 'first_saved', selected: onboarding_selected ?? '' } }); return; }
    router.back();
  }, [from_onboarding, onboarding_selected, router, toast]);
  return (
    <AppAiLink
      stockName={mockDetailStockName}
      memo={memo}
      state={state}
      items={items}
      fromNew={from === 'new'}
      onConfirm={confirm}
      onCancel={cancel}
      onEditMemo={() => (isNew ? router.back() : router.replace({ pathname: '/memo/[id]', params: { id: id! } }))}
      onRetry={() => {
        setFailed(false);
        setState('loading');
      }}
    />
  );
}
