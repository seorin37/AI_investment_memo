/** MY (프로필 → 들어가는 화면) */
export type MyMenuKey = 'profile' | 'usage' | 'notifications' | 'plan' | 'data' | 'trash' | 'about' | 'feedback' | 'help';

export interface MyPageProps {
  name: string;
  initial: string;
  /** '대학생 · 카카오로 로그인 중' */
  sub: string;
  /** 이번 기간 AI 사용량 % */
  usage_percent: number;
  /** '11.30 갱신' */
  usage_reset_label: string;
  dark_mode: boolean;
  onToggleDark: (on: boolean) => void;
  onOpen: (key: MyMenuKey) => void;
}
