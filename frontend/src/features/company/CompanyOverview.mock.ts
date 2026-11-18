/** 기업정보 예시 — 체험판 SK하이닉스 (웹 v2와 같은 계산값 · 11.12 종가 · 수익성 3개) */
import type { CompanyOverviewProps } from '@/features/company/CompanyOverview.types';
import { mockStockSk } from '@/features/board/MemoBoard.mock';

const noop = () => {};

export const mockCompanyOverviewProps: CompanyOverviewProps = {
  stock: mockStockSk,
  onChangeTab: noop,
  onGoBoard: noop,
  range: '1M',
  onChangeRange: noop,
  candles: [
    { date: '10.08', open: 150200, high: 152600, low: 148500, close: 152000, volume: 2280000 },
    { date: '10.09', open: 152100, high: 155600, low: 151700, close: 154500, volume: 3370000 },
    { date: '10.12', open: 153700, high: 154900, low: 151400, close: 151800, volume: 2330000 },
    { date: '10.13', open: 151700, high: 157200, low: 151100, close: 155200, volume: 2660000 },
    { date: '10.14', open: 155400, high: 159700, low: 153900, close: 157400, volume: 3090000 },
    { date: '10.15', open: 158300, high: 160500, low: 156200, close: 160100, volume: 2820000 },
    { date: '10.16', open: 159500, high: 160000, low: 158000, close: 158900, volume: 4140000 },
    { date: '10.19', open: 158300, high: 165000, low: 156700, close: 163500, volume: 3030000 },
    { date: '10.20', open: 163600, high: 167600, low: 163200, close: 167200, volume: 2610000 },
    { date: '10.21', open: 167500, high: 172200, low: 166500, close: 171000, volume: 3560000 },
    { date: '10.22', open: 170900, high: 176200, low: 168900, close: 175300, volume: 3850000 },
    { date: '10.23', open: 174800, high: 180400, low: 173400, close: 178900, volume: 4290000 },
    { date: '10.26', open: 179300, high: 180200, low: 174800, close: 177200, volume: 2400000 },
    { date: '10.27', open: 177100, high: 179000, low: 175900, close: 176500, volume: 3320000 },
    { date: '10.28', open: 175700, high: 181500, low: 173800, close: 179800, volume: 3530000 },
    { date: '10.29', open: 180500, high: 181500, low: 176600, close: 178400, volume: 3590000 },
    { date: '10.30', open: 178500, high: 183400, low: 176400, close: 182100, volume: 4460000 },
    { date: '11.02', open: 182100, high: 183800, low: 180500, close: 180900, volume: 3850000 },
    { date: '11.03', open: 181200, high: 186700, low: 179200, close: 184300, volume: 2810000 },
    { date: '11.04', open: 184100, high: 185800, low: 181400, close: 181700, volume: 3250000 },
    { date: '11.05', open: 181100, high: 184100, low: 180700, close: 183600, volume: 4020000 },
    { date: '11.06', open: 182900, high: 183700, low: 179400, close: 180500, volume: 4280000 },
  ],
  week52_low: '140,000',
  week52_high: '299,500',
  quote_rows: [
    { label: '전일', value: '174,400' },
    { label: '시가', value: '175,000' },
    { label: '고가', value: '181,200' },
    { label: '저가', value: '174,800' },
    { label: '거래량', value: '3,214,560주' },
    { label: '거래대금', value: '5,742억' },
  ],
  metrics: [
    { key: 'mc', label: '시가총액', value: '131.4조', has_help: true },
    { key: 'sh', label: '상장주수', value: '7.28억주', has_help: true },
    { key: 'per', label: 'PER', value: '3.06배', has_help: true },
    { key: 'pbr', label: 'PBR', value: '1.90배', has_help: true },
    { key: 'eps', label: 'EPS', value: '58,980원', has_help: true },
    { key: 'bps', label: 'BPS', value: '95,100원', has_help: true },
  ],
  overview: 'SK하이닉스는 DRAM과 NAND 플래시 등 메모리 반도체를 설계·제조하는 기업입니다. AI 서버용 고대역폭 메모리(HBM)를 비롯한 고성능 메모리 제품을 공급하며, 반도체 업황과 AI 수요에 따라 실적이 크게 움직이는 종목이에요.',
  quarters: ['24.3Q', '24.4Q', '25.1Q', '25.2Q', '25.3Q', '25.4Q', '26.1Q', '26.2Q'],
  growth: [
    { key: 'rev', label: '매출', color: '#B9A8DA', values: [17.6, 19.8, 17.6, 22.2, 24.4, 33.5, 30.1, 33.5] },
    { key: 'op', label: '영업이익', color: '#B9A8DA', values: [7.0, 8.1, 7.4, 9.2, 11.4, 16.8, 14.2, 16.1] },
    { key: 'ni', label: '순이익', color: '#B9A8DA', values: [5.8, 8.0, 8.1, 7.0, 12.6, 13.2, 11.8, 13.9] },
  ],
  profitability: [
    { key: 'opm', label: '영업이익률', color: '#16171A', values: [39.8, 40.9, 42.0, 41.4, 46.7, 50.1, 47.2, 48.1] },
    { key: 'npm', label: '순이익률', color: '#3D73F0', values: [33.0, 40.4, 46.0, 31.5, 51.6, 39.4, 39.2, 41.5] },
    { key: 'roe', label: 'ROE', color: '#E5484D', values: [18.2, 21.5, 22.0, 19.4, 28.1, 27.3, 24.0, 25.6] },
  ],
  health_basis: '2026년 6월 기준',
  health: [
    { key: 'debt', label: '부채비율', value: '58%', score: 0.72 },
    { key: 'cur', label: '유동비율', value: '170%', score: 0.78 },
    { key: 'quick', label: '당좌비율', value: '125%', score: 0.64 },
    { key: 'icr', label: '이자보상비율', value: '25배', score: 0.7 },
    { key: 'ret', label: '유보율', value: '1,750%', score: 0.9 },
  ],
  onHelp: noop,
};

/** 시범 4종목 밖 (예: 기아) — 준비 중 */
export const mockCompanyNotReadyProps: CompanyOverviewProps = {
  ...mockCompanyOverviewProps,
  stock: { ...mockStockSk, stock_code: '000270', name: '기아', logo_text: '기', logo_bg: '#05141F', status: 'watching', close: 101300, change_amount: 300, change_rate: 0.3 },
  not_ready: true,
};
