import { useEffect, useRef, type RefObject } from 'react';

/**
 * 웹 내 종목 우클릭 (원본 mine.tsx onContextMenu): 상자 안에서 [data-mine] 줄을 우클릭하면 그 종목 코드와 마우스 위치를 알려 줌.
 * RN-web 의 View ref 는 DOM 요소라서 여기(.web.tsx)에서만 다룸.
 */
export function useContextMenuDom(onMenu: (code: string, at: { x: number; y: number }) => void) {
  const box = useRef<HTMLElement | null>(null);
  const cb = useRef(onMenu);
  useEffect(() => {
    cb.current = onMenu;
  });
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const f = (e: MouseEvent) => {
      const row = (e.target as HTMLElement).closest<HTMLElement>('[data-mine]');
      if (!row) return;
      e.preventDefault();
      cb.current(row.dataset.mine ?? '', { x: e.clientX, y: e.clientY });
    };
    el.addEventListener('contextmenu', f);
    return () => el.removeEventListener('contextmenu', f);
  }, []);
  return box as unknown as RefObject<never>;
}
