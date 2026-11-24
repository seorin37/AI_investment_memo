import { useEffect } from 'react';

/** 알림함: 열려 있을 때만 Esc 로 닫기 (원본 x.tsx InboxPanel keydown) */
export function useEscWhile(open: boolean, onEscape: () => void) {
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onEscape(); };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [open, onEscape]);
}
