import type { NativeScrollEvent, NativeSyntheticEvent } from 'react-native';
import type { StockStatus } from '@/types/models';

/** 내 종목 줄 1개 */
export interface MyStockRow {
  stock_code: string;
  name: string;
  logo_text: string;
  logo_bg: string;
  logo_fg?: string;
  status: StockStatus; // 'holding' | 'watching'
  close: number;
  change_rate: number; // %
  memo_count: number;
  ai_memo_count: number;
  new_count: number;
  /** 시범 4종목 밖이라 AI 연결을 아직 못 켜는 종목 */
  ai_unavailable?: boolean;
}

export type MyStocksFilter = 'all' | StockStatus;

export interface MyStocksProps {
  stocks: MyStockRow[];
  close_date: string; // 'MM.DD'
  onOpenStock: (stock_code: string) => void;
  onAddStock: () => void;
  /** 꾹 누름 → 고르기(보유↔관심 옮기기 · 빼기 · 순서 바꾸기)는 호스트에서 */
  onLongPressStock: (stock_code: string) => void;
  /** 순서 바꾸기 중이면 줄 오른쪽에 ⋮⋮ 손잡이가 생기고 끌어서 옮김 (Lucian #317) */
  reorder_mode?: boolean;
  /** 보유 또는 관심 묶음 안의 새 순서 (stock_code 차례) */
  onReorder?: (status: StockStatus, stock_codes: string[]) => void;
  /** 스크롤 위치를 호스트로 (Lucian #332 큰 제목 접기 · TopBar 아래 선): useLargeTitle().onScroll 을 넘김 */
  onScroll?: (e: NativeSyntheticEvent<NativeScrollEvent>) => void;
}
