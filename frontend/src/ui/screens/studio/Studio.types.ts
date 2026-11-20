import type { CreditPack } from '../my/My.mock';

export type StudioKind = 'audio' | 'report' | 'lab' | 'quiz';

/** 스튜디오 기능 카드 (원본 FEAT / FEATURES) */
export interface StudioFeatureItem {
  key: StudioKind;
  title: string;
  desc: string;
}

/** 만든 항목 (30일 보관) */
export interface MadeItem {
  id: string;
  kind: Exclude<StudioKind, 'quiz'>;
  title: string;
  /** 앱 줄 아래 글 (원본 앱 MADE[2]) */
  sub: string;
  /** 웹 줄 아래 글 (원본 웹 m.meta) */
  meta: string;
  /** 'N일 뒤 삭제' */
  left: string;
  /** 오디오 길이 'm:ss' */
  dur?: string;
  /** 앱 라디오 카드 아래 왼쪽 글 */
  foot?: string;
  /** 주간보고서: 넣은 종목 · 국내 증시 흐름 포함 */
  codes?: string[];
  market?: boolean;
  /** 투자 실험실: 종목 · 조건 4칸 (상승/유지/하락) */
  lab?: { code: string; dirs: ('상승' | '유지' | '하락')[] };
}

export interface StudioHomeProps {
  features: StudioFeatureItem[];
  made: MadeItem[];
  usage_pct: number;
  /** '12월 1일' */
  usage_refill: string;
  stock_count: number;
  ai_memo_count: number;
  onFeature: (k: StudioKind) => void;
  onOpenMade: (m: MadeItem) => void;
  onBuyCredit: () => void;
  onChangePlan: () => void;
}

export interface ChargeProps {
  packs: CreditPack[];
  default_credits: number;
  onBack: () => void;
  onPay: (credits: number) => void;
}
