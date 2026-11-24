export type StockStatus = 'holding' | 'watching';
export type HomeMode = 'template' | 'custom';

export interface OnboardingStock {
  stock_code: string;
  name: string;
  market: 'KOSPI' | 'KOSDAQ';
  category: string;
  logo: string;
  logo_bg: string;
  logo_ink?: string;
}

export type OnboardingSelection = Record<string, StockStatus>;
export type OnboardingStep = 'pick' | 'setup' | 'ready';

export interface OnboardingFlowProps {
  stocks: OnboardingStock[];
  query: string;
  selected: OnboardingSelection;
  step: OnboardingStep;
  holding_open: boolean;
  onQueryChange: (value: string) => void;
  onToggle: (stock_code: string) => void;
  onStatusChange: (stock_code: string, status: StockStatus) => void;
  onRemove: (stock_code: string) => void;
  onOpenHolding: () => void;
  onCloseHolding: () => void;
  onBack: () => void;
  onSkip: () => void;
  onContinue: () => void;
  onChooseHome: (mode: HomeMode) => void;
  onFinish: () => void;
  /** 고른 종목 담는 중 — 계속 버튼은 '고른 종목 없음'과 같은 비활성 모양 (두 번 누름 방지) */
  saving?: boolean;
  /** 담기 실패 문구 — 있을 때만 버튼 위 한 줄 */
  error?: string | null;
}
