import type { ChartRange } from '@/types/models';
import type { StockSummary, StockTab } from '@/components/mobile/StockSummaryCard';

/** 모바일 기업정보 (기존 웹용 CompanyInfo 와 이름이 겹치지 않게 CompanyOverview) */

export interface CompanyCandle {
  date: string; // 'MM.DD'
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/** 시세·투자정보 칸 (값이 없으면 null → '—') */
export interface CompanyMetric {
  key: string; // 'per' · 'pbr' · 'eps' · 'bps' · 'mc' · 'sh' ...
  label: string;
  value: string | null;
  /** ? 버튼으로 설명을 띄울 수 있는 지표 */
  has_help?: boolean;
}

/** 분기별 값 (성장성 = 조원, 수익성 = %) */
export interface CompanySeries {
  key: string;
  label: string;
  color: string;
  values: (number | null)[];
}

export interface CompanyHealthItem {
  key: string; // 'debt' · 'cur' · 'quick' · 'icr' · 'ret'
  label: string; // '부채비율'
  value: string; // '58%'
  /** 0~1 (바깥쪽일수록 안정적) — 점수화는 프론트 규칙 */
  score: number;
}

export interface CompanyOverviewProps {
  stock: StockSummary;
  onChangeTab: (tab: StockTab) => void;
  /** 시범 4종목 밖 종목: 차트·재무를 지어내지 않고 "준비 중" 카드 */
  not_ready?: boolean;
  /** 불러오는 중이면 빛줄기 뼈대 (#079) */
  loading?: boolean;
  onGoBoard: () => void;
  range: ChartRange; // '1W' | '1M' | '3M' | '1Y'
  onChangeRange: (range: ChartRange) => void;
  candles: CompanyCandle[];
  week52_low: string;
  week52_high: string;
  /** 전일 · 시가 · 고가 · 저가 · 거래량 · 거래대금 */
  quote_rows: { label: string; value: string }[];
  metrics: CompanyMetric[];
  overview: string;
  quarters: string[]; // ['24.3Q', ... ]
  growth: CompanySeries[]; // 매출 · 영업이익 · 순이익 (조원)
  profitability: CompanySeries[]; // 영업이익률 · 순이익률 · ROE (11.18 ROA 뺌)
  health_basis: string; // '2026년 6월 기준'
  health: CompanyHealthItem[];
  onHelp: (key: string) => void;
}
