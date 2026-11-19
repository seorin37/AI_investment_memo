import type { SideStock } from './WebShell.types';

/** 예시 계정 (원본 웹 시연 '예시 계정': 보유 SK하이닉스 · 관심 삼성전자 · 네이버) */
export const mockSideStocks: SideStock[] = [
  { stock_code: '000660', name: 'SK하이닉스', status: 'holding', logo: 'S', logo_bg: '#EA002C' },
  { stock_code: '005930', name: '삼성전자', status: 'watching', logo: '삼', logo_bg: '#1428A0' },
  { stock_code: '035420', name: '네이버', status: 'watching', logo: '네', logo_bg: '#03C75A' },
];

export const mockSideProfile = { name: '김나라', job: '대학생', photoUrl: null };

export const mockRecentSearches = ['SK하이닉스', '삼성전자'];

export const mockPopular = [
  { stock_code: '005930', name: '삼성전자', mine: true },
  { stock_code: '000660', name: 'SK하이닉스', mine: true },
  { stock_code: '005380', name: '현대차', mine: false },
  { stock_code: '105560', name: 'KB금융', mine: false },
];

export const mockUnreadNotifs = 3;

export const mockStudioHead = { stockCount: 3, aiMemoCount: 5, usagePct: 38 };
