/**
 * UI v2 값 — 원본 그대로 (docs/ui-v2-rules.md 0·8번)
 * - 앱: 원본UI/app 의 x/app.css + 화면 HTML 10개 :root·CSS
 * - 웹: 원본UI/web 의 src/*.css · tailwind 기본 팔레트 · 화면 tsx 임의값
 * 숫자는 원본 px 그대로. 줄 높이는 원본 배수(1.6 등)를 px로 계산해서 쓴다(규칙 6).
 */
import { Easing, type TextStyle } from 'react-native';
import type { MemoColor } from '@/types/models';

/* ───────── 글자 ───────── */

/** Pretendard 의 line-height: normal (Chrome 실측: 100px → 113.16px). 원본에서 줄 높이를 안 적은 글자의 기본값 */
export const NORMAL_LH = 1.1316;

/** 원본 배수 줄 높이 → px (소수 둘째 자리) */
export function lh(size: number, ratio: number = NORMAL_LH): number {
  return Math.round(size * ratio * 100) / 100;
}

/** 앱 글자: 크기 + 원본 배수(없으면 normal) → { fontSize, lineHeight } */
export function ft(size: number, ratio?: number): Pick<TextStyle, 'fontSize' | 'lineHeight'> {
  return { fontSize: size, lineHeight: lh(size, ratio) };
}

/** 웹 글자: 원본이 px 로 적은 줄 높이 그대로 */
export function fpx(size: number, lineHeight: number): Pick<TextStyle, 'fontSize' | 'lineHeight'> {
  return { fontSize: size, lineHeight };
}

/** 웹 원본 전체 자간 -0.02em (index.css) → px */
export function webTracking(size: number): number {
  return Math.round(size * -0.02 * 100) / 100;
}

/** 웹 원본 글자 쌍 (text-[N] leading-[N]) — 많이 쓰는 순 */
export const webType = {
  t11: fpx(11, 16),
  t13: fpx(13, 20),
  t14: fpx(14, 21),
  t15: fpx(15, 23),
  t17: fpx(17, 26),
  t20: fpx(20, 29),
  t22: fpx(22, 31),
  t26: fpx(26, 35),
  t30: fpx(30, 40),
} as const;

/* ───────── 색: 앱 ───────── */
export const appColor = {
  /** --a 주요 선택 */
  accent: '#8569E3',
  /** --a2 진한 보라 (login · home · update · memo · studio · my) */
  deepPurple: '#6A42AB',
  /** --a2 진한 보라 (start · stock · company · journal) */
  tabPurple: '#7356D6',
  /** --aSoft 연보라 (선택 탭 알약 · 아바타) */
  accentSoft: '#EEE9FB',
  /** 연보라 2 (홈 편집 [추가] · AI 사용량 칩) */
  accentSoft2: '#F0ECFF',
  /** 연보라 3 (투자 기록 새 기록 버튼) */
  accentSoft3: '#EDE8FB',
  /** 보라 글자 (읽지 않은 소식 칩 · AI 사용량) */
  accentInk: '#5B3BD1',
  /** --ink */
  ink: '#16171A',
  /** --ink2 */
  ink2: '#575B63',
  /** --ink3 흐린 글자 */
  ink3: '#9A9EA7',
  /** --ink3 흐린 글자 — 첫 홈(start)만 */
  ink3Start: '#8A8F98',
  /** 아래 탭 기본 글자 */
  tabInk: '#3F434A',
  /** --line */
  line: '#E6E8EC',
  /** 칩 테두리 */
  chipLine: '#E3E5EA',
  /** --bg 화면 배경 */
  bg: '#F3F4F6',
  surface: '#FFFFFF',
  /** --sf 회색 면 (탭 바탕 · 보조 버튼) */
  sf: '#F2F2F5',
  /** 검색칸 (업데이트) */
  searchBg: '#E9EAEE',
  /** 검색칸 (투자 기록) */
  searchBg2: '#E6E8EC',
  /** 줄 바탕 (홈 업데이트 줄) */
  row: '#F6F7F9',
  /** --red 새 소식 배지 */
  red: '#E5484D',
  /** 빼기 버튼 바탕 */
  redSoft: '#FFE8E8',
  /** --up 상승 · --down 하락 */
  up: '#E5484D',
  down: '#2F6BDB',
  /** --org (stock · company · journal) */
  org: '#F2A33A',
  okInk: '#1B7A45',
  okSoft: '#E3F5EA',
  badInk: '#B42318',
  badSoft: '#FFE9E9',
  /** 스낵바 */
  snack: '#1F2024',
  /** 넛지 알약 */
  nudge: '#15171A',
} as const;

