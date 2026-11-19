import React, { useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import type { Memo, MemoVersion } from '@/types/models';
import { AppMemoDetail } from '@/ui/screens/memo/app/MemoDetail';
import { mockDetailStockName, mockFeed, mockLastChecked, mockMemoById, mockToday, mockTrackItems, mockVersions } from '@/ui/screens/memo/MemoDetail.mock';

/**
 * 앱 메모 상세 = UI v2 (ui/screens/memo/app). mock 단계: 보드 예시 메모(m1~m5)를 id 로 찾아 보여 주고, 바꾼 내용은 이 화면 안에서만.
 * AI 연결 켜기 → AI 연결 창 (/memo/link) · 근거 상세 · 원문 · 주간보고서 넛지는 다음 묶음.
 */
export default function MemoDetailScreen() {
  const { id, tab, t } = useLocalSearchParams<{ id: string; tab?: string; t?: string }>();
  const router = useRouter();
  const notice = useMockNotice();
  const [memo, setMemo] = useState<Memo>(() => mockMemoById(id));
  const [versions, setVersions] = useState<MemoVersion[]>(() => mockVersions[memo.id] ?? []);
  const [feed, setFeed] = useState(() => mockFeed[memo.id] ?? []);
  return (
    <AppMemoDetail
      memo={memo}
      stockName={mockDetailStockName}
      versions={versions}
      feed={feed}
      trackItems={mockTrackItems[memo.id] ?? []}
      lastChecked={mockLastChecked}
      initialTab={tab === 'ai' ? 'ai' : 'memo'}
      tabRequest={t ? { tab: tab === 'ai' ? 'ai' : 'memo', key: t } : undefined}
      onBack={() => router.back()}
      onSave={({ title, body }) => {
        setVersions((v) => [{ version: (v[0]?.version ?? 0) + 1, title, body, saved_at: mockToday }, ...v]);
        setMemo((m) => ({ ...m, title, body, updated_at: mockToday }));
      }}
      onChangeColor={(color) => setMemo((m) => ({ ...m, color }))}
      onTogglePin={(pinned) => setMemo((m) => ({ ...m, pinned }))}
      onDelete={() => router.back()}
      onCopy={() => {}}
      onConnectAi={() => router.push({ pathname: '/memo/link', params: { id: memo.id } })}
      onDisconnectAi={() => setMemo((m) => ({ ...m, ai_linked: false }))}
      onSeenUpdates={() => setTimeout(() => setFeed((f) => f.map((x) => ({ ...x, unread: false }))), 4000)}
      onOpenSource={() => notice('원문 열기')}
      onOpenEvidence={(f) => router.push({ pathname: '/memo/evidence', params: { id: memo.id, fid: f.id } })}
      onNudge={() => notice('주간보고서')}
      onSpentAction={(a) => notice(a === 'credit' ? '크레딧 구매' : '플랜 변경')}
    />
  );
}
