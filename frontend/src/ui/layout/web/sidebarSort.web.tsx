import React, { useState } from 'react';
import { useShellSize } from './shellSize';

/**
 * 사이드바 종목 순서 바꾸기 (원본 shell.tsx SortList · Lucian #317 날아가는 정렬 목록)
 * 줄은 절대 위치(translateY) + transform .6s cubic-bezier(.3,1.1,.4,1). 올라가는 줄은 앞으로(그림자), 내려가는 줄은 뒤로(.9). 잡은 줄은 손을 따라옴.
 * 끌기는 4px 넘게 움직였을 때만 (그냥 누르면 그 종목으로 이동). 우클릭 = 종목 메뉴. 키보드: Alt + ↑/↓.
 * window · DOM 은 이 .web.tsx 안에서만.
 */
export function SortList({ codes, renderRow, onCommit, onMenu }: { codes: string[]; renderRow: (code: string, lifted: boolean) => React.ReactNode; onCommit: (codes: string[]) => void; onMenu: (code: string, at: { x: number; y: number }) => void }) {
  const z = useShellSize();
  const ROW = z.sortStep;
  const [drag, setDrag] = useState<{ code: string; from: number; dy: number } | null>(null);
  const [moved, setMoved] = useState<Record<string, 'up' | 'dn'>>({});
  const target = drag ? Math.max(0, Math.min(codes.length - 1, Math.round((drag.from * ROW + drag.dy) / ROW))) : -1;
  const order = drag
    ? (() => {
        const o = codes.filter((c) => c !== drag.code);
        o.splice(target, 0, drag.code);
        return o;
      })()
    : codes;
  const commit = (code: string, to: number) => {
    const from = codes.indexOf(code);
    if (from === to || to < 0 || to >= codes.length) return;
    const next = codes.filter((c) => c !== code);
    next.splice(to, 0, code);
    const mv: Record<string, 'up' | 'dn'> = {};
    next.forEach((c, i) => {
      const was = codes.indexOf(c);
      if (was > i) mv[c] = 'up';
      else if (was < i) mv[c] = 'dn';
    });
    setMoved(mv);
    window.setTimeout(() => setMoved({}), 1300);
    onCommit(next);
  };
  const down = (code: string, i: number) => (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    const y0 = e.clientY;
    let started = false;
    const mv = (ev: PointerEvent) => {
      const dy = ev.clientY - y0;
      if (!started && Math.abs(dy) < 4) return;
      started = true;
      setDrag({ code, from: i, dy });
    };
    const up = (ev: PointerEvent) => {
      window.removeEventListener('pointermove', mv);
      window.removeEventListener('pointerup', up);
      if (!started) return;
      const dy = ev.clientY - y0;
      const to = Math.max(0, Math.min(codes.length - 1, Math.round((i * ROW + dy) / ROW)));
      setDrag(null);
      commit(code, to);
      /* 끌고 놓은 뒤의 클릭은 막음 (종목으로 이동하지 않게) */
      const stop = (ce: MouseEvent) => {
        ce.stopPropagation();
        ce.preventDefault();
        window.removeEventListener('click', stop, true);
      };
      window.addEventListener('click', stop, true);
      window.setTimeout(() => window.removeEventListener('click', stop, true), 50);
    };
    window.addEventListener('pointermove', mv);
    window.addEventListener('pointerup', up);
  };
  return React.createElement(
    'div',
    { 'data-sort-list': true, style: { position: 'relative', width: z.stockRow, height: codes.length * ROW - 12 } },
    codes.map((code, i) => {
      const pos = order.indexOf(code);
      const me = drag?.code === code;
      const y = me && drag ? drag.from * ROW + drag.dy : pos * ROW;
      const stt = me ? 'lift' : (moved[code] ?? '');
      return React.createElement(
        'div',
        {
          key: code,
          'data-sort-row': code,
          onPointerDown: down(code, i),
          onContextMenu: (e: React.MouseEvent) => {
            e.preventDefault();
            onMenu(code, { x: e.clientX, y: e.clientY });
          },
          onKeyDown: (e: React.KeyboardEvent) => {
            if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
              e.preventDefault();
              commit(code, i + (e.key === 'ArrowUp' ? -1 : 1));
            }
          },
          title: '끌어서 순서 바꾸기 · Alt + ↑↓',
          style: {
            position: 'absolute',
            left: 0,
            top: 0,
            width: z.stockRow,
            borderRadius: 8,
            touchAction: 'none',
            userSelect: 'none',
            transform: `translateY(${y}px)${me ? ' scale(1.03)' : ''}`,
            transition: me ? 'box-shadow .3s' : 'transform .6s cubic-bezier(.3,1.1,.4,1), box-shadow .3s, opacity .3s',
            background: me ? '#fff' : undefined,
            cursor: me ? 'grabbing' : undefined,
            zIndex: me ? 20 : stt === 'up' ? 10 : 0,
            opacity: stt === 'dn' ? 0.9 : 1,
            boxShadow: me ? '0 10px 22px -12px rgba(17,17,17,.45)' : stt === 'up' ? '0 10px 22px -12px rgba(17,17,17,.35)' : undefined,
          },
        },
        renderRow(code, me),
      );
    }),
  );
}
