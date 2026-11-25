import React, { useState } from 'react';
import { Linking, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { AppEvidence } from '@/ui/screens/memo/app/Evidence';
import { NewMemoSheet, type NewMemoTarget } from '@/ui/screens/memo/app/NewMemoSheet';
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
  const [memoTo, setMemoTo] = useState<NewMemoTarget | null>(null);
  const memo = data.memo;
  const item = data.feed.find((f) => f.id === fid) ?? data.feed[0];
  if (!memo || !item) return null;
  return (
    <View style={{ flex: 1 }}>
    <AppEvidence
      item={item}
      memo={memo}
      version={data.versions.find((v) => v.version === item.memo_version)}
      onBack={() => router.back()}
      onShowMemo={() => router.dismissTo({ pathname: '/memo/[id]', params: { id: memo.id, tab: 'memo', t: String(Date.now()) } })}
      onOpenSource={(f) => (f.url ? Linking.openURL(f.url) : notice('원문 열기'))}
      onOpenHistory={(v) => router.push({ pathname: '/memo/history', params: { id: memo.id, v: String(v) } })}
      /* 답 카드 [알림 받기] (2026-11-25): 이 종목 새 메모를 글을 채우고 AI 연결을 켠 채로 연다. 저장하면 평소처럼 가격 알림이 잡힌다.
         앱은 이동하지 않고 시트로 열고, 저장 뒤 흐름은 '메모에 추가'와 같음 */
      onSuggestMemo={(text) => setMemoTo({ code: memo.stock_code, name: data.stockName, text, ai: true, studio: {} })}
    />
    <NewMemoSheet target={memoTo} onClose={() => setMemoTo(null)} />
    </View>
  );
}
