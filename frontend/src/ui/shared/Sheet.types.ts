import type { ReactNode } from 'react';

/** 앱 바텀 시트 / 웹 가운데 창 — 같은 props (규칙 2) */
export interface SheetProps {
  open: boolean;
  onClose: () => void;
  /** 시트 제목 (앱: 손잡이 아래 17px 800 · 웹: 창 안에서 각 화면이 그림) */
  title?: string;
  children: ReactNode;
  /** 웹 창 폭 */
  width?: number;
  /** 접근성 이름 */
  label: string;
}
