/** 로그인 전 서비스 소개 3장 */
export interface IntroSlide {
  key: 'flood' | 'memo' | 'listen';
  title: string; // 줄바꿈은 \n
  body: string;
}

export interface IntroSlidesProps {
  slides: IntroSlide[];
  /** [건너뛰기] 또는 마지막 장 [시작하기] → 로그인 */
  onDone: () => void;
}
