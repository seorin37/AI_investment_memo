/** 가입: 첫 종목 고르기 (많이 찾는 종목 12개 · 검색·업종 탭 없음 · 11.13 결정) */
export interface PickStock {
  stock_code: string;
  name: string;
  logo_text: string;
  logo_bg: string;
  logo_fg?: string;
}

export interface StockPickProps {
  stocks: PickStock[];
  /** 고른 종목 코드 (순서 = 고른 순서) */
  selected: string[];
  onToggle: (stock_code: string) => void;
  /** 아래 트레이 [보유·관심 정하기 ›] → 보유/관심 시트 (호스트) */
  onOpenHolding: () => void;
  onNext: () => void;
  onSkip: () => void;
}
