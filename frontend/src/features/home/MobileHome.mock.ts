/** 모바일 홈 예시 — 체험판 home.html (11.12 종가 기준) */
import type { MobileHomeProps } from '@/features/home/MobileHome.types';

const noop = () => {};

export const mockMobileHomeProps: MobileHomeProps = {
  user_name: '김나라',
  new_count: 5,
  holding_count: 1,
  watching_count: 2,
  ai_memo_count: 4,
  market: [
    { key: 'kospi', name: '코스피', value: 2650.35, change: -12.4, change_rate: -0.47, close_date: '11.12', closes: [2671.2, 2668.4, 2675.9, 2662.1, 2669.3, 2658.7, 2664.0, 2655.2, 2660.8, 2650.35] },
    { key: 'kosdaq', name: '코스닥', value: 850.12, change: -4.18, change_rate: -0.49, close_date: '11.12', closes: [846.1, 848.0, 845.2, 849.7, 851.3, 849.0, 853.2, 852.4, 854.3, 850.12] },
    { key: 'usd', name: '원/달러', value: 1350.2, change: 3.2, change_rate: 0.24, close_date: '11.12', closes: [1344.1, 1347.0, 1342.8, 1349.5, 1346.2, 1351.0, 1348.3, 1352.6, 1347.0, 1350.2] },
  ],
  updates: [
    { stock_code: '000660', name: 'SK하이닉스', logo_text: 'S', logo_bg: '#EA002C', status: 'holding', new_count: 3 },
    { stock_code: '005930', name: '삼성전자', logo_text: '삼', logo_bg: '#1428A0', status: 'watching', new_count: 2 },
    { stock_code: '035420', name: '네이버', logo_text: '네', logo_bg: '#03C75A', status: 'watching', new_count: 0 },
  ],
  news_total_today: 8,
  news: [
    { id: 'n0', time: '13:12', title: '반도체 강세에 코스피 상승 출발', source: '연합뉴스' },
    { id: 'n1', time: '12:48', title: 'SK하이닉스, HBM4 공급 확대 기대감에 강세', source: '한국경제' },
    { id: 'n2', time: '11:30', title: '외국인, 이틀 연속 반도체 순매수', source: '매일경제' },
    { id: 'n3', time: '10:05', title: '3분기 실적 시즌 개막…IT·반도체 주목', source: '서울경제' },
  ],
  onOpenUpdates: noop,
  onOpenMarket: noop,
  onRetryMarket: noop,
  onOpenStockUpdates: noop,
  onOpenNews: noop,
};
