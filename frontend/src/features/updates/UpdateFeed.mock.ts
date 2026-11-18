/** 최신 업데이트 예시 — 체험판/웹 v2와 같은 9건 (SK 3 · 삼성 3 · 네이버 3, 읽지 않은 소식 5) */
import type { FeedStock, UpdateFeedProps } from '@/features/updates/UpdateFeed.types';

export const mockFeedStocks: FeedStock[] = [
  {
    stock_code: '000660', name: 'SK하이닉스', market: 'KOSPI', logo_text: 'S', logo_bg: '#EA002C', status: 'holding',
    items: [
      { id: 'a1', type: 'disclosure', title: '신규 시설투자 관련 공시', ago: '2시간 전', unread: true },
      { id: 'a2', type: 'news', title: 'HBM4 공급 확대 기대감', ago: '1일 전', unread: true },
      { id: 'a3', type: 'price', title: '11.03 종가 +7.1%', ago: '2일 전', unread: true },
    ],
  },
  {
    stock_code: '005930', name: '삼성전자', market: 'KOSPI', logo_text: '삼', logo_bg: '#1428A0', status: 'watching',
    items: [
      { id: 'b1', type: 'disclosure', title: '자기주식 취득 결정 관련 공시', ago: '2시간 전', unread: true },
      { id: 'b3', type: 'price', title: '11.05 종가 +2.1%', ago: '3시간 전', unread: false },
      { id: 'b2', type: 'news', title: 'HBM4 공급 확대 기대감', ago: '1일 전', unread: true },
    ],
  },
  {
    stock_code: '035420', name: '네이버', market: 'KOSPI', logo_text: '네', logo_bg: '#03C75A', status: 'watching',
    items: [
      { id: 'c1', type: 'disclosure', title: '사업보고서 제출 관련 공시', ago: '1시간 전', unread: false },
      { id: 'c2', type: 'news', title: 'AI 검색 서비스 개편 기대감', ago: '5시간 전', unread: false },
      { id: 'c3', type: 'price', title: '11.04 종가 +1.3%', ago: '1일 전', unread: false },
    ],
  },
];

export const mockUpdateFeedProps: UpdateFeedProps = {
  stocks: mockFeedStocks,
  selected_stock: null,
  onSelectStock: () => {},
  onOpenStock: () => {},
  onOpenItem: () => {},
};
