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
  /** 없으면 왼쪽은 휴지통 하나 (투자 기록 · 원본 journal.html .ar 88) */
  onAi?: () => void;
  aiLabel?: string;
  onDelete: () => void;
  children: ReactNode;
  /** memo: 메모 보드 (기본) · journal: 투자 기록 (원본 journal.html: 오른쪽 60 넘겨 놓으면 고정 · 70 넘으면 ×.35 · 주황 #F2A33A · 핀 20 · 12px · 왼쪽 휴지통 88 하나 · -44 넘으면 열림) */
  kind?: 'memo' | 'journal';
}
