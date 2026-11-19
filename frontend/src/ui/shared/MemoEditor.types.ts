import type { Ref } from 'react';

/** 한 칸 메모 편집기 — 첫 줄은 제목 크기 (앱 TextInput · 웹 원본처럼 줄 묶음 편집기) */
export interface MemoEditorProps {
  /** 한 칸 글 (제목\n본문) — 처음 값 */
  value: string;
  onChangeText: (v: string) => void;
  /** false 면 보기만 (앱: 종이를 누르면 편집 시작) */
  editable: boolean;
  autoFocus?: boolean;
  /** 앱: 원본 memo.html .ed · 웹: 원본 board.tsx .memo-ed */
  variant: 'app' | 'web';
  /** 처음부터 다시 그릴 때 바꾸는 값 (웹 편집기는 내용을 직접 들고 있음) */
  resetKey?: string | number;
  onFocus?: () => void;
  /** 앱: 포커스 · 커서 끝으로 (편집 시작) */
  focusRef?: Ref<{ focus: () => void; blur: () => void }>;
  accessibilityLabel?: string;
}
