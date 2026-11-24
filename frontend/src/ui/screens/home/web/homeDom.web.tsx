import React from 'react';

/**
 * 웹 홈 마우스 끌기 (원본 homex.tsx HomeGrid down · custom.tsx drag): window pointermove/up 은 이 .web.tsx 안에서만.
 */

/** 홈 편집 ⋮⋮ 손잡이: 끄는 동안 마우스 아래 위젯([data-hw]) 이름을 알려 줌 */
export function HomeGrip({ id, onStart, onOver, onEnd, children }: { id: string; onStart: () => void; onOver: (to: string) => void; onEnd: () => void; children: React.ReactNode }) {
  return React.createElement(
    'div',
    {
      'aria-label': '끌어서 순서 바꾸기',
      role: 'button',
      onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => {
        e.preventDefault();
        onStart();
        const mv = (ev: PointerEvent) => {
          const els = [...document.querySelectorAll<HTMLElement>('[data-hw]')];
          const hit = els.find((el) => {
            const r = el.getBoundingClientRect();
            return ev.clientX >= r.left && ev.clientX <= r.right && ev.clientY >= r.top && ev.clientY <= r.bottom;
          });
          const to = hit?.dataset.hw;
          if (to && to !== id) onOver(to);
        };
        const up = () => {
          window.removeEventListener('pointermove', mv);
          window.removeEventListener('pointerup', up);
          onEnd();
        };
        window.addEventListener('pointermove', mv);
        window.addEventListener('pointerup', up);
      },
      style: { width: 32, height: 32, borderRadius: 8, display: 'grid', placeItems: 'center', cursor: 'grab', touchAction: 'none' },
    },
    children,
  );
}

/** 맞춤 홈 위젯 상단 손잡이: 누른 곳에서 얼마나 움직였는지(px) 알려 줌 */
export function MoveHandle({ onDown, onMove, onUp, children }: { onDown: () => void; onMove: (dx: number, dy: number) => void; onUp: () => void; children: React.ReactNode }) {
  return React.createElement(
    'div',
    {
      onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        onDown();
        const sx = e.clientX;
        const sy = e.clientY;
        const mv = (ev: PointerEvent) => onMove(ev.clientX - sx, ev.clientY - sy);
        const up = () => {
          window.removeEventListener('pointermove', mv);
          window.removeEventListener('pointerup', up);
          onUp();
        };
        window.addEventListener('pointermove', mv);
        window.addEventListener('pointerup', up);
      },
      style: { height: 32, width: '100%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 12px', boxSizing: 'border-box', cursor: 'grab', touchAction: 'none' },
    },
    children,
  );
}

/** 맞춤 홈 위젯 자리 그림의 24px 격자 바탕 (원본 linear-gradient #E6EAF0 1px) */
export function GridBg() {
  return React.createElement('div', {
    'aria-hidden': true,
    style: { position: 'absolute', inset: 0, pointerEvents: 'none', backgroundImage: 'linear-gradient(#e6eaf0 1px, transparent 1px), linear-gradient(90deg, #e6eaf0 1px, transparent 1px)', backgroundSize: '24px 24px' },
  });
}
