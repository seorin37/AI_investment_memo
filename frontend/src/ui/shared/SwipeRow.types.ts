import type { ReactNode } from 'react';

/** 목록 줄 밀기 (앱만 동작 · 웹은 내용만) — 같은 props */
export interface SwipeRowProps {
  /** 밀 수 있는지 (원본: 목록 보기 · 고르기 아님 · 메모만) */
  enabled: boolean;
  /** 왼쪽으로 밀어 동작 버튼이 열려 있는지 (한 번에 한 줄만 — 부모가 관리) */
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 오른쪽으로 70 넘게 밀고 놓으면 */
  onPin: () => void;
  pinLabel: string;
  onAi: () => void;
  aiLabel: string;
  onDelete: () => void;
  children: ReactNode;
}
