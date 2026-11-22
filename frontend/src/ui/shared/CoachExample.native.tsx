import React from 'react';
import { StyleSheet, View } from 'react-native';
import { env } from '@/config/env';
import { coachExample } from '@/lib/coachTarget';
import { useCoach } from '@/store/coach';
import { COACH_EXAMPLE_HANDLERS, coachExampleMemo } from '@/ui/screens/memo/coachExampleData';
import { AppMemoDetail } from '@/ui/screens/memo/app/MemoDetail';
import { appColor } from '@/ui/theme';

/**
 * 사용법 안내 ②③ 예시 메모 화면 (앱 · 2026-11-22).
 * 앱 안내는 ②③에서 /memo/m1 로 가는데 실제 모드에서는 'm1' 을 조회하지 않아 빈 화면 → 그 위에 실제 메모 상세와 같은 화면
 * (AppMemoDetail 그대로 · mock m1 · AI 업데이트 탭 · 머리에 '예시')을 덮는다. 손으로 누를 수 없음(pointerEvents none).
 * MemoFeed 의 'ai' · 'feed' 대상을 안내가 짚는다. ②③을 지나거나 안내가 끝나면 사라짐.
 * 루트 레이아웃에서 CoachOverlay 바로 앞에 두어 안내가 이 화면 위에 그려진다.
 */
export function CoachExample() {
  const step = useCoach((s) => s.step);
  if (!coachExample(step, !env.useMock, false)) return null;
  const data = coachExampleMemo();
  return (
    <View pointerEvents="none" style={[StyleSheet.absoluteFill, st.cover]}>
      <AppMemoDetail {...data} {...COACH_EXAMPLE_HANDLERS} initialTab="ai" badge="예시" />
    </View>
  );
}

const st = StyleSheet.create({ cover: { backgroundColor: appColor.bg } });
