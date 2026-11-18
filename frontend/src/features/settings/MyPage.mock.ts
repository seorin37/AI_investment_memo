/** MY 예시 — 체험판 my.html */
import type { MyPageProps } from '@/features/settings/MyPage.types';

export const mockMyPageProps: MyPageProps = {
  name: '김나라',
  initial: '김',
  sub: '대학생 · 카카오로 로그인 중',
  usage_percent: 62,
  usage_reset_label: '11.30 갱신',
  dark_mode: false,
  onToggleDark: () => {},
  onOpen: () => {},
};
