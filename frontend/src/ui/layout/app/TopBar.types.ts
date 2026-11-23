import type { AppIconName } from '@/ui/icons/Icon';

/**
 * 원본 화면별 상단 바 (원본 HTML 실측)
 * 탭 화면: home(.hh 60·로고) · updates(.uh 60) · stocks(.hh 60) · journal(.hh 60) · studio(.sh 56) · start(.hh 56·로고)
 * 밀려 들어오는 화면: board(메모 보드 .hdr 56·흰 바탕) · memoDetail(.dh 56) · company(.ph2 56) · my(.bh 58) · market(홈 지수 자세히 .ph2 56·흰 바탕)
 */
export type TopBarPreset = 'home' | 'updates' | 'stocks' | 'journal' | 'studio' | 'start' | 'board' | 'memoDetail' | 'company' | 'my' | 'market';

export interface TopBarAction {
  icon: AppIconName;
  label: string;
  onPress?: () => void;
  /** 버튼 크기 (없으면 프리셋 값 40·42) */
  size?: number;
  /** 아이콘 크기 (없으면 원본 머리 버튼 22) */
  iconSize?: number;
  /** 아이콘 색 (없으면 원본 #16171A) */
  color?: string;
}

export interface TopBarProps {
  preset: TopBarPreset;
  /** 제목 (home · start 는 로고) */
  title?: string;
  /** 뒤로 (밀려 들어오는 화면) */
  onBack?: () => void;
  /** 오른쪽 아이콘 버튼들 (원본 순서대로) */
  actions?: TopBarAction[];
  /** 맨 오른쪽 아바타 (탭 화면) */
  avatar?: { name: string; photoUrl?: string | null; onPress?: () => void };
  /** 아래 선 (큰 제목이 접힐 때 등) */
  showLine?: boolean;
}
