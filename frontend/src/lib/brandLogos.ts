/**
 * 종목 로고 대표색 (2026-11-23). 실제 API 에 로고·색 칸이 없어(api-inventory C-6: 로고는 프론트 규칙) 프론트 상수로 둔다.
 * - 값은 Home.mock.ts 앱 검색 12종목(원본 home.html STK)과 같다. mock 파일을 import 하지 않으려고 따로 둔다.
 * - 표에 없는 종목은 useCompanyInfo 의 fallbackLogo 가 지금 규칙(이름 첫 글자 + 코드로 고른 색)으로 정한다.
 */
export interface BrandLogo {
  logo: string;
  logo_bg: string;
  /** 글자 색 (없으면 흰색). 밝은 바탕(노랑)만 어둡게 */
  logo_ink?: string;
}

export const BRAND_LOGOS: Readonly<Record<string, BrandLogo>> = {
  '005930': { logo: '삼', logo_bg: '#1428A0' }, // 삼성전자
  '000660': { logo: 'S', logo_bg: '#EA002C' }, // SK하이닉스
  '035420': { logo: '네', logo_bg: '#03C75A' }, // 네이버
  '105560': { logo: 'K', logo_bg: '#FFBC00', logo_ink: '#1A1A1A' }, // KB금융
  '373220': { logo: 'L', logo_bg: '#A50034' }, // LG에너지솔루션
  '207940': { logo: '삼', logo_bg: '#1428A0' }, // 삼성바이오로직스
  '005380': { logo: '현', logo_bg: '#002C5F' }, // 현대차
  '000270': { logo: '기', logo_bg: '#05141F' }, // 기아
  '068270': { logo: '셀', logo_bg: '#0A6CB6' }, // 셀트리온
  '035720': { logo: '카', logo_bg: '#FEE500', logo_ink: '#1A1A1A' }, // 카카오
  '055550': { logo: '신', logo_bg: '#0046FF' }, // 신한지주
  '012450': { logo: '한', logo_bg: '#F37321' }, // 한화에어로스페이스
};
