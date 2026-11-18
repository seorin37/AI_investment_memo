import React, { useEffect, useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { MobileScreen } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { AiLinkConfirm } from '@/features/board/AiLinkConfirm';
import { mockAiLinkConfirmProps } from '@/features/board/AiLinkConfirm.mock';
import type { AiLinkStep } from '@/features/board/AiLinkConfirm.types';
import { useUI } from '@/store/ui';

/**
 * AI 연결 확인 (아래에서 올라옴). mock 단계: 찾는 중 0.9초 → mock 후보.
 * 다음 단계: PUT /memos/{id}/ai-link 의 analysis.items 를 후보로 (서버가 항목을 정함 · 웹과 같은 제약).
 */
export default function AiLinkScreen() {
  const { title, body } = useLocalSearchParams<{ title?: string; body?: string }>();
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const [step, setStep] = useState<AiLinkStep>('scanning');
  const [candidates, setCandidates] = useState(mockAiLinkConfirmProps.candidates);
  useEffect(() => {
    const t = setTimeout(() => setStep('select'), 900);
    return () => clearTimeout(t);
  }, []);
  const memo = title ? { ...mockAiLinkConfirmProps.memo, title, body: body ?? '' } : mockAiLinkConfirmProps.memo;
  return (
    <MobileScreen bg="#FFFFFF" bar={<TopBar left="cancel" title="AI 연결" onCancel={() => router.back()} />}>
      <AiLinkConfirm
        {...mockAiLinkConfirmProps}
        step={step}
        memo={memo}
        candidates={candidates}
        onToggleCandidate={(id) => setCandidates((all) => all.map((c) => (c.id === id ? { ...c, selected: !c.selected } : c)))}
        onConnect={() => { toast('AI 연결을 켰어요 (예시)'); router.back(); }}
        onLater={() => router.back()}
        onEditMemo={() => router.back()}
      />
    </MobileScreen>
  );
}
