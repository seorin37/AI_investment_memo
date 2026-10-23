/**
 * 디자인 토큰 — 'AI 투자 메모보드 UI_최종' Figma(SVG)에서 추출한 값.
 * 화면 코드에서는 HEX 를 직접 쓰지 말고 여기 토큰을 사용하세요.
 */
import type { MemoColor, UpdateType } from '@/types/models';

export const colors = {
  // 배경 · 면
  page: '#FDFDFD',
  surface: '#FFFFFF',
  surfaceMuted: '#F9F9F9', // 사이드바 검색, 입력
  surfaceSubtle: '#F5F6F8', // 위젯 내부 행
  surfaceWarm: '#F5F3EF', // 메모 팝업 세그먼트 · 본문 박스
  surfaceCanvas: '#F4F5F7', // 홈 사용자화 캔버스
  overlay: 'rgba(17, 19, 23, 0.36)',

  // 선
  border: '#E5E8EB',
  borderSoft: '#EEF0F3',
  borderStrong: '#D9DEE7',

  // 텍스트
  text: '#15171A',
  textStrong: '#191F28',
  textBody: '#333D4B',
  textSub: '#6B7684',
  textMuted: '#9AA3B2',
  textWarm: '#57535F', // 메모 팝업 보조 텍스트
  placeholder: '#B0B8C1',

  // 브랜드 · 강조
  black: '#111214',
  brand: '#6A42AB', // 사이드바 활성 텍스트
  brandSoft: '#F4EFFD', // 사이드바 활성 배경
  brandLine: '#986BEE',
  blue: '#477BFF', // 정보·데이터 구분 (주요 액션은 brand)
  blueStrong: '#3B82F5',
  blueSoft: '#EEF3FF',
  teal: '#1AB8A2', // AI 연결 토글 ON
  green: '#278D66',
  greenSoft: '#E7F5EF',
  greenText: '#128A72',
  danger: '#E5484D',
  dangerSoft: '#FDECEC',
  amber: '#A76818',

  // 시세 (기본: 상승 빨강 · 하락 파랑 — 설정에서 변경)
  up: '#F04545',
  down: '#3B82F5',
  upAlt: '#119C72',
  downAlt: '#E45D6A',
} as const;

export const memoPalette: Record<MemoColor, { bg: string; border: string; swatch: string; ink: string }> = {
  yellow: { bg: '#FFF4C6', border: '#EDE2B6', swatch: '#FFF4C4', ink: '#4F473B' },
  blue: { bg: '#DDEBFF', border: '#CDDBED', swatch: '#DDEBFF', ink: '#2F4A6D' },
  pink: { bg: '#FFE1E6', border: '#EDD0D6', swatch: '#FFE1E9', ink: '#6D3842' },
  green: { bg: '#DEF5E3', border: '#CEE4D3', swatch: '#DEF4E4', ink: '#2F5C3B' },
  purple: { bg: '#E8E0FF', border: '#D8CFED', swatch: '#EAE1FF', ink: '#4B3D73' },
};

export const MEMO_COLORS: MemoColor[] = ['yellow', 'blue', 'pink', 'green', 'purple'];

export const updateBadge: Record<UpdateType, { label: string; bg: string; fg: string }> = {
  disclosure: { label: '공시', bg: '#FDECEC', fg: '#E5484D' },
  news: { label: '뉴스', bg: '#E8EDF5', fg: '#404752' },
  price: { label: '주가', bg: '#E8F5EC', fg: '#278D66' },
};

/** AI 업데이트 타임라인 카드 색 */
export const timelineTone: Record<UpdateType, { bg: string; bar: string; iconBg: string; icon: string; label: string }> = {
  news: { bg: '#EBF2F8', bar: '#397FBD', iconBg: '#DDEBFF', icon: '#397FBD', label: '뉴스' },
  price: { bg: '#FFF6E9', bar: '#A76818', iconBg: '#FFF4C4', icon: '#A76818', label: '주가' },
  disclosure: { bg: '#F0EDFF', bar: '#6A57F2', iconBg: '#EAE1FF', icon: '#6A57F2', label: '공시' },
};

/** 보드 우측 AI 업데이트 패널 아이콘 색 */
export const panelIconTone: Record<UpdateType, { bg: string; label: string }> = {
  disclosure: { bg: '#6366F1', label: '공시' },
  news: { bg: '#FF8A3D', label: '뉴스' },
  price: { bg: '#14B8A6', label: '주가 변동' },
};

export const chartColors = {
  revenue: '#8E8BEB',
  operating: '#51C38B',
  net: '#F5D20A',
  yoyLine: '#333D4B',
  opm: '#141A24',
  npm: '#4A74B8',
  roe: '#C0392B',
  radar: '#378ADD',
  radarFill: 'rgba(55, 138, 221, 0.18)',
  grid: '#E8ECF3',
  axis: '#6B788C',
};

export const radius = { xs: 6, sm: 8, md: 12, lg: 16, xl: 20, xxl: 24, pill: 999 } as const;

export const space = { xxs: 4, xs: 8, sm: 12, md: 16, lg: 20, xl: 24, xxl: 32, xxxl: 40 } as const;

/** 공통 버튼 규격 — 화면에서는 너비·배치만 조정한다. */
export const buttonSizes = {
  sm: { h: 32, px: 12, fs: 13, r: radius.sm },
  md: { h: 44, px: 18, fs: 15, r: radius.md },
  lg: { h: 48, px: 22, fs: 16, r: radius.md },
} as const;

export const interaction = { hoverOpacity: 0.9, pressedOpacity: 0.8, disabledOpacity: 0.4, focusWidth: 2 } as const;

export const modalLayout = { padding: space.xl, radius: radius.xxl, titleSize: 20, descriptionSize: 14, closeSize: 20, closeBox: 36 } as const;

export const layout = {
  sidebarWidth: 250,
  sidebarCollapsed: 72,
  contentMaxWidth: 1180,
  pagePaddingX: 32,
  aiPanelWidth: 334,
  breakpoints: { mobile: 768, desktop: 1100 },
} as const;

export const fonts = {
  regular: 'Pretendard-Regular',
  medium: 'Pretendard-Medium',
  semibold: 'Pretendard-SemiBold',
  bold: 'Pretendard-Bold',
} as const;

export type FontWeightKey = keyof typeof fonts;

export const shadow = {
  card: {
    shadowColor: '#0F172A',
    shadowOpacity: 0.04,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  pop: {
    shadowColor: '#0F172A',
    shadowOpacity: 0.12,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 8 },
    elevation: 8,
  },
  modal: {
    shadowColor: '#0F172A',
    shadowOpacity: 0.18,
    shadowRadius: 40,
    shadowOffset: { width: 0, height: 16 },
    elevation: 16,
  },
} as const;
