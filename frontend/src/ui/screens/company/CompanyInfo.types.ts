import type { Candle, ChartRange, ISODate, StockProfile } from '@/types/models';
import type { StockHeadProps } from '@/ui/shared/StockHead.types';

/**
 * 분기 재무 한 줄 (DART 정기보고서 · 연결). 금액은 억원, 비율은 %.
 * 금융업은 매출·영업이익(·이익률)을 공시하지 않아 null → 화면에 '—'.
 * models.Financials 는 연간만 있어서, 분기 화면에 필요한 모양을 여기 둠 (API 연결 단계에서 맞춤).
 */
export interface CompanyQuarter {
  /** '26.3Q' */
  q: string;
  /** '2026년 3분기' */
  label: string;
  revenue: number | null;
  op: number | null;
  net: number | null;
  op_margin: number | null;
  net_margin: number | null;
  roe: number | null;
  roa: number | null;
}

/** 기업 건전성 (최근 분기 재무상태표). 금융업은 유동·당좌·이자보상이 없어 null */
export interface CompanyHealth {
  debt: number | null;
  current: number | null;
  quick: number | null;
  interest: number | null;
  reserve: number | null;
}

/** 기업정보 (웹·앱 같은 props) */
export interface CompanyInfoProps {
  /** 종목 머리 (메모 보드와 같은 카드) */
  stock: StockHeadProps;
  /** 시세·투자정보·기업 개요 (전일 확정 값) */
  profile: StockProfile;
  /** 시세 기준 시각 (전일 종가) */
  quote_as_of: ISODate;
  /** 기간별 캔들 (1W·1M·3M 일봉 · 1Y 주봉), 오래된 → 최근 */
  candles: Record<ChartRange, Candle[]>;
  /** 분기 재무 12개 (오래된 → 최근). 화면은 뒤 8개, 앞 4개는 전년 동기 비교 */
  quarters: CompanyQuarter[];
  health: CompanyHealth;
  /** 건전성 기준 분기 말 'YYYY-MM-DD' */
  health_as_of: string;
  /** 금융업 (은행·지주 등): 매출·영업이익 — · 금융업 안내 */
  financial: boolean;
  /** 시범 종목 밖: 차트·재무를 지어내지 않고 '준비 중' */
  preparing?: boolean;

  onBack: () => void;
  onMore?: () => void;
  /** 메모 보드 ↔ 기업정보 */
  onChangeTab: (tab: 'board' | 'company') => void;
  /** 넛지: 공시·재무 요약 (주간보고서) */
  onNudge?: () => void;
}
