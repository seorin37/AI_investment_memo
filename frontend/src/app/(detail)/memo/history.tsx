import React from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { AppMemoHistory } from '@/ui/screens/memo/app/Evidence';
import { useMemoScreen } from '@/ui/screens/memo/useMemoScreen';

/** 앱 수정 이력 = UI v2 (근거 상세의 '연결된 내 메모'에서 열림 · 그 버전이 펼쳐짐). 데이터: useMemoScreen */
export default function MemoHistoryScreen() {
  const { id, v } = useLocalSearchParams<{ id: string; v?: string }>();
  const router = useRouter();
  const { data } = useMemoScreen(id);
  if (!data.memo) return null;
  return <AppMemoHistory memo={data.memo} versions={data.versions} openVersion={v ? Number(v) : undefined} onBack={() => router.back()} />;
}
