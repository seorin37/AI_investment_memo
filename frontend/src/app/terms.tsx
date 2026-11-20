import React, { useState } from 'react';
import { Platform } from 'react-native';
import { Redirect, useLocalSearchParams, useRouter } from 'expo-router';
import { useAuth } from '@/store/auth';
import { checkedTerms, emptyTermChecks, legalDocument, mockTerms } from '@/ui/screens/auth/Auth.mock';
import type { LegalKey, TermKey } from '@/ui/screens/auth/Auth.types';
import { AppTerms } from '@/ui/screens/auth/app/Terms';
import { WebTerms } from '@/ui/screens/auth/web/Terms';

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

  if (status === 'signedOut') return <Redirect href="/login" />;

  const props = {
    items: mockTerms,
    checked,
    document: documentKey ? legalDocument(documentKey) : null,
    leave_open: leaveOpen,
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
    onContinue: () => router.replace('/onboarding/pick'),
  };
  return Platform.OS === 'web' ? <WebTerms {...props} /> : <AppTerms {...props} />;
}
