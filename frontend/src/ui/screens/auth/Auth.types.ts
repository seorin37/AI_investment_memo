import type { AuthProvider } from '@/types/models';

export type IntroPageKey = 'flood' | 'attach' | 'studio';

export interface IntroPage {
  key: IntroPageKey;
  title: string;
  description: string;
}

export interface IntroProps {
  pages: IntroPage[];
  page: number;
  onPageChange: (page: number) => void;
  onDone: () => void;
}

export type LoginErrorKind = 'login' | 'network' | null;

export interface LoginProps {
  busy: AuthProvider | null;
  error: LoginErrorKind;
  recent_provider: AuthProvider | null;
  onLogin: (provider: AuthProvider) => void;
  onRetry: () => void;
  onIntro: () => void;
}

export type LegalKey = 'terms' | 'privacy' | 'invest';
export type TermKey = 'age' | 'service' | 'invest';

export interface TermItem {
  key: TermKey;
  label: string;
  required: boolean;
  document?: LegalKey;
}

export interface LegalDocument {
  key: LegalKey;
  title: string;
  html: string;
}

export interface TermsProps {
  items: TermItem[];
  checked: Record<TermKey, boolean>;
  document: LegalDocument | null;
  leave_open: boolean;
  onToggle: (key: TermKey) => void;
  onToggleAll: () => void;
  onOpenDocument: (key: LegalKey) => void;
  onCloseDocument: () => void;
  onBack: () => void;
  onCancelLeave: () => void;
  onConfirmLeave: () => void;
  onContinue: () => void;
}

export function requiredComplete(items: TermItem[], checked: Record<TermKey, boolean>): boolean {
  return items.every((item) => !item.required || checked[item.key]);
}

export function allTermsChecked(items: TermItem[], checked: Record<TermKey, boolean>): boolean {
  return items.every((item) => checked[item.key]);
}
