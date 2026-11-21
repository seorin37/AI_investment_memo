import type { ReactNode } from 'react';

export type Hold = 'holding' | 'watching';

/** 내 종목 한 줄 (가격은 전일 확정 종가) */
export interface MyStock {
  stock_code: string;
  name: string;
  logo: string;
  logo_bg: string;
  logo_ink?: string;
  market: string;
  status: Hold;
  memo_count: number;
  ai_count: number;
  /** 읽지 않은 새 소식 */
  new_count: number;
  /** 전일 확정 종가 */
  price: number;
  /** 전일 대비 % */
  change_pct: number;
  /** AI 연결 가능한 종목 (시범 종목) */
  ai_ready: boolean;
}

/** 종목 추가 후보 (종목 마스터) */
export interface StockCandidate {
  stock_code: string;
  name: string;
  logo: string;
  logo_bg: string;
  logo_ink?: string;
  market: string;
  /** 웹 종목 추가 창의 분야 칩 */
  sector: string;
  ai_ready: boolean;
  /** 전일 확정 종가 · 등락률 (추가하면 줄에 바로 보임) */
  price: number;
  change_pct: number;
}

export interface MyStocksData {
  stocks: MyStock[];
  /** 시세 기준일 YYYY-MM-DD */
  as_of: string;
  /** 종목 추가: 검색 대상 · 처음에 보이는 많이 찾는 종목 */
  universe: StockCandidate[];
  popular: string[];
}

export interface MyStocksCallbacks {
  onOpenStock: (code: string) => void;
  onAdd: (code: string, hold: Hold) => void;
  /** 보유 ↔ 관심 옮기기 */
  onMove: (codes: string[], hold: Hold) => void;
  onRemove: (codes: string[]) => void;
  /** 되돌리기: 빼기·옮기기 전 상태로 */
  onRestore: (snapshot: MyStock[]) => void;
  /** 같은 묶음 안 순서 (전체 순서) */
  onReorder: (codes: string[]) => void;
  /** 추가 뒤 [메모 쓰기] */
  onWriteMemo: (code: string) => void;
}

export interface AppMyStocksProps extends MyStocksData, MyStocksCallbacks {
  header: (o: { onSearch: () => void }) => ReactNode;
  /** 선택 모드면 탭바를 숨김 */
  onSelectionChange?: (n: number) => void;
}

export interface WebMyStocksProps extends MyStocksData, MyStocksCallbacks {
  onOpenCompany: (code: string) => void;
}

/** 웹 종목 추가 창 (내 종목 · 사이드바 + 에서 같이 씀) */
export interface AddStockProps {
  open: boolean;
  mine: MyStock[];
  universe: StockCandidate[];
  popular: string[];
  onClose: () => void;
  onAdd: (code: string, hold: Hold) => void;
}
