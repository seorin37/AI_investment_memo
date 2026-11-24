import React from 'react';
import { Linking } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { AppEvidence } from '@/ui/screens/memo/app/Evidence';
import { useMemoScreen } from '@/ui/screens/memo/useMemoScreen';

/**
 * 앱 근거 상세 = UI v2 (메모 상세 · 업데이트 탭(⑥)에서 밀려 들어옴). 데이터: useMemoScreen (실제 모드면 timeline 의 소식 · 이력).
 * [메모 보기] → 메모 상세의 메모 탭 · 연결된 내 메모 → 그 버전 수정 이력 · 원문은 링크가 있으면 브라우저.
 */
export default function EvidenceScreen() {
  const { id, fid } = useLocalSearchParams<{ id: string; fid: string }>();
  const router = useRouter();
  const notice = useMockNotice();
  const { data } = useMemoScreen(id);
  const memo = data.memo;
  const item = data.feed.find((f) => f.id === fid) ?? data.feed[0];
  if (!memo || !item) return null;
  return (
    <AppEvidence
      item={item}
      memo={memo}
      version={data.versions.find((v) => v.version === item.memo_version)}
      onBack={() => router.back()}
      onShowMemo={() => router.dismissTo({ pathname: '/memo/[id]', params: { id: memo.id, tab: 'memo', t: String(Date.now()) } })}
      onOpenSource={(f) => (f.url ? Linking.openURL(f.url) : notice('원문 열기'))}
      onOpenHistory={(v) => router.push({ pathname: '/memo/history', params: { id: memo.id, v: String(v) } })}
    />
  );
}
