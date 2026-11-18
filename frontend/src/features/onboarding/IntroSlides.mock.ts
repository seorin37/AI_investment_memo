/** 서비스 소개 3장 — 체험판/웹과 같은 문구 */
import type { IntroSlidesProps } from '@/features/onboarding/IntroSlides.types';

export const mockIntroSlidesProps: IntroSlidesProps = {
  slides: [
    { key: 'flood', title: '정보는 넘치는데,\n내 종목엔 뭐가 중요할까요?', body: '공시·뉴스·리포트를 다 읽을 시간은 없죠.' },
    { key: 'memo', title: '떠오른 생각 한 줄이면\n충분해요', body: '“HBM 수요 계속 갈까?”처럼 적어 두면, AI가 관련 공시·뉴스를 매일 대신 확인해 붙여 드려요.' },
    { key: 'listen', title: '바쁠 땐 듣고,\n주말엔 한 번에', body: '쌓인 소식은 라디오나 주간보고서로 받아 보세요.' },
  ],
  onDone: () => {},
};
