import type { OnboardingStock } from './Onboarding.types';

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
