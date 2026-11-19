import React from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { AppEvidence } from '@/ui/screens/memo/app/Evidence';
import { mockFeed, mockMemoById, mockVersions } from '@/ui/screens/memo/MemoDetail.mock';

/**
 * 앱 근거 상세 = UI v2 (메모 상세 위로 밀려 들어옴). mock: 메모 id · 소식 id 로 예시 데이터에서 찾음.
 * [메모 보기] → 메모 상세의 메모 탭 · 연결된 내 메모 → 그 버전 수정 이력 · 원문 열기는 콜백만 (앱 안 브라우저는 연결 단계).
 */
export default function EvidenceScreen() {
  const { id, fid } = useLocalSearchParams<{ id: string; fid: string }>();
  const router = useRouter();
  const notice = useMockNotice();
  const memo = mockMemoById(id);
  const feed = mockFeed[memo.id] ?? [];
  const item = feed.find((f) => f.id === fid) ?? feed[0];
  if (!item) return null;
  const versions = mockVersions[memo.id] ?? [];
  return (
    <AppEvidence
      item={item}
      memo={memo}
      version={versions.find((v) => v.version === item.memo_version)}
      onBack={() => router.back()}
      onShowMemo={() => router.dismissTo({ pathname: '/memo/[id]', params: { id: memo.id, tab: 'memo', t: String(Date.now()) } })}
      onOpenSource={() => notice('원문 열기')}
      onOpenHistory={(v) => router.push({ pathname: '/memo/history', params: { id: memo.id, v: String(v) } })}
    />
  );
}
