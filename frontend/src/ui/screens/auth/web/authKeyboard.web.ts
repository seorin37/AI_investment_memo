import { useEffect } from 'react';

export function useIntroKeyboard(page: number, total: number, onPageChange: (page: number) => void) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'ArrowRight') onPageChange(Math.min(total - 1, page + 1));
      if (event.key === 'ArrowLeft') onPageChange(Math.max(0, page - 1));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onPageChange, page, total]);
}

export function useEscape(onEscape: () => void) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onEscape();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onEscape]);
}
