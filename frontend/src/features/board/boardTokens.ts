/**
 * 메모 보드 화면들(MemoBoard · MemoDetail · NewMemo · ChecklistDetail · AiLinkConfirm)이 같이 쓰는 색.
 * 나중에 src/theme/tokens.ts 로 옮길 것. 이름은 기존 models.ts의 MemoColor('yellow' 등)와 같음.
 */
import type { MemoColor } from '@/types/models';

export const BOARD_C = {
  appBg: '#F3F4F6',
  card: '#FFFFFF',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  body: '#2E2E38',
  line: '#EEF0F3',
  accent: '#8569E3',
  accentDeep: '#6A42AB',
  accentSoft: '#EEE9FB',
  red: '#E5484D',
  redSoft: '#FFF5F4',
  dark: '#16171A',
  white: '#FFFFFF',
  scrim: 'rgba(246,247,249,0.8)',
  modalScrim: 'rgba(0,0,0,0.35)',
  selMarkBg: 'rgba(0,0,0,0.12)',
  skeleton: '#EEF0F3',
  chipLine: '#E3E5EA',
  green: '#1B7A45',
  greenSoft: '#E3F5EA',
  blue: '#2F6BDB',
  blueSoft: '#E4ECFF',
  warnBg: '#FFF6E0',
  warnText: '#7A4B00',
  warnBtn: '#8A5A00',
  warnLine: '#F1D9A8',
  shadow: '#000000',
  vtKnob: '#FFFFFF',
  pinSwipe: '#F29A1F',
} as const;

/** 메모지 색: 종이(bg)와 접힌 모서리·테이프(fold). 체험판 값 그대로 */
export const MEMO_PAPER: Record<MemoColor, { bg: string; fold: string }> = {
  yellow: { bg: '#FCEAAA', fold: '#EFBF2A' },
  green: { bg: '#CDEFD9', fold: '#2FAE68' },
  blue: { bg: '#CFE0FF', fold: '#3D73F0' },
  purple: { bg: '#D2BEFF', fold: '#7046F5' },
  pink: { bg: '#F7C6F0', fold: '#D62BC4' },
};

/** 체크리스트 = 귤색 (메모 5색과 겹치지 않게, 11.17 결정) */
export const CHECKLIST_C = {
  paper: '#FFEADB',
  tape: '#FF7A1A',
  check: '#FF7A1A',
  deep: '#C2410C',
  iconBg: '#FFDCC4',
  boxLine: '#E9B48F',
  doneText: '#B49A8A',
  more: '#B07A55',
  meta: '#9A6B4F',
  line: 'rgba(194,65,12,0.12)',
  barTrack: 'rgba(255,255,255,0.8)',
  barFrom: '#FFB547',
} as const;

/** 다크 모드 메모지 (11.18 결정 · 반전 없이 이 색을 그대로) — 다크 모드 구현 때 사용 */
export const MEMO_PAPER_DARK: Record<MemoColor | 'checklist', string> = {
  yellow: '#6E5D2A',
  green: '#2F5E44',
  blue: '#33497A',
  purple: '#4D4083',
  pink: '#6E3863',
  checklist: '#704530',
};
