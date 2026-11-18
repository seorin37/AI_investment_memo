import React, { useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { MobileScreen, useMockNotice } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { MemoDetail } from '@/features/board/MemoDetail';
import { mockMemoDetailProps } from '@/features/board/MemoDetail.mock';
import type { MemoDetailTab } from '@/features/board/MemoDetail.types';
import { useBackClose } from '@/hooks/useBackClose';
import { joinMemo, splitMemo } from '@/lib/memoText';
import { useUI } from '@/store/ui';

/** 메모 상세 (메모 · AI 업데이트 탭). 편집은 한 칸 글 → 저장할 때 웹과 같은 규칙으로 제목 · 본문 (lib/memoText). mock 단계 */
export default function MemoDetailScreen() {
  const { tab: tabParam } = useLocalSearchParams<{ id: string; tab?: string }>();
  const router = useRouter();
  const notice = useMockNotice();
  const toast = useUI((s) => s.showToast);
  const [tab, setTab] = useState<MemoDetailTab>(tabParam === 'ai' ? 'ai' : 'memo');
  const [memo, setMemo] = useState(mockMemoDetailProps.memo);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  /* 안드로이드 뒤로가기: 편집 중이면 편집 취소가 먼저 */
  useBackClose(() => {
    if (editing) { setEditing(false); return true; }
    return false;
  });
  const save = () => {
    const { title, body } = splitMemo(draft);
    setMemo((m) => ({ ...m, title, body }));
    setEditing(false);
    toast(`저장했어요 (예시) · 제목 "${title}"`);
  };
  return (
    <MobileScreen
      bar={
        <TopBar
          left="back"
          title="메모 보드"
          onBack={() => (editing ? setEditing(false) : router.back())}
          actions={editing ? [{ kind: 'text', label: '완료', emphasis: true, onPress: save }] : []}
        />
      }
    >
      <MemoDetail
        {...mockMemoDetailProps}
        memo={memo}
        tab={tab}
        onChangeTab={setTab}
        editing={editing}
        draft={draft}
        onStartEdit={() => { setDraft(joinMemo(memo.title, memo.body)); setEditing(true); }}
        onChangeDraft={setDraft}
        onOpenEvidence={() => notice('근거 보기')}
        onOpenOriginal={() => notice('원문 열기')}
        onToggleAi={() => (memo.ai_linked ? notice('AI 연결 끄기') : router.push({ pathname: '/memo/link', params: { title: memo.title, body: memo.body } }))}
        onOpenHistory={() => notice('메모 이력')}
      />
    </MobileScreen>
  );
}
