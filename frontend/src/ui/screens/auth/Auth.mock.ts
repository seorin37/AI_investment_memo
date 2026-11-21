import { LEGAL } from './AuthLegal';
import type { IntroPage, LegalDocument, LegalKey, TermItem, TermKey } from './Auth.types';

export const mockIntroPages: IntroPage[] = [
  {
    key: 'flood',
    title: '정보는 넘치는데,\n내 종목엔 뭐가 중요할까요?',
    description: '공시·뉴스·리포트를 다 읽을 시간은 없죠.',
  },
  {
    key: 'attach',
    title: '떠오른 생각 한 줄이면\n충분해요',
    description: '“HBM 수요 계속 갈까?”처럼 적어 두면, AI가 관련 공시·뉴스를 매일 대신 확인해 붙여 드려요.',
  },
  {
    key: 'studio',
    title: '바쁠 땐 듣고,\n주말엔 한 번에',
    description: '쌓인 소식은 라디오나 주간보고서로 받아 보세요.',
  },
];

export const mockTerms: TermItem[] = [
  { key: 'age', label: '[필수] 만 14세 이상이에요', required: true },
  { key: 'service', label: '[필수] 서비스 이용약관에 동의해요', required: true, document: 'terms' },
  { key: 'invest', label: '[필수] 투자 정보 이용 안내를 확인했어요', required: true, document: 'invest' },
];

export const emptyTermChecks: Record<TermKey, boolean> = {
  age: false,
  service: false,
  invest: false,
};

export const checkedTerms: Record<TermKey, boolean> = {
  age: true,
  service: true,
  invest: true,
};

export function legalDocument(key: LegalKey): LegalDocument {
  const source = LEGAL[key];
  return { key, title: source.t, html: source.h };
}
