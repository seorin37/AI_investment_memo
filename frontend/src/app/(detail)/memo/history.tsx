import React from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { AppMemoHistory } from '@/ui/screens/memo/app/Evidence';
import { mockMemoById, mockVersions } from '@/ui/screens/memo/MemoDetail.mock';

/** 앱 수정 이력 = UI v2 (근거 상세의 '연결된 내 메모'에서 열림 · 그 버전이 펼쳐짐). mock 단계 */
export default function MemoHistoryScreen() {
  const { id, v } = useLocalSearchParams<{ id: string; v?: string }>();
  const router = useRouter();
  const memo = mockMemoById(id);
  return <AppMemoHistory memo={memo} versions={mockVersions[memo.id] ?? []} openVersion={v ? Number(v) : undefined} onBack={() => router.back()} />;
}
