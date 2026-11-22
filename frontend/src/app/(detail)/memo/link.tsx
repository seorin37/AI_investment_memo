import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import type { MemoColor } from '@/types/models';
import { AppAiLink } from '@/ui/screens/memo/app/AiLink';
import type { AiLinkState, AiTrackItem } from '@/ui/screens/memo/MemoDetail.types';
import { mockDetailStockName, mockExtract, mockMemoById, mockTrackItems } from '@/ui/screens/memo/MemoDetail.mock';
import { useMemoScreen } from '@/ui/screens/memo/useMemoScreen';

/**
 * 앱 AI 연결 창 = UI v2 (아래에서 올라옴). mock 단계: 분석 중 1.2초 (새 메모면 1.7초) → 항목 있음 / 항목 없음.
 * ?fail=1 이면 분석 실패 화면 (다시 시도 → 분석 중 → 항목). 항목은 서버가 정함 (읽기 전용).
 * 실제 모드(2026-11-22, 결정 7 임시안 '저장 = 켜기'): 창이 열릴 때 PUT ai-link(켜기) → analysis.items, '일반 메모로 두기' = 끄기.
 */
export default function AiLinkScreen() {
  const { id, title, body, from, fail, from_onboarding, onboarding_selected, stock_name, first_code, first_title, first_body } = useLocalSearchParams<{ id?: string; title?: string; body?: string; from?: string; fail?: string; from_onboarding?: string; onboarding_selected?: string; stock_name?: string; first_code?: string; first_title?: string; first_body?: string }>();
  /* 첫 메모 흐름: 홈(첫 홈)으로 돌아가며 고른 종목과 저장한 메모 요약을 넘긴다 */
  const homeParams = useMemo(
    () => ({ onboarding: 'first_saved', selected: onboarding_selected ?? '', first_code: first_code ?? '', first_title: first_title ?? title ?? '', first_body: first_body ?? body ?? '' }),
    [onboarding_selected, first_code, first_title, first_body, title, body],
  );
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const isNew = !id || id === 'new';
  const screen = useMemoScreen(isNew ? '' : id!);
  const real = !!screen.ops && !isNew; // 첫 메모(온보딩) 흐름의 id='new' 는 아직 mock
  const base = isNew ? null : real ? screen.data.memo : mockMemoById(id);
  const memo = { title: base?.title ?? title ?? '', body: base?.body ?? body ?? '', color: (base?.color ?? 'yellow') as MemoColor };
  const [realItems, setRealItems] = useState<AiTrackItem[]>([]);
  const items = real ? realItems : isNew ? mockExtract(memo.title, memo.body) : (mockTrackItems[id] ?? []);
  const [state, setState] = useState<AiLinkState>('loading');
  const [failed, setFailed] = useState(__DEV__ && fail === '1');
  /* 실제 모드: 분석 중 동안 AI 켜기 → 분석 결과 */
  const [asked, setAsked] = useState(0);
  const [askedFor, setAskedFor] = useState(-1);
  if (real && state === 'loading' && askedFor !== asked) {
    setAskedFor(asked);
    void screen.ops!.aiOn().then((r) => {
      setRealItems(r.items);
      setState(r.state);
    });
  }
  useEffect(() => {
    if (real || state !== 'loading') return;
    const t = setTimeout(() => setState(failed ? 'error' : items.length ? 'items' : 'empty'), from === 'new' ? 1700 : 1200);
    return () => clearTimeout(t);
  }, [real, state, failed, items.length, from]);
  const cancel = useCallback(() => {
    if (real) void screen.ops!.aiOff();
    if (from === 'new') toast('일반 메모로 저장했어요 · AI 연결은 나중에 켤 수 있어요');
    if (from_onboarding === '1') { router.dismissTo({ pathname: '/', params: { ...homeParams, first_ai: '0' } }); return; }
    router.back();
  }, [real, screen.ops, from, from_onboarding, homeParams, router, toast]);
  const confirm = useCallback(() => {
    toast('이제 AI가 이 메모를 지켜봐요');
    if (from_onboarding === '1') { router.dismissTo({ pathname: '/', params: { ...homeParams, first_ai: '1' } }); return; }
    router.back();
  }, [from_onboarding, homeParams, router, toast]);
  return (
    <AppAiLink
      stockName={stock_name || (real ? screen.data.stockName : mockDetailStockName)}
      memo={memo}
      state={state}
      items={items}
      fromNew={from === 'new'}
      onConfirm={confirm}
      onCancel={cancel}
      onEditMemo={() => (isNew ? router.back() : router.replace({ pathname: '/memo/[id]', params: { id: id! } }))}
      onRetry={() => {
        setFailed(false);
        setAsked((n) => n + 1);
        setState('loading');
      }}
    />
  );
}
