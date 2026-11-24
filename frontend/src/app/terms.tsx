import React, { useEffect, useState } from 'react';
import { Platform } from 'react-native';
import { Redirect, useLocalSearchParams, useRouter } from 'expo-router';
import { api } from '@/api';
import { routeAfterTerms } from '@/lib/afterLogin';
import { useAuth } from '@/store/auth';
import type { TermsItem } from '@/types/models';
import { checkedTerms, emptyTermChecks, legalDocument, mockTerms } from '@/ui/screens/auth/Auth.mock';
import type { LegalKey, TermKey } from '@/ui/screens/auth/Auth.types';
import { AppTerms } from '@/ui/screens/auth/app/Terms';
import { WebTerms } from '@/ui/screens/auth/web/Terms';

const SAVE_ERROR = '저장하지 못했어요. 다시 시도해 주세요.';

/**
 * 약관 동의 (2026-11-22). 동의는 POST /me/terms (서버가 준 required 그대로 · 버전은 서버만 가짐).
 * 이미 다 동의했으면 / 로 (뒤로가기 · 주소 직접 입력). 동의 뒤 갈 곳은 lib/afterLogin routeAfterTerms.
 */
export default function TermsScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ demo?: string; doc?: LegalKey }>();
  const status = useAuth((s) => s.status);
  const signOut = useAuth((s) => s.signOut);
  /* ?demo= 는 화면 상태 확인용 — 개발 빌드에서만 */
  const demo = __DEV__ ? params.demo : undefined;
  const [checked, setChecked] = useState<Record<TermKey, boolean>>(() => demo === 'all' ? checkedTerms : emptyTermChecks);
  const [documentKey, setDocumentKey] = useState<LegalKey | null>(params.doc ?? null);
  const [leaveOpen, setLeaveOpen] = useState(demo === 'leave');
  /* 서버의 현재 필수 약관 (버전 포함). 못 받았으면 동의할 때 다시 받는다 */
  const [required, setRequired] = useState<TermsItem[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== 'signedIn') return;
    let alive = true;
    api.getTerms().then(
      (t) => {
        if (!alive) return;
        setRequired(t.required);
        /* 이미 동의했으면 약관을 다시 보여 주지 않음 (화면 상태 확인 ?demo= 는 제외) */
        if (t.complete && !demo) router.replace('/');
      },
      () => {},
    );
    return () => {
      alive = false;
    };
  }, [status, demo, router]);

  if (status === 'signedOut') return <Redirect href="/login" />;

  const props = {
    items: mockTerms,
    checked,
    document: documentKey ? legalDocument(documentKey) : null,
    leave_open: leaveOpen,
    saving,
    error,
    onToggle: (key: TermKey) => setChecked((current) => ({ ...current, [key]: !current[key] })),
    onToggleAll: () => setChecked((current) => {
      const all = mockTerms.every((item) => current[item.key]);
      return Object.fromEntries(mockTerms.map((item) => [item.key, !all])) as Record<TermKey, boolean>;
    }),
    onOpenDocument: setDocumentKey,
    onCloseDocument: () => setDocumentKey(null),
    onBack: () => setLeaveOpen(true),
    onCancelLeave: () => setLeaveOpen(false),
    onConfirmLeave: () => {
      setLeaveOpen(false);
      void signOut().finally(() => router.replace('/login'));
    },
    onContinue: () => {
      if (saving) return;
      setSaving(true);
      setError(null);
      void routeAfterTerms({
        agree: async () => api.agreeTerms(required ?? (await api.getTerms()).required),
        listMyStocks: api.listMyStocks,
      }).then((r) => {
        if (r.ok) {
          router.replace(r.next);
          return;
        }
        setError(SAVE_ERROR);
        setSaving(false);
      });
    },
  };
  return Platform.OS === 'web' ? <WebTerms {...props} /> : <AppTerms {...props} />;
}
