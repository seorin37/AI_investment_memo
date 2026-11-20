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
}
