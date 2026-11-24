import type { Checklist } from '@/types/models';
import { mockBoardChecklist } from '@/ui/screens/board/MemoBoard.mock';
import type { CustomItem, HomeData, HomeWidget, SearchStock } from './Home.types';
import { HOME_DAYS, HOME_INDICES, HOME_NEWS, HOME_NEWS_DAY_TOTAL, HOME_SCHEDULE } from './homeData.mock';

/**
 * 홈 예시 데이터 — 웹 원본 '예시 계정'(seed.ts) 을 2026-11-19 09:00 KST 에 연 값 (11.18 종가 기준).
 * 앱 원본(home.html)의 Figma 예시 숫자(11.12 · SK 3건 · 삼성 2건 등) 대신 웹·앱 모두 이 값을 씀 (⑤ 와 같은 방식).
 */
export const mockHomeNow = '2026-11-19T09:00:00+09:00';

/** 원본 seed.ts 삼성전자 체크리스트 — 제목 '매수 전 확인' 은 문구 규칙(매수 권유 0건)으로 '살펴볼 것' */
const samsungChecklist: Checklist = {
  id: 'cl-005930',
  kind: 'checklist',
  stock_code: '005930',
  title: '살펴볼 것',
  position: 0,
  created_at: '2026-11-09T21:10:00+09:00',
  updated_at: '2026-11-09T21:10:00+09:00',
  items: [
    { id: 's1', text: '배당 기준일 확인', done: true },
    { id: 's2', text: '파운드리 수주 공시 보기', done: false },
  ],
};

export const mockHomeDefaultWidgets: HomeWidget[] = ['market', 'updates', 'news'];

export const mockHomeData: HomeData = {
  user_name: '김나라',
  counts: { holding: 1, watching: 2, ai_memos: 5 },
  updates: [
    { stock_code: '000660', name: 'SK하이닉스', logo: 'S', logo_bg: '#EA002C', status: 'holding', new_count: 2, latest: { kind: '공시', title: '분기보고서 제출 공시가 나왔어요', memo_title: '실적 나오면 다시 보기', memo_color: 'yellow' } },
    { stock_code: '005930', name: '삼성전자', logo: '삼', logo_bg: '#1428A0', status: 'watching', new_count: 0, latest: { kind: '뉴스', title: '삼성전자 자사주 관련 신규 계약 소식', memo_title: '자사주 매입 나오면 다시 보기', memo_color: 'yellow' } },
    { stock_code: '035420', name: '네이버', logo: '네', logo_bg: '#03C75A', status: 'watching', new_count: 1, latest: { kind: '뉴스', title: '네이버, AI 검색 관련 보도 뒤 거래 늘어', memo_title: 'AI 검색 반응 보기', memo_color: 'green' } },
  ],
  /* 지표마다 자기 날짜 (예시는 셋 다 HOME_DAYS) */
  market: HOME_INDICES.map((m) => ({ ...m, dates: HOME_DAYS.slice(-m.closes.length) })),
  days: HOME_DAYS,
  news: HOME_NEWS,
  news_day_total: HOME_NEWS_DAY_TOTAL,
  now: mockHomeNow,
  stocks: [
    { stock_code: '000660', name: 'SK하이닉스' },
    { stock_code: '005930', name: '삼성전자' },
    { stock_code: '035420', name: '네이버' },
  ],
  checklists: { '000660': mockBoardChecklist, '005930': samsungChecklist },
  widgets: mockHomeDefaultWidgets,
};

export const mockHomeSchedule = HOME_SCHEDULE;

/** 맞춤 홈 (원본 custom.tsx): 처음엔 빈 보드 */
export const mockCustomBoard: CustomItem[] = [];

/** 앱 검색 (원본 home.html STK 12종목) */
const STK: SearchStock[] = [
  { stock_code: '005930', name: '삼성전자', logo: '삼', logo_bg: '#1428A0' },
  { stock_code: '000660', name: 'SK하이닉스', logo: 'S', logo_bg: '#EA002C' },
  { stock_code: '035420', name: '네이버', logo: '네', logo_bg: '#03C75A' },
  { stock_code: '105560', name: 'KB금융', logo: 'K', logo_bg: '#FFBC00', logo_ink: '#1A1A1A' },
  { stock_code: '373220', name: 'LG에너지솔루션', logo: 'L', logo_bg: '#A50034' },
  { stock_code: '207940', name: '삼성바이오로직스', logo: '삼', logo_bg: '#1428A0' },
  { stock_code: '005380', name: '현대차', logo: '현', logo_bg: '#002C5F' },
  { stock_code: '000270', name: '기아', logo: '기', logo_bg: '#05141F' },
  { stock_code: '068270', name: '셀트리온', logo: '셀', logo_bg: '#0A6CB6' },
  { stock_code: '035720', name: '카카오', logo: '카', logo_bg: '#FEE500', logo_ink: '#1A1A1A' },
  { stock_code: '055550', name: '신한지주', logo: '신', logo_bg: '#0046FF' },
  { stock_code: '012450', name: '한화에어로스페이스', logo: '한', logo_bg: '#F37321' },
];
export const mockHomeSearch = { recent: [STK[0], STK[1], STK[3]], popular: STK.slice(4, 10), all: STK };
