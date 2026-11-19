import type { Candle, ChartRange, StockProfile } from '@/types/models';
import { mockBoardStock, mockEmptyStock } from '@/ui/screens/board/MemoBoard.mock';
import type { CompanyInfoProps } from './CompanyInfo.types';
import { candlesKB, candlesSK, finKB, finSK, quoteKB, quoteSK, type CandleRow } from './companyData.mock';

/**
 * 기업정보 예시 — 일반 종목(SK하이닉스) · 금융업 종목(KB금융). 값은 companyData.mock.ts (웹 예시 계정 11.18 종가 기준).
 * 기업 개요: SK하이닉스는 웹 원본 ABOUT, KB금융은 웹 원본이 overview·sector 로 만드는 문장.
 */
const toCandles = (rows: CandleRow[]): Candle[] => rows.map(([date, open, high, low, close, volume]) => ({ date, open, high, low, close, volume }));
const candleSet = (c: Record<ChartRange, CandleRow[]>) => ({ '1W': toCandles(c['1W']), '1M': toCandles(c['1M']), '3M': toCandles(c['3M']), '1Y': toCandles(c['1Y']) });
const profile = (q: typeof quoteSK, name: string, overview: string): StockProfile => ({
  code: q.stock_code,
  name,
  market: 'KOSPI',
  overview,
  prev_close: q.prev_close,
  open: q.open,
  high: q.high,
  low: q.low,
  volume: q.volume,
  trading_value: q.value,
  per: q.per,
  pbr: q.pbr,
  eps: q.eps,
  bps: q.bps,
  market_cap: q.market_cap,
  shares_outstanding: Math.round(q.market_cap / q.price),
  week52_low: q.w52_low,
  week52_high: q.w52_high,
});

type Data = Omit<CompanyInfoProps, 'onBack' | 'onMore' | 'onChangeTab' | 'onNudge'>;

export const mockCompanySK: Data = {
  stock: mockBoardStock,
  profile: profile(quoteSK, 'SK하이닉스', 'SK하이닉스는 DRAM과 NAND 플래시 등 메모리 반도체를 설계·제조하는 기업입니다. AI 서버용 고대역폭 메모리(HBM)를 비롯한 고성능 메모리 제품을 공급하며, 반도체 업황과 AI 수요에 따라 실적이 크게 움직이는 종목이에요.'),
  quote_as_of: quoteSK.as_of,
  candles: candleSet(candlesSK),
  quarters: finSK.quarters,
  health: finSK.health,
  health_as_of: finSK.as_of,
  financial: false,
};

export const mockCompanyKB: Data = {
  stock: mockEmptyStock,
  profile: profile(quoteKB, 'KB금융', 'KB국민은행을 둔 국내 대표 금융지주이에요. 금융 업종으로, 업황과 실적 발표에 따라 주가가 움직이는 종목이에요.'),
  quote_as_of: quoteKB.as_of,
  candles: candleSet(candlesKB),
  quarters: finKB.quarters,
  health: finKB.health,
  health_as_of: finKB.as_of,
  financial: true,
};

export const mockCompanyByCode = (code: string): Data => (code === mockEmptyStock.stock_code ? mockCompanyKB : mockCompanySK);
