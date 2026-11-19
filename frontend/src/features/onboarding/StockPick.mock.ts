/** 첫 종목 고르기 예시 — 체험판 '많이 찾는 종목' 12개 (가입 화면은 웹처럼 NAVER 표기) */
import type { StockPickProps } from '@/features/onboarding/StockPick.types';

export const mockStockPickProps: StockPickProps = {
  stocks: [
    { stock_code: '005930', name: '삼성전자', logo_text: '삼', logo_bg: '#1428A0' },
    { stock_code: '000660', name: 'SK하이닉스', logo_text: 'S', logo_bg: '#EA002C' },
    { stock_code: '035420', name: 'NAVER', logo_text: 'N', logo_bg: '#03C75A' },
    { stock_code: '105560', name: 'KB금융', logo_text: 'K', logo_bg: '#FFBC00', logo_fg: '#1A1A1A' },
    { stock_code: '373220', name: 'LG에너지솔루션', logo_text: 'L', logo_bg: '#A50034' },
    { stock_code: '207940', name: '삼성바이오로직스', logo_text: '삼', logo_bg: '#1428A0' },
    { stock_code: '005380', name: '현대차', logo_text: '현', logo_bg: '#002C5F' },
    { stock_code: '000270', name: '기아', logo_text: '기', logo_bg: '#05141F' },
    { stock_code: '068270', name: '셀트리온', logo_text: '셀', logo_bg: '#0A6CB6' },
    { stock_code: '035720', name: '카카오', logo_text: '카', logo_bg: '#FEE500', logo_fg: '#1A1A1A' },
    { stock_code: '055550', name: '신한지주', logo_text: '신', logo_bg: '#0046FF' },
    { stock_code: '012450', name: '한화에어로스페이스', logo_text: '한', logo_bg: '#F37321' },
  ],
  selected: ['000660', '005930', '035420'],
  onToggle: () => {},
  onOpenHolding: () => {},
  onNext: () => {},
  onSkip: () => {},
};
