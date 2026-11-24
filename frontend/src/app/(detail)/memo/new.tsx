import React, { useCallback, useMemo } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { api } from '@/api';
import { env } from '@/config/env';
import { useQueryClient } from '@tanstack/react-query';
import { qk } from '@/hooks/queries';
import { useUI } from '@/store/ui';
import { AppNewMemo } from '@/ui/screens/memo/app/NewMemo';
import { useMarkWatchAdded } from '@/ui/screens/studio/reportView';
import { mockDetailStockName } from '@/ui/screens/memo/MemoDetail.mock';
import { mockFirstHomeStocks } from '@/ui/screens/onboarding/Onboarding.mock';
import { AppFirstMemo } from '@/ui/screens/onboarding/app/FirstMemo';

/**
 * 앱 새 메모 = UI v2. from_onboarding은 기존 저장 API를 바꾸지 않고 복귀 위치만 홈으로 지정한다.
 * 첫 메모(from_onboarding=1)는 원본 start.html #nm 화면(AppFirstMemo) — 머리 종목 칩으로 종목을 바꿀 수 있다.
 */
export default function NewMemoScreen() {
  const { code, name, first_line, body: preBody, ai: preAi, wr, wk, from_onboarding, onboarding_selected } = useLocalSearchParams<{ code?: string; name?: string; first_line?: string; body?: string; ai?: string; wr?: string; wk?: string; from_onboarding?: string; onboarding_selected?: string }>();
  /* 주간보고서 '메모에 추가'(2026-11-24): 제목·본문을 채우고 AI 연결을 켠 채로 연다. 저장하면 보고서에 '추가됨'(wr·wk) */
  const markWatch = useMarkWatchAdded();
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const qc = useQueryClient();
  const cancel = useCallback(() => router.back(), [router]);
  const firstStocks = useMemo(() => (from_onboarding === '1' ? mockFirstHomeStocks(onboarding_selected) : []), [from_onboarding, onboarding_selected]);

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

  return (
    <AppNewMemo
      stockName={name || mockDetailStockName}
      initialText={first_line ? (preBody ? `${first_line}\n${preBody}` : first_line) : undefined}
      initialAi={preAi === '1'}
      onCancel={cancel}
      onEmpty={() => (code ? router.dismissTo({ pathname: '/stocks/[code]', params: { code, notice: 'empty', t: String(Date.now()) } }) : cancel())}
      onSave={({ title, body, color, ai }) => {
        /* 실제 모드(2026-11-22): 일반 메모로 저장 → AI 를 켰으면 그 메모로 AI 연결 창 (창이 열릴 때 켜고 분석) */
        if (!env.useMock && code) {
          void api.createMemo(code, { title, body, color, tags: [], ai_linked: false }).then(
            (m) => {
              void qc.invalidateQueries({ queryKey: qk.board(code) });
              markWatch(wr, wk, m.id);
              if (ai) router.replace({ pathname: '/memo/link', params: { id: m.id, from: 'new' } });
              else router.dismissTo({ pathname: '/stocks/[code]', params: { code, notice: 'saved', t: String(Date.now()) } });
            },
            () => toast('메모를 저장하지 못했어요 · 잠시 뒤 다시 해 주세요'),
          );
          return;
        }
        if (ai) {
          router.replace({ pathname: '/memo/link', params: { id: 'new', title, body, from: 'new' } });
          return;
        }
        if (code) router.dismissTo({ pathname: '/stocks/[code]', params: { code, notice: 'saved', t: String(Date.now()) } });
        else {
          toast('메모를 저장했어요');
          router.back();
        }
      }}
    />
  );
}