/* ───────── 색: 웹 ───────── */
export const webColor = {
  ink: '#15171A',
  /** 사이드바 글자 */
  label: '#1C1C1C',
  /** 사이드바 아이콘 */
  icon: '#333333',
  /** 접기·펼치기 아이콘 */
  iconSub: '#666666',
  /** 스튜디오 아이콘 */
  icon2: '#404752',
  /** 보유·관심 묶음 이름 · 검색 placeholder */
  groupLabel: '#6B7078',
  /** 프로필 직업 */
  sub: '#9F9F9F',
  sub2: '#8B95A1',
  ink2: '#575B63',
  strong: '#191F28',
  mute: '#8F8F8F',
  mute2: '#9AA0AA',
  studioSub: '#8E8A97',
  line: '#E5E7EB',
  line2: '#E5E8EB',
  line3: '#E8ECF3',
  studioLine: '#E4E4E7',
  /** 가운데 영역 */
  page: '#FDFDFD',
  /** body */
  body: '#F6F6F6',
  surface: '#FFFFFF',
  hover: '#F9F9F9',
  selBg: '#FBF8FF',
  selInk: '#6A42AB',
  chip: '#F2F3F4',
  chipHover: '#E9EAEC',
  row: '#F5F6F8',
  active: '#EFEFEF',
  menuHover: '#ECECEC',
  up: '#E5484D',
  down: '#2F6BDB',
  /** 스튜디오 접힘 열 배지 */
  badge: '#E45D6A',
  /** 화면이 좁을 때 스튜디오 열 바탕 */
  studioBg: '#F3F4F6',
  usageOutBg: '#FFF4E5',
  usageOutInk: '#7A4A00',
  usageOutBar: '#C27A00',
} as const;

/** 웹 원본이 쓰는 tailwind 3.4 기본 색 (zinc 등) */
export const tw = {
  zinc50: '#FAFAFA',
  zinc100: '#F4F4F5',
  zinc200: '#E4E4E7',
  zinc300: '#D4D4D8',
  zinc400: '#A1A1AA',
  zinc500: '#71717A',
  zinc600: '#52525B',
  zinc800: '#27272A',
  zinc900: '#18181B',
  zinc950: '#09090B',
  red50: '#FEF2F2',
  red600: '#DC2626',
  red700: '#B91C1C',
  sky50: '#F0F9FF',
  sky700: '#0369A1',
  emerald50: '#ECFDF5',
  emerald700: '#047857',
  black: '#111111',
} as const;

/** 스튜디오 기능 색 (웹 studio.tsx KIND · 접힘 열) */
export const studioFeature = {
  audio: { box: '#D6E4FF', ink: '#2F6BDB' },
  report: { box: '#FFDADB', ink: '#D6404A' },
  quiz: { box: '#D3F0DE', ink: '#1F8A4C' },
  lab: { box: '#FCE9AE', ink: '#A8740A' },
} as const;

/* ───────── 메모지 · 체크리스트 (웹·앱 같음) ───────── */
export const paper: Record<MemoColor, { bg: string; accent: string; label: string }> = {
  yellow: { bg: '#FCEAAA', accent: '#EFBF2A', label: '노랑' },
  green: { bg: '#CDEFD9', accent: '#2FAE68', label: '초록' },
  blue: { bg: '#CFE0FF', accent: '#3D73F0', label: '파랑' },
  purple: { bg: '#D2BEFF', accent: '#7046F5', label: '보라' },
  pink: { bg: '#F7C6F0', accent: '#D62BC4', label: '분홍' },
};
export const checklistColor = { tape: '#FF7A1A', paper: '#FFEADB', ink: '#C2410C' } as const;

/** 소식 종류 태그 (웹 kit.tsx KindTag) */
export const webKindTag = {
  공시: { bg: tw.red50, ink: tw.red600 },
  뉴스: { bg: tw.sky50, ink: tw.sky700 },
  주가: { bg: tw.emerald50, ink: tw.emerald700 },
  기타: { bg: tw.zinc100, ink: tw.zinc600 },
} as const;

