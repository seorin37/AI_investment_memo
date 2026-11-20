import type { AuthProvider } from '@/types/models';
import type { LegalKey } from '@/ui/screens/auth/Auth.types';
import type { PlanInfo, TrackedStock } from './My.mock';

/** MY · 설정 (원본 app/my.html · web overlays.tsx Settings) — ⑨-3a: 본 화면 · 내 프로필 · 로그아웃 · 회원 탈퇴 */
export interface MyProfile {
  name: string;
  /** 한 줄 소개 (원본 job) */
  intro: string;
  provider: AuthProvider;
  email: string;
}

/** MY 본 화면에서 여는 하위 화면 (⑨-3b·c 에서 채움) */
export type MyMenuKey = 'noti' | 'usage' | 'data' | 'trash' | 'info' | 'fb' | 'help';

export interface AppMyProps {
  profile: MyProfile;
  /** AI 사용량 % (예시) */
  usage_pct: number;
  /** 사용량 갱신일 'MM.DD' */
  usage_renew: string;
  version: string;
  dark: boolean;
  onBack: () => void;
  onProfile: () => void;
  onUsage: () => void;
  onOpen: (key: MyMenuKey) => void;
  onToggleDark: () => void;
}

export interface ProfileProps {
  profile: MyProfile;
  onBack: () => void;
  /** 이름·한 줄 소개 저장 (서버 API 없음 → 화면 상태만) */
  onChange: (p: Pick<MyProfile, 'name' | 'intro'>) => void;
  onPhoto: () => void;
  onPhotoDelete: () => void;
  onLink: (provider: AuthProvider) => void;
  onLogout: () => void;
  onWithdraw: () => void;
}

export interface WithdrawProps {
  /** 지워지는 것 (웹: 4칸 · 앱 원본은 11.13 에 목록을 뺐음) */
  counts: { memo: number; journal: number; stock: number; ai: number };
  onBack: () => void;
  /** 마지막 확인까지 끝났을 때 (mock: 실제로 지우지 않음) */
  onConfirm: (reasons: string[]) => void;
}

/* ---------- ⑨-3b ---------- */
export interface NotiSettings { ai: boolean; studio: boolean }

export interface NotiProps {
  noti: NotiSettings;
  onBack: () => void;
  onChange: (n: NotiSettings) => void;
}

export interface UsageProps {
  usage_pct: number;
  usage_renew: string;
  plan_name: string;
  tracked: TrackedStock[];
  onBack: () => void;
  onOpenMemo: (stock_code: string, title: string) => void;
  onPlans: () => void;
}

export interface PlansProps {
  plans: PlanInfo[];
  compare: [string, (string | true)[]][];
  notes: string[];
  default_key: string;
  onBack: () => void;
  /** 결제·업그레이드 (연결 안 됨 → 안내만) */
  onStart: (plan_key: string) => void;
}

export interface DataProps {
  counts: WithdrawProps['counts'];
  onBack: () => void;
  /** 웹만: 내보내기 */
  onExport?: () => void;
  /** 확인창까지 누른 뒤 (mock: 실제로 지우지 않음) */
  onWipe: () => void;
}

export type InfoDoc = LegalKey | 'oss';
export interface InfoProps {
  /** 앱 설정(app.json version)에서 읽은 버전 '0.1.0' */
  version: string;
  sources: [string, string][];
  onBack: () => void;
  onDoc: (doc: InfoDoc) => void;
  /** 피드백 보내기 · 문의하기 (⑨-3c) */
  onFeedback: () => void;
  /** 웹만: 사용법 다시 보기 */
  onReplayGuide?: () => void;
}

export const WITHDRAW_REASONS = ['자주 쓰지 않아요', '원하는 기능이 없어요', '사용이 어려워요', '개인정보가 걱정돼요', '기타'] as const;
