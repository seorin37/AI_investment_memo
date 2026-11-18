/** 내 종목 예시 — 체험판 (보유 1 · 관심 2, 11.12 종가) */
import type { MyStocksProps } from '@/features/stock/MyStocks.types';

export const mockMyStocksProps: MyStocksProps = {
  close_date: '11.12',
  stocks: [
    { stock_code: '000660', name: 'SK하이닉스', logo_text: 'S', logo_bg: '#EA002C', status: 'holding', close: 180500, change_rate: 2.38, memo_count: 5, ai_memo_count: 3, new_count: 3 },
    { stock_code: '005930', name: '삼성전자', logo_text: '삼', logo_bg: '#1428A0', status: 'watching', close: 71400, change_rate: 2.15, memo_count: 2, ai_memo_count: 0, new_count: 2 },
    { stock_code: '035420', name: '네이버', logo_text: '네', logo_bg: '#03C75A', status: 'watching', close: 212300, change_rate: 1.29, memo_count: 1, ai_memo_count: 1, new_count: 0 },
  ],
  onOpenStock: () => {},
  onAddStock: () => {},
  onLongPressStock: () => {},
};
