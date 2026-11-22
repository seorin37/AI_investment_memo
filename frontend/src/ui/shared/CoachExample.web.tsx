import React from 'react';
import { env } from '@/config/env';
import { coachExample } from '@/lib/coachTarget';
import { useCoach } from '@/store/coach';
import { COACH_EXAMPLE_HANDLERS, coachExampleMemo } from '@/ui/screens/memo/coachExampleData';
import { WebMemoDialog } from '@/ui/screens/memo/web/MemoDialog';

/**
 * 사용법 안내 ③ 예시 메모 창 (웹 · 2026-11-22).
 * 실제 모드에서 ③에 열 실제 AI 메모가 없을 때(지금은 보드가 mock 'm1' 을 열어 실제 모드에서 빈 화면) 실제 메모 창과 같은 창을
 * AI 업데이트 탭으로 띄운다 — WebMemoDialog 그대로 · mock m1 데이터 · 머리에 '예시' · 동작 없음.
 * 소식 목록(WebFeed)의 'feed' 대상을 안내가 짚는다. ③을 지나거나 안내가 끝나면 닫힘.
 * 루트 레이아웃에서 CoachOverlay 바로 앞에 두어 안내(Modal)가 이 창 위에 붙는다.
 */
export function CoachExample() {
  const step = useCoach((s) => s.step);
  if (!coachExample(step, !env.useMock, true)) return null;
  const data = coachExampleMemo();
  return <WebMemoDialog open {...data} {...COACH_EXAMPLE_HANDLERS} initialTab="ai" badge="예시" />;
}