/* ───────── 치수 ───────── */
export const size = {
  /** 앱 기준 폭 (원본 .dev) */
  appWidth: 412,
  appSide: 16,
  cardGap: 14,
  touch: 44,
  /** 아래 탭바: 전체 80 = 내용 66 + 아래 여백 14 */
  tabBar: 80,
  tabBarPadBottom: 14,
  /** 웹 사이드바 */
  sidebar: 250,
  rail: 72,
  sideInner: 218,
  /** 웹 스튜디오 열 (바깥 · 안쪽 카드 · 접힘) */
  studioCol: 436,
  studioCard: 412,
  studioColClosed: 96,
  studioRail: 72,
  /** 웹: 화면이 이 폭 이하면 스튜디오 열이 처음에 접힘 (studio.tsx) */
  studioNarrow: 1280,
} as const;

export const radius = {
  /** 앱 메모 카드 (16 16 0 16 · 접힌 귀퉁이 쪽 0) */
  memo: 16,
  /** 앱 메모 상세 종이 (22 22 0 22) */
  memoPaper: 22,
  /** 앱 카드 */
  card: 20,
  /** 앱 바텀 시트 위 */
  sheet: 26,
  /** 앱 스낵바 */
  snack: 14,
  /** 웹 스튜디오 카드 */
  studioCard: 22,
  /** 웹 사이드바 줄 */
  sideRow: 8,
} as const;

/* ───────── 모션 (웹 motion.css · 앱 :root 같은 값) ───────── */
export const curve = {
  /** 기본 이동 · 화면 밀기 · 펼치기 */
  ease: Easing.bezier(0.2, 0.8, 0.2, 1),
  /** 페이드 스루 들어오기 */
  enter: Easing.bezier(0.2, 0, 0, 1),
  /** 작은 톡 튀는 반동 (토글 · 배지 · 스낵) */
  spring: Easing.bezier(0.34, 1.45, 0.64, 1),
  /** 시트 · 숫자 굴림 · 큰 반동 */
  sheet: Easing.bezier(0.3, 1.25, 0.5, 1),
  /** 끌어서 놓을 때 앉기 */
  land: Easing.bezier(0.3, 1.2, 0.5, 1),
  /** 날아가는 정렬 (사이드바 순서 바꾸기 #317) */
  fly: Easing.bezier(0.3, 1.1, 0.4, 1),
} as const;

/** ms — 동작 줄이기면 useMotionK() 배수(0.01)를 곱해서 쓴다 */
export const dur = {
  out: 90,
  in: 210,
  fast: 200,
  base: 300,
  /** 앱 화면 밀기 (index.html show push/pop .32s) */
  push: 320,
  pop: 350,
  slow: 450,
  sheet: 500,
  odo: 600,
  stagger: 70,
} as const;

/* ───────── 그림자 (규칙 5: shadow* 와 elevation 함께) ───────── */
export const shadow = {
  /** 앱 탭 알약 (ppill: 0 1px 4px rgba(0,0,0,.09)) */
  pill: { shadowColor: '#000000', shadowOpacity: 0.09, shadowRadius: 4, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  /** 웹 Seg 알약 (0 1px 3px rgba(0,0,0,.08)) */
  seg: { shadowColor: '#000000', shadowOpacity: 0.08, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  /** 앱 바텀 시트 (0 -10px 30px -12px rgba(0,0,0,.25)) */
  sheet: { shadowColor: '#000000', shadowOpacity: 0.25, shadowRadius: 18, shadowOffset: { width: 0, height: -10 }, elevation: 16 },
  /** 앱 + 버튼 (0 10px 22px -8px rgba(106,66,171,.6)) */
  fab: { shadowColor: '#6A42AB', shadowOpacity: 0.6, shadowRadius: 14, shadowOffset: { width: 0, height: 10 }, elevation: 8 },
  /** 웹 토스트 · 넛지 (0 12px 30px rgba(20,23,26,.25)) */
  toast: { shadowColor: '#14171A', shadowOpacity: 0.25, shadowRadius: 30, shadowOffset: { width: 0, height: 12 }, elevation: 10 },
  /** 웹 사이드바 펼침 메뉴 (0 4px 16px rgba(0,0,0,.12)) */
  menu: { shadowColor: '#000000', shadowOpacity: 0.12, shadowRadius: 16, shadowOffset: { width: 0, height: 4 }, elevation: 6 },
  /** 웹 검색 결과 (0 8px 24px rgba(31,46,84,.10)) */
  drop: { shadowColor: '#1F2E54', shadowOpacity: 0.1, shadowRadius: 24, shadowOffset: { width: 0, height: 8 }, elevation: 6 },
} as const;
