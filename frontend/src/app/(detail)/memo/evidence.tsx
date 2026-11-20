import React from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { AppEvidence } from '@/ui/screens/memo/app/Evidence';
import { feedOf, findMemo, versionsOf } from '@/ui/screens/updates/Updates.mock';

/**
 * 앱 근거 상세 = UI v2 (메모 상세 · 업데이트 탭(⑥)에서 밀려 들어옴). mock: 메모 id · 소식 id 로 예시 데이터에서 찾음 (보드 메모 + 다른 종목 메모).
 * [메모 보기] → 메모 상세의 메모 탭 · 연결된 내 메모 → 그 버전 수정 이력 · 원문 열기는 콜백만 (앱 안 브라우저는 연결 단계).
 */
export default function EvidenceScreen() {
  const { id, fid } = useLocalSearchParams<{ id: string; fid: string }>();
  const router = useRouter();
  const notice = useMockNotice();
  const memo = findMemo(id);
  const feed = feedOf(memo.id);
  const item = feed.find((f) => f.id === fid) ?? feed[0];
  if (!item) return null;
  const versions = versionsOf(memo.id);
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
