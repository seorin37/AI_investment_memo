/** 앱 아래 탭 5개 (원본 .tabbar: 홈 · 업데이트 · 내 종목 · 투자 기록 · 스튜디오) */
export type AppTab = 'home' | 'updates' | 'stocks' | 'journal' | 'studio';

export interface BottomTabBarProps {
  current: AppTab;
  onPress: (tab: AppTab) => void;
  /** 탭 아이콘 위 빨간 숫자 (원본: 업데이트 = 고른 종목의 읽지 않은 소식 수) */
  badges?: Partial<Record<AppTab, number>>;
  /** 숨김 (메모 고르기 중 등): 아래로 내려가며 높이를 접음 — 빈 공간 없음 */
  hidden?: boolean;
}
