import type { Market, StockStatus } from '@/types/models';

/** 종목 머리 (메모 보드 · 기업정보 위) — 웹·앱 같은 데이터 */
export interface StockHeadProps {
  stock_code: string;
  name: string;
  market: Market;
  status: StockStatus;
  logo: string;
  logo_bg: string;
  logo_ink?: string;
  price: number;
  change: number;
  change_pct: number;
  /** 종가 날짜 'MM.DD' (규칙 7: 'MM.DD 종가 기준') */
  as_of: string;
  /** 최근 종가 (작은 선) */
  closes: number[];
}
