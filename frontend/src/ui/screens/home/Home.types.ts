import type { ReactNode } from 'react';
import type { Checklist, MemoColor } from '@/types/models';

/** 시장 지수 (코스피 · 코스닥 · 원/달러) — 전일 확정 종가 기준 */
export type MarketKey = 'kospi' | 'kosdaq' | 'usd';

export interface MarketIndex {
  key: MarketKey;
  /** 코스피 */
  name: string;
  /** 앱 지수 자세히의 작은 제목 (KOSPI 지수) */
  sub: string;
  /** 마지막 종가 */
  value: number;
  /** 전일 대비 */
  change: number;
  /** 전일 대비 % */
  pct: number;
  /** 기준 거래일 YYYY-MM-DD */
  as_of: string;
  /** 일별 종가 (오래된 → 최근, days 와 같은 길이) */
  closes: number[];
  /** 웹 '1일': 전 거래일 하루 흐름 (09:00~15:30 40점) */
  day_flow: number[];
}

/** 홈 업데이트 위젯 한 줄 (종목별 새 소식) */
export interface HomeUpdateRow {
  stock_code: string;
  name: string;
  logo: string;
  logo_bg: string;
  logo_ink?: string;
  status: 'holding' | 'watching';
  /** 읽지 않은 새 소식 수 */
  new_count: number;
  /** 웹: 가장 새 소식이 있는 AI 메모와 그 소식 */
  latest?: { kind: '공시' | '뉴스' | '주가'; title: string; memo_title: string; memo_color: MemoColor };
}

export interface HomeNewsItem {
  id: string;
  title: string;
  /** 언론사 */
  src: string;
  /** ISO */
  at: string;
  url: string;
}

/** 주요 증시 일정 (웹 맞춤 홈 달력) */
export interface MarketEvent {
  date: string;
  title: string;
}

export type HomeWidget = 'market' | 'updates' | 'news' | 'check';

/** 검색 종목 (앱 홈 돋보기) */
export interface SearchStock {
  stock_code: string;
  name: string;
  logo: string;
  logo_bg: string;
  logo_ink?: string;
}

/** 내 종목 (체크리스트 위젯 칩 · 웹) */
export interface HomeStock {
  stock_code: string;
  name: string;
}

/** 웹·앱 홈이 함께 쓰는 데이터 */
export interface HomeData {
  user_name: string;
  /** 보유 · 관심 · AI 연결 메모 수 */
  counts: { holding: number; watching: number; ai_memos: number };
  updates: HomeUpdateRow[];
  /** null = 시장 정보를 불러오지 못함 (위젯 안에서만 오류) */
  market: MarketIndex[] | null;
  /** 지수 일별 종가의 날짜 (MarketIndex.closes 와 같은 길이) */
  days: string[];
  news: HomeNewsItem[];
  /** 기준 거래일의 뉴스 수 */
  news_day_total: number;
  /** 지금 (뉴스 'N시간 전' 계산) */
  now: string;
  stocks: HomeStock[];
  /** 종목별 체크리스트 */
  checklists: Record<string, Checklist>;
  /** 켜 둔 위젯과 순서 */
  widgets: HomeWidget[];
}

export interface HomeCallbacks {
  onChangeWidgets: (w: HomeWidget[]) => void;
  /** 업데이트 탭 · 종목별 업데이트 */
  onOpenUpdates: () => void;
  onOpenStockUpdates: (code: string) => void;
  /** 메모 보드 (③) */
  onOpenStock: (code: string) => void;
  onOpenNews: (n: HomeNewsItem) => void;
  onRetryMarket: () => void;
  onToggleCheck: (code: string, itemId: string) => void;
  onAddCheck: (code: string, text: string) => void;
  /** 넛지: 홈 = 주간보고서 · 원/달러 = 투자 실험실 */
  onNudge: (kind: 'report' | 'lab') => void;
}

export interface AppHomeProps extends HomeData, HomeCallbacks {
  /** 지수 자세히 (앱은 밀려 들어오는 화면) */
  onOpenMarket: (key: MarketKey) => void;
  /** 홈 편집 중이면 탭바를 숨김 (원본 .edit-on .tabbar) */
  onEditingChange?: (editing: boolean) => void;
  /** 위 바 (탭 화면 셸) — 스크롤하면 아래 선 */
  header: (o: { line: boolean; onSearch: () => void }) => ReactNode;
  /** 검색: 최근 · 많이 찾는 · 전체 */
  search: { recent: SearchStock[]; popular: SearchStock[]; all: SearchStock[] };
}

export interface WebHomeProps extends HomeData, HomeCallbacks {
  /** 'custom' = 홈 직접 사용자화 (온보딩에서 '직접' 고른 경우) */
  mode: 'template' | 'custom';
  /** 맞춤 홈 달력 (실제 데이터 연결 안 함) */
  schedule: MarketEvent[];
  /** 맞춤 홈: 놓인 위젯 (24px 격자 좌표) */
  board: CustomItem[];
  onChangeBoard: (b: CustomItem[]) => void;
  onGoStart: () => void;
}

export type CustomWidget = 'market' | 'updates' | 'schedule' | 'news';
export interface CustomItem {
  id: CustomWidget;
  x: number;
  y: number;
  w: number;
  h: number;
}

/** 앱 지수 자세히 */
export interface MarketDetailProps {
  index: MarketIndex;
  days: string[];
  /** 위 바 (밀려 들어오는 화면 셸) */
  header: ReactNode;
  /** 원/달러 자세히: 투자 실험실 넛지 */
  onNudge?: () => void;
}
