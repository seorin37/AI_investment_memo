import { useWindowDimensions } from 'react-native';
import { size } from '@/ui/theme';

/** 이 폭 미만이면 웹 사이드바·스튜디오 열을 약 90% 크기로 줄임 (v2 원본에는 없는 값) */
export const SHELL_COMPACT_BELOW = 1600;

const shell = <T extends { sidebar: number; sideInner: number; rowH: number; avatar: number }>(v: T) => ({
  ...v,
  /* 사이드바 안 위치는 폭에서 계산 (1600 이상: 벨 154 · 접기 194 · 화살표 186 · 종목 170 · 내 종목 154 · 프로필 138 · 설정 팝업 234 · 알림함 258) */
  bellLeft: v.sideInner - 64,
  foldLeft: v.sideInner - 24,
  groupChevLeft: v.sideInner - 32,
  stockRow: v.sideInner - 48,
  mineRow: v.sideInner - 64,
  /* 이름 칸 = 사진 + 간격 12 + 로그아웃 자리 28 을 뺀 폭 (사진이 작아지면 이름이 넓어짐) */
  profileText: v.sideInner - (v.avatar + 12 + 28),
  flyLeft: v.sidebar - 16,
  inboxLeft: v.sidebar + 8,
  /* 줄 높이에서 계산 (1600 이상: 메뉴 버튼 8 · 화살표 4 · 검색 목록 48 · 종목 간격 52) */
  stockMenuTop: (v.rowH - 24) / 2,
  groupChevTop: (v.rowH - 32) / 2,
  dropTop: v.rowH + 8,
  sortStep: v.rowH + 12,
});

const REGULAR = shell({
  compact: false as boolean,
  sidebar: size.sidebar as number,
  sideInner: size.sideInner as number,
  rowH: 40,
  /* 펼친 사이드바 아래 프로필 사진 (엑셀 웹 #10: 48 → 40, 접힌 사이드바와 같게) · 이니셜 40 × .45 */
  avatar: 40,
  avatarText: 18,
  menuText: { fontSize: 17, lineHeight: 26 },
  icon: 20,
  logo: 24,
  searchPadY: 10,
  studioCol: size.studioCol as number,
  studioCard: size.studioCard as number,
  studioHead: { height: 72, paddingTop: 20, paddingBottom: 10, paddingLeft: 20, paddingRight: 12 },
  studioTitle: { fontSize: 22, lineHeight: 28.6 },
  studioSub: { fontSize: 14, lineHeight: 21 },
  homePadX: 16,
  feat: { paddingHorizontal: 12, paddingVertical: 14 },
  featBox: { width: 44, height: 44, borderRadius: 13 },
  featIcon: 22,
  featTitle: { fontSize: 17, lineHeight: 24 },
  featDesc: { fontSize: 15, lineHeight: 22 },
});

const COMPACT: typeof REGULAR = shell({
  compact: true,
  sidebar: 224,
  sideInner: 192,
  rowH: 36,
  avatar: 36,
  avatarText: 16,
  menuText: { fontSize: 15, lineHeight: 23 },
  icon: 18,
  logo: 22,
  searchPadY: 6,
  studioCol: 388,
  studioCard: 364,
  studioHead: { height: 64, paddingTop: 18, paddingBottom: 9, paddingLeft: 18, paddingRight: 11 },
  studioTitle: { fontSize: 20, lineHeight: 26 },
  studioSub: { fontSize: 13, lineHeight: 19.5 },
  homePadX: 14,
  feat: { paddingHorizontal: 11, paddingVertical: 12 },
  featBox: { width: 40, height: 40, borderRadius: 12 },
  featIcon: 20,
  featTitle: { fontSize: 15, lineHeight: 21 },
  featDesc: { fontSize: 14, lineHeight: 20 },
});

export const shellSizeFor = (width: number) => (width < SHELL_COMPACT_BELOW ? COMPACT : REGULAR);

export function useShellSize() {
  return shellSizeFor(useWindowDimensions().width);
}
