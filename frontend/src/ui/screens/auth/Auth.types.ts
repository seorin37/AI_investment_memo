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
  /** 동의 저장 중 — 버튼은 '체크 덜 됨'과 같은 비활성 모양 (두 번 누름 방지) */
  saving?: boolean;
  /** 저장 실패 문구 — 있을 때만 버튼 위 한 줄 */
  error?: string | null;
}

export function requiredComplete(items: TermItem[], checked: Record<TermKey, boolean>): boolean {
  return items.every((item) => !item.required || checked[item.key]);
}

export function allTermsChecked(items: TermItem[], checked: Record<TermKey, boolean>): boolean {
  return items.every((item) => checked[item.key]);
}
