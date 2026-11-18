import type { NativeScrollEvent, NativeSyntheticEvent } from 'react-native';
export type StudioFeatureKey = 'audio' | 'report' | 'lab' | 'quiz';

export interface StudioFeature {
  key: StudioFeatureKey;
  title: string; // 'AI 오디오'
  desc: string;
}

/** 만든 항목 (30일 보관) */
export interface StudioMadeItem {
  id: string;
  kind: Exclude<StudioFeatureKey, 'quiz'>;
  title: string;
  sub: string;
  expire_label: string; // '23일 뒤 삭제'
}

/** 맨 위 최신 오디오 카드 */
export interface StudioFeaturedAudio {
  id: string;
  title: string; // '11.06 내 종목 라디오'
  sub: string;
  duration: string; // '6:42'
  meta: string; // '종목 3개 · 전날 기준'
  expire_label: string;
  /** 0~1 재생 위치 (파형 앞부분 색) */
  progress: number;
}

export interface StudioHomeProps {
  /** 이번 달 AI 사용량 % (화면에는 %만, 크레딧 숫자는 결제 화면에서만) */
  usage_percent: number;
  /** 다 썼으면 노란 칩 */
  usage_spent?: boolean;
  features: StudioFeature[];
  featured_audio?: StudioFeaturedAudio;
  made: StudioMadeItem[];
  onOpenUsage: () => void;
  onOpenFeature: (key: StudioFeatureKey) => void;
  /** 누르면 재생 ↔ 멈춤 (호스트가 실제 소리를 틀고 멈춤) */
  onPlayAudio: (id: string) => void;
  /** 지금 재생 중인 오디오 id (재생 ↔ 멈춤 모양 · 소리 막대 움직임) */
  playing_id?: string | null;
  onOpenMade: (id: string) => void;
  /** 스크롤 위치를 호스트로 (Lucian #332 큰 제목 접기 · TopBar 아래 선): useLargeTitle().onScroll 을 넘김 */
  onScroll?: (e: NativeSyntheticEvent<NativeScrollEvent>) => void;
}
