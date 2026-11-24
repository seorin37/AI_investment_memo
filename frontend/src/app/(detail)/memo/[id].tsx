import React, { useState } from 'react';
import { Linking } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import type { MemoVersion } from '@/types/models';
import { AppMemoDetail } from '@/ui/screens/memo/app/MemoDetail';
import { mockToday } from '@/ui/screens/memo/MemoDetail.mock';
import { useMemoScreen } from '@/ui/screens/memo/useMemoScreen';
import { useUsageView } from '@/ui/screens/my/useUsageView';

/**
 * 앱 메모 상세 = UI v2 (ui/screens/memo/app).
 * 데이터: useMemoScreen — 실제 모드면 GET board-item · timeline, 저장 · 색 · 고정 · 삭제 · AI 끄기를 API 로 (2026-11-22).
 * mock 모드: 보드 예시 메모(m1~m5)를 id 로 찾아 보여 주고, 바꾼 내용은 이 화면 안에서만.
 * AI 연결 켜기 → AI 연결 창 (/memo/link).
 */
export default function MemoDetailScreen() {
  const { id, tab, t } = useLocalSearchParams<{ id: string; tab?: string; t?: string }>();
  const router = useRouter();
  const notice = useMockNotice();
  const { data, ops, setMockMemo } = useMemoScreen(id);
  /* AI 사용량을 다 쓰면 안내 상자 (스튜디오와 같은 기준: 정지 또는 100% 이상, 2026-11-24) */
  const usage = useUsageView();
  /* mock 모드에서만 쓰는 화면 안 상태 (수정 이력 · 소식 읽음) */
  const [mockVersions, setMockVersions] = useState<MemoVersion[] | null>(null);
  const [mockSeen, setMockSeen] = useState(false);
  const memo = data.memo;
  if (!memo) return null;
  const versions = ops ? data.versions : mockVersions ?? data.versions;
  const feed = ops || !mockSeen ? data.feed : data.feed.map((x) => ({ ...x, unread: false }));
  const patch = (p: Partial<typeof memo>) => setMockMemo((m) => (m ? { ...m, ...p } : m));
  return (
    <AppMemoDetail
      memo={memo}
      stockName={data.stockName}
      versions={versions}
      feed={feed}
      trackItems={data.trackItems}
      lastChecked={data.lastChecked}
      initialTab={tab === 'ai' ? 'ai' : 'memo'}
      tabRequest={t ? { tab: tab === 'ai' ? 'ai' : 'memo', key: t } : undefined}
      onBack={() => router.back()}
      onSave={({ title, body }) => {
        if (ops) return ops.save({ title, body });
        setMockVersions([{ version: (versions[0]?.version ?? 0) + 1, title, body, saved_at: mockToday }, ...versions]);
        patch({ title, body, updated_at: mockToday });
      }}
      onChangeColor={(color) => (ops ? ops.color(color) : patch({ color }))}
      onTogglePin={(pinned) => (ops ? ops.pin(pinned) : patch({ pinned }))}
      onDelete={() => {
        if (ops) void ops.remove().finally(() => router.back());
        else router.back();
      }}
      onCopy={() => {}}
      onConnectAi={() => router.push({ pathname: '/memo/link', params: { id: memo.id } })}
      onDisconnectAi={() => (ops ? void ops.aiOff() : patch({ ai_linked: false }))}
      onSeenUpdates={() => (ops ? ops.seenUpdates() : setTimeout(() => setMockSeen(true), 4000))}
      onOpenSource={(f) => (f.url ? Linking.openURL(f.url) : notice('원문 열기'))}
      onOpenEvidence={(f) => router.push({ pathname: '/memo/evidence', params: { id: memo.id, fid: f.id } })}
      onNudge={() => notice('주간보고서')}
      aiSpent={memo.ai_linked && (usage.paused || usage.usage_pct >= 100)}
      aiRefill={usage.usage_refill}
      onSpentAction={(a) => router.push(a === 'credit' ? '/studio-charge' : '/my-plans')}
    />
  );
}
