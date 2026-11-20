import type { OnboardingStock, StockStatus } from './Onboarding.types';

/** 앱 첫 홈 (원본 app/start.html) — 고른 종목 + 보유/관심 + 메모 수 */
export interface FirstHomeStock extends OnboardingStock {
  status: StockStatus;
  memo_count: number;
  ai_count: number;
}

/** 첫 메모를 저장한 뒤 홈에 보이는 요약 (원본 state 'saved' · 'watch') */
export interface FirstMemoSummary {
  stock_code: string;
  stock_name: string;
  title: string;
  body: string;
  ai: boolean;
  /** AI 연결 칩 (원본 .chip: '가격 조건 · …' / '공시·뉴스 · …') */
  chips: string[];
}

export interface AppFirstHomeProps {
  user_name: string;
  stocks: FirstHomeStock[];
  /** null = 아직 첫 메모 전 (빈 상태) */
  memo: FirstMemoSummary | null;
  picker_open: boolean;
  /** [첫 메모 쓰기] → 종목 시트 */
  onOpenPicker: () => void;
  onClosePicker: () => void;
  /** 시트 [이 종목에 메모 쓰기] · 내 종목 [+ 메모] */
  onPickStock: (stock: FirstHomeStock) => void;
  /** 고른 종목이 없을 때 [첫 메모 쓰기] */
  onNoStocks: () => void;
  /** [홈으로 이어서 보기 →] */
  onContinue: () => void;
}

/** 앱 첫 메모 (원본 start.html #nm: 메모 보드 새 메모와 같은 양식 + 머리 종목 칩 · 예시로 채워 보기 · AI 안내 말풍선) */
export interface AppFirstMemoProps {
  stocks: FirstHomeStock[];
  /** 처음 고른 종목 (머리 칩으로 바꿀 수 있음) */
  stock_code: string;
  onCancel: () => void;
  /** 빈 메모로 [완료] */
  onEmpty: () => void;
  onSave: (r: { stock: FirstHomeStock; title: string; body: string; ai: boolean }) => void;
}

export interface FirstStockSheetProps {
  open: boolean;
  stocks: FirstHomeStock[];
  selected: string | null;
  /** '이 종목에 메모 쓰기' (첫 홈) · '이 종목으로 바꾸기' (새 메모 머리) */
  button: string;
  onClose: () => void;
  onConfirm: (stock: FirstHomeStock) => void;
}

export interface FirstHomeProps {
  stocks: OnboardingStock[];
  guide_open: boolean;
  picker_open: boolean;
  saved: boolean;
  onNextGuide: () => void;
  onCloseGuide: () => void;
  onSkip: () => void;
  onOpenPicker: () => void;
  onClosePicker: () => void;
  onPickStock: (stock: OnboardingStock) => void;
}
