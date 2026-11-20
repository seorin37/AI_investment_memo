import { useEffect, useRef } from 'react';

/*
 * 웹 다크 모드 (원본 web/src/theme.tsx · theme.css): html 전체를 반전(색상은 유지)하고,
 * 바뀔 때 누른 자리에서 원으로 번지며 바뀜 (Lucian #219 · .7s cubic-bezier(.65,0,.35,1)). 동작 줄이기면 바로 바뀜.
 * 원래 색 유지(.dk-keep)는 Dark.tsx Keep 이 filter 스타일로.
 */
const CSS = `
html.dark { filter: invert(1) hue-rotate(180deg) contrast(.88); background: #fff; }
::view-transition-old(root), ::view-transition-new(root) { animation: none; mix-blend-mode: normal; }
::view-transition-new(root) { animation: u219-reveal .7s cubic-bezier(.65,0,.35,1) both; }
@keyframes u219-reveal { from { clip-path: circle(0px at var(--vt-x, 50%) var(--vt-y, 50%)); } to { clip-path: circle(var(--vt-r, 150vmax) at var(--vt-x, 50%) var(--vt-y, 50%)); } }
@media (prefers-reduced-motion: reduce) { ::view-transition-new(root) { animation: none; } }
`;

let origin: { x: number; y: number } | null = null;
export function setDarkOrigin(x: number, y: number) {
  origin = { x, y };
}

export function useDarkDom(dark: boolean) {
  const first = useRef(true);
  useEffect(() => {
    if (document.getElementById('memos-dark-css')) return;
    const s = document.createElement('style');
    s.id = 'memos-dark-css';
    s.textContent = CSS;
    document.head.appendChild(s);
  }, []);
  useEffect(() => {
    const root = document.documentElement;
    const apply = () => {
      root.classList.toggle('dark', dark);
    };
    if (first.current || root.classList.contains('dark') === dark) {
      first.current = false;
      apply();
      return;
    }
    const doc = document as Document & { startViewTransition?: (cb: () => void) => unknown };
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!doc.startViewTransition || reduce) {
      apply();
      return;
    }
    const x = origin?.x ?? innerWidth / 2;
    const y = origin?.y ?? innerHeight / 2;
    root.style.setProperty('--vt-x', `${x}px`);
    root.style.setProperty('--vt-y', `${y}px`);
    root.style.setProperty('--vt-r', `${Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y))}px`);
    doc.startViewTransition(apply);
  }, [dark]);
}
