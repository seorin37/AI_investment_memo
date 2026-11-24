import type { MyStock, MyStocksData, StockCandidate } from './MyStocks.types';

/**
 * 내 종목 예시 — 웹 예시 계정(11.18 종가 기준 · ⑤ 기업정보와 같은 SK하이닉스 180,500원).
 * 메모·AI 연결·새 소식 수는 메모 보드(③)·홈(②)·업데이트(⑥) 예시와 같게.
 */
export const mockMyStocks: MyStock[] = [
  { stock_code: '000660', name: 'SK하이닉스', logo: 'S', logo_bg: '#EA002C', market: 'KOSPI', status: 'holding', memo_count: 5, ai_count: 3, new_count: 2, price: 180500, change_pct: 0.95, ai_ready: true },
  { stock_code: '005930', name: '삼성전자', logo: '삼', logo_bg: '#1428A0', market: 'KOSPI', status: 'watching', memo_count: 2, ai_count: 1, new_count: 0, price: 71400, change_pct: 0.28, ai_ready: true },
  { stock_code: '035420', name: '네이버', logo: '네', logo_bg: '#03C75A', market: 'KOSPI', status: 'watching', memo_count: 1, ai_count: 1, new_count: 1, price: 212500, change_pct: -1.16, ai_ready: true },
];

const C = (stock_code: string, name: string, logo: string, logo_bg: string, sector: string, price: number, change_pct: number, ai_ready = false, logo_ink?: string): StockCandidate => ({ stock_code, name, logo, logo_bg, logo_ink, market: 'KOSPI', sector, ai_ready, price, change_pct });

/** 종목 마스터 예시 (원본 stock.html M · 웹 universe 의 분야 · 가격은 화면 예시 — 삼성전자우는 원본 앱 목록에 없어 예시 값) */
export const mockUniverse: StockCandidate[] = [
  C('000660', 'SK하이닉스', 'S', '#EA002C', '반도체', 180500, 0.95, true),
  C('005930', '삼성전자', '삼', '#1428A0', '반도체', 71400, 0.28, true),
  C('035420', '네이버', '네', '#03C75A', '인터넷', 212500, -1.16, true),
  C('105560', 'KB금융', 'K', '#FFBC00', '금융', 78300, -0.51, true, '#1A1A1A'),
  C('005380', '현대차', '현', '#002C5F', '자동차', 238500, -0.62),
  C('000270', '기아', '기', '#05141F', '자동차', 101300, 0.3),
  C('055550', '신한지주', '신', '#0046FF', '금융', 52800, 0.57),
  C('086790', '하나금융지주', '하', '#008485', '금융', 63100, 0.32),
  C('316140', '우리금융지주', '우', '#0067AC', '금융', 15420, -0.13),
  C('035720', '카카오', 'K', '#FEE500', '인터넷', 37650, -1.05, false, '#1A1A1A'),
  C('373220', 'LG에너지솔루션', 'LG', '#A50034', '2차전지', 351500, -0.85),
  C('207940', '삼성바이오로직스', '삼', '#1A4D9C', '바이오', 1012000, 0.4),
  C('012450', '한화에어로스페이스', '한', '#F37321', '방산', 412000, 3.12),
  C('005490', 'POSCO홀딩스', 'P', '#05507D', '철강', 318000, -0.47),
  C('005935', '삼성전자우', '삼', '#1428A0', '반도체', 58200, 0.17),
];

export const mockMyStocksData: MyStocksData = {
  stocks: mockMyStocks,
  as_of: '2026-11-18',
  universe: mockUniverse,
  /* 앱 시트 '많이 찾는 종목 · 예시' (원본 sheetList) */
  popular: ['105560', '005380', '000270', '055550', '000660'],
};
