import type { FirstHomeStock } from './FirstHome.types';
import type { OnboardingStock, StockStatus } from './Onboarding.types';

export const mockOnboardingStocks: OnboardingStock[] = [
  { stock_code: '005930', name: '삼성전자', market: 'KOSPI', category: '반도체', logo: '삼', logo_bg: '#1D4ED8' },
  { stock_code: '000660', name: 'SK하이닉스', market: 'KOSPI', category: '반도체', logo: 'SK', logo_bg: '#E11D48' },
  { stock_code: '373220', name: 'LG에너지솔루션', market: 'KOSPI', category: '2차전지', logo: 'LG', logo_bg: '#A50034' },
  { stock_code: '005380', name: '현대차', market: 'KOSPI', category: '자동차', logo: 'H', logo_bg: '#002C5F' },
  { stock_code: '207940', name: '삼성바이오로직스', market: 'KOSPI', category: '바이오', logo: 'S', logo_bg: '#2563EB' },
  { stock_code: '035420', name: 'NAVER', market: 'KOSPI', category: '플랫폼', logo: 'N', logo_bg: '#03C75A' },
  { stock_code: '035720', name: '카카오', market: 'KOSPI', category: '플랫폼', logo: 'K', logo_bg: '#FEE500', logo_ink: '#181600' },
  { stock_code: '068270', name: '셀트리온', market: 'KOSPI', category: '바이오', logo: 'C', logo_bg: '#1769AA' },
  { stock_code: '105560', name: 'KB금융', market: 'KOSPI', category: '금융', logo: 'KB', logo_bg: '#FFBC00', logo_ink: '#3B3023' },
  { stock_code: '055550', name: '신한지주', market: 'KOSPI', category: '금융', logo: '신', logo_bg: '#0B63CE' },
  { stock_code: '006400', name: '삼성SDI', market: 'KOSPI', category: '2차전지', logo: 'SDI', logo_bg: '#183883' },
  { stock_code: '051910', name: 'LG화학', market: 'KOSPI', category: '화학', logo: 'LG', logo_bg: '#A50034' },
  { stock_code: '005490', name: 'POSCO홀딩스', market: 'KOSPI', category: '소재', logo: 'P', logo_bg: '#055AA3' },
  { stock_code: '028260', name: '삼성물산', market: 'KOSPI', category: '지주', logo: '삼', logo_bg: '#3157A4' },
  { stock_code: '012330', name: '현대모비스', market: 'KOSPI', category: '자동차', logo: 'M', logo_bg: '#002C5F' },
  { stock_code: '086790', name: '하나금융지주', market: 'KOSPI', category: '금융', logo: 'H', logo_bg: '#009490' },
  { stock_code: '034730', name: 'SK', market: 'KOSPI', category: '지주', logo: 'SK', logo_bg: '#E11D48' },
  { stock_code: '003670', name: '포스코퓨처엠', market: 'KOSPI', category: '2차전지', logo: 'P', logo_bg: '#055AA3' },
];

/**
 * 앱 종목 고르기 '많이 찾는 종목' 12개 = 원본 app/login.html renderS2 의 STK[0..11] (순서·로고 글자·색 그대로).
 * 실제 데이터 출처 없음: '많이 찾는' 순위는 서버 계약이 생기면 그쪽 값으로 바꾼다.
 */
export const mockAppPopularStocks: OnboardingStock[] = [
  { stock_code: '005930', name: '삼성전자', market: 'KOSPI', category: '반도체', logo: '삼', logo_bg: '#1428A0' },
  { stock_code: '000660', name: 'SK하이닉스', market: 'KOSPI', category: '반도체', logo: 'S', logo_bg: '#EA002C' },
  { stock_code: '035420', name: 'NAVER', market: 'KOSPI', category: '인터넷', logo: 'N', logo_bg: '#03C75A' },
  { stock_code: '105560', name: 'KB금융', market: 'KOSPI', category: '금융', logo: 'K', logo_bg: '#FFBC00', logo_ink: '#1A1A1A' },
  { stock_code: '373220', name: 'LG에너지솔루션', market: 'KOSPI', category: '2차전지', logo: 'L', logo_bg: '#A50034' },
  { stock_code: '207940', name: '삼성바이오로직스', market: 'KOSPI', category: '바이오', logo: '삼', logo_bg: '#1428A0' },
  { stock_code: '005380', name: '현대차', market: 'KOSPI', category: '자동차', logo: '현', logo_bg: '#002C5F' },
  { stock_code: '000270', name: '기아', market: 'KOSPI', category: '자동차', logo: '기', logo_bg: '#05141F' },
  { stock_code: '068270', name: '셀트리온', market: 'KOSPI', category: '바이오', logo: '셀', logo_bg: '#0A6CB6' },
  { stock_code: '012450', name: '한화에어로스페이스', market: 'KOSPI', category: '조선·방산', logo: '한', logo_bg: '#F37321' },
  { stock_code: '329180', name: 'HD현대중공업', market: 'KOSPI', category: '조선·방산', logo: 'H', logo_bg: '#0A6E8A' },
  { stock_code: '055550', name: '신한지주', market: 'KOSPI', category: '금융', logo: '신', logo_bg: '#0046FF' },
];

/** 첫 홈(원본 start.html)은 NAVER 를 '네이버' · 로고 '네' 로 보여 준다 (11.17 웹 통일) */
export const mockFirstHomeNameOverride: Record<string, { name: string; logo: string }> = {
  '035420': { name: '네이버', logo: '네' },
};

/**
 * 가입 흐름 query 'selected' (예: '000660:holding,005930:watching') → 첫 홈 종목.
 * 서버 상태가 아니라 이번 흐름의 임시 값 (웹·앱 host 와 같은 형식). 실제로는 내 종목 API 로 바꾼다.
 */
export function mockFirstHomeStocks(selected: string | undefined, memo?: { stock_code: string; ai: boolean } | null): FirstHomeStock[] {
  const all = [...mockAppPopularStocks, ...mockOnboardingStocks];
  return (selected ?? '')
    .split(',')
    .map((v) => v.split(':'))
    .filter(([code]) => !!code)
    .map(([code, status]) => {
      const base = all.find((s) => s.stock_code === code);
      if (!base) return null;
      const o = mockFirstHomeNameOverride[code];
      const has = memo?.stock_code === code;
      return { ...base, ...(o ? { name: o.name, logo: o.logo } : null), status: (status === 'holding' ? 'holding' : 'watching') as StockStatus, memo_count: has ? 1 : 0, ai_count: has && memo?.ai ? 1 : 0 };
    })
    .filter((s): s is FirstHomeStock => s !== null);
}
