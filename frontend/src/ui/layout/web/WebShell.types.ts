import type { StockStatus } from '@/types/models';

/** 사이드바 종목 줄: 종목(models) + 로고 모양 */
export interface SideStock {
  stock_code: string;
  name: string;
  status: StockStatus;
  /** 로고 글자 · 바탕 · 글자색 (원본 fig.tsx SLogo) */
  logo: string;
  logo_bg: string;
  logo_ink?: string;
}

/** 사이드바에서 고른 곳 */
export type SideKey = 'home' | 'updates' | 'journal' | 'mine' | { stock: string } | null;

/** 사이드바 검색 결과 한 줄 (원본: 종목 · 메모 · 기록을 한 번에) */
export interface SideSearchHit {
  key: string;
  title: string;
  sub: string;
}

export interface SidebarProps {
  /** 펼침 250 / 접힘 72 */
  open: boolean;
  onToggle: () => void;
  current: SideKey;
  stocks: SideStock[];
  profile: { name: string; job: string; photoUrl?: string | null };
  /** 종 배지 (읽지 않은 알림 수) */
  unreadNotifs: number;
  /** 다크 모드 (이번 묶음은 표시만 · ⑩에서 바뀜) */
  dark: boolean;
  /** 검색 */
  recentSearches: string[];
  popular: { stock_code: string; name: string; mine: boolean }[];
  onSearch: (q: string) => SideSearchHit[];
  onPickSearch: (hit: SideSearchHit) => void;
  onPickRecent: (name: string) => void;
  onPickPopular: (code: string) => void;
  /** 이동 · 동작 (콜백만) */
  onNavigate: (to: 'home' | 'updates' | 'journal' | 'mine') => void;
  onOpenStock: (code: string) => void;
  onStockMenu: (code: string) => void;
  onAddStock: () => void;
  onBell: () => void;
  onToggleDark: () => void;
  onTrash: () => void;
  onSettings: () => void;
  onFeedback: () => void;
  onHelp: () => void;
  onProfile: () => void;
  onLogout: () => void;
}

export type StudioFeature = 'audio' | 'report' | 'quiz' | 'lab';

export interface StudioColumnFrameProps {
  /** 펼침 436 / 접힘 96 */
  open: boolean;
  onToggle: () => void;
  stockCount: number;
  aiMemoCount: number;
  /** AI 사용량 % (100 이상이면 주황) */
  usagePct: number;
  onUsage: () => void;
  onFeature: (f: StudioFeature) => void;
  /** 접힘 열의 기능 버튼 배지 ('1' 또는 만드는 중 '·') */
  badges?: Partial<Record<StudioFeature, string>>;
  /** 카드 안 내용 (⑧ 스튜디오 묶음에서 채움) */
  children?: React.ReactNode;
}
