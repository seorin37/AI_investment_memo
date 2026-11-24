/**
 * 웹 보드의 DOM 동작 (규칙 2: document · window 는 .web.tsx 안에서만)
 * - 마우스 끌기로 순서 바꾸기 (원본 boardDrag.ts: 마우스는 6px 넘게 움직이면 · 터치는 0.35초 꾹 · Esc 취소 · 위아래 끝 64 에서 자동 스크롤)
 * - 우클릭 메뉴 (원본 board.tsx onContextMenu)
 * - Esc 키
 * RN-web 의 View ref 는 DOM 요소라서 여기서 HTMLElement 로 다룸. 카드 칸에는 dataSet={{ bkey }} (→ data-bkey) 를 붙임.
 */
import { useEffect, useRef, useState } from 'react';
import { moveCard } from '../boardCards';

const HOLD = 350;
const SLOP = 6;
const EDGE = 64;

/** 칸 모양: 격자 3칸(276×200 · 16/24) · 목록 1칸(줄 76) */
export interface DragCell {
  cols: number;
  w: number;
  h: number;
  gx: number;
  gy: number;
}

type St = { key: string; pid: number; touch: boolean; sx: number; sy: number; px: number; py: number; gx: number; gy: number; active: boolean; timer: number; raf: number; scroller: HTMLElement | null; to: number };

function scrollParent(el: HTMLElement | null): HTMLElement | null {
  for (let n = el?.parentElement ?? null; n; n = n.parentElement) {
    const o = getComputedStyle(n).overflowY;
    if ((o === 'auto' || o === 'scroll') && n.scrollHeight > n.clientHeight + 1) return n;
  }
  return null;
}

/** 끌기 상태: 집은 카드 key · 놓일 자리 · 틀(860) 기준 위치 */
export interface DragView {
  key: string;
  to: number;
  left: number;
  top: number;
  h: number;
}

/**
 * @param box 격자 View 의 ref (웹에서는 DOM 요소)
 * @param order 지금 순서
 * @param enabled 끌 수 있는지 (전체 보기 · 고르기 아님 · 격자)
 * @param scale 고정 틀 배율 (화면 px → 틀 px)
 * @param onDrop 바뀐 순서
 * @param pinCount 앞에서부터 고정 카드 수 — 끌 수 없고 그 안으로도 못 놓음. 키보드는 Alt+↑↓ (사이드바 종목 순서와 같음)
 */
export function useBoardDragWeb(box: { current: unknown }, ready: boolean, order: string[], enabled: boolean, scale: number, onDrop: (o: string[]) => void, pinCount: number, cell: DragCell) {
  const [drag, setDrag] = useState<DragView | null>(null);
  const st = useRef<St | null>(null);
  const dropped = useRef(0);
  const live = useRef({ order, scale, onDrop, enabled, pinCount, cell });
  useEffect(() => {
    live.current = { order, scale, onDrop, enabled, pinCount, cell };
  });

  useEffect(() => {
    const el = box.current as HTMLElement | null;
    if (!el) return;
    const rect = () => el.getBoundingClientRect();
    const place = (s: St) => {
      const r = rect();
      const z = live.current.scale || 1;
      const left = (s.px - s.gx - r.left) / z;
      const top = (s.py - s.gy - r.top) / z;
      /* 놓일 자리: 집은 카드 가운데가 들어간 칸 (행 × 3 + 열) */
      const { cols, w, h, gx, gy } = live.current.cell;
      const cx = left + w / 2;
      const cy = top + h / 2;
      const col = Math.max(0, Math.min(cols - 1, Math.floor((cx + gx / 2) / (w + gx))));
      const row = Math.max(0, Math.floor((cy + gy / 2) / (h + gy)));
      const n = live.current.order.filter((k) => k !== s.key).length;
      const to = Math.max(live.current.pinCount, Math.min(n, row * cols + col));
      s.to = to;
      setDrag({ key: s.key, to, left, top, h });
    };
    const auto = () => {
      const s = st.current;
      if (!s?.active) return;
      const sc = s.scroller;
      const r = sc ? sc.getBoundingClientRect() : { top: 0, bottom: window.innerHeight };
      const v = s.py < r.top + EDGE ? -Math.ceil((r.top + EDGE - s.py) / 6) : s.py > r.bottom - EDGE ? Math.ceil((s.py - (r.bottom - EDGE)) / 6) : 0;
      if (v) {
        if (sc) sc.scrollTop += v;
        else window.scrollBy(0, v);
        place(s);
      }
      s.raf = requestAnimationFrame(auto);
    };
    const activate = () => {
      const s = st.current;
      if (!s || s.active) return;
      const slot = el.querySelector<HTMLElement>(`[data-bkey="${CSS.escape(s.key)}"]`);
      if (!slot) return;
      const r = slot.getBoundingClientRect();
      s.gx = s.sx - r.left;
      s.gy = s.sy - r.top;
      s.active = true;
      s.scroller = scrollParent(el);
      document.documentElement.style.cursor = 'grabbing';
      try {
        navigator.vibrate?.(12);
      } catch {
        /* 무시 */
      }
      place(s);
      s.raf = requestAnimationFrame(auto);
    };
    const end = (commit: boolean) => {
      const s = st.current;
      if (!s) return;
      clearTimeout(s.timer);
      cancelAnimationFrame(s.raf);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      window.removeEventListener('pointercancel', cancel);
      document.documentElement.style.cursor = '';
      st.current = null;
      if (!s.active) return;
      dropped.current = Date.now();
      const o = commit ? moveCard(live.current.order, live.current.pinCount, s.key, s.to) : null;
      setDrag(null);
      if (o) live.current.onDrop(o);
    };
    function move(e: PointerEvent) {
      const s = st.current;
      if (!s || e.pointerId !== s.pid) return;
      s.px = e.clientX;
      s.py = e.clientY;
      if (!s.active) {
        if (Math.hypot(s.px - s.sx, s.py - s.sy) > SLOP) {
          if (s.touch) end(false); /* 꾹 누르기 전에 움직이면 스크롤 */
          else activate();
        }
        return;
      }
      e.preventDefault();
      place(s);
    }
    function up(e: PointerEvent) {
      if (st.current && e.pointerId === st.current.pid) end(true);
    }
    function cancel(e: PointerEvent) {
      if (st.current && e.pointerId === st.current.pid) end(false);
    }
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && st.current?.active) {
        e.preventDefault();
        e.stopPropagation();
        end(false);
      }
    };
    const down = (e: PointerEvent) => {
      if (!live.current.enabled || st.current || (e.pointerType === 'mouse' && e.button !== 0)) return;
      const t = e.target as HTMLElement;
      if (t.closest('[data-nodrag]')) return;
      const slot = t.closest<HTMLElement>('[data-bkey]');
      if (!slot || !el.contains(slot)) return;
      if (live.current.order.indexOf(slot.dataset.bkey!) < live.current.pinCount) return; /* 고정 카드는 끌지 않음 */
      st.current = { key: slot.dataset.bkey!, pid: e.pointerId, touch: e.pointerType !== 'mouse', sx: e.clientX, sy: e.clientY, px: e.clientX, py: e.clientY, gx: 0, gy: 0, active: false, timer: 0, raf: 0, scroller: null, to: 0 };
      st.current.timer = window.setTimeout(activate, HOLD);
      window.addEventListener('pointermove', move, { passive: false });
      window.addEventListener('pointerup', up);
      window.addEventListener('pointercancel', cancel);
    };
    /* 키보드: 초점이 있는 카드를 Alt+↑↓ 로 한 자리씩 */
    const alt = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (!e.altKey || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') || !live.current.enabled || st.current) return;
      const key = t.closest<HTMLElement>('[data-bkey]')?.dataset.bkey;
      if (!key) return;
      e.preventDefault();
      const i = live.current.order.indexOf(key);
      const o = moveCard(live.current.order, live.current.pinCount, key, i + (e.key === 'ArrowUp' ? -1 : 1));
      if (!o) return;
      live.current.onDrop(o);
      /* 자리가 바뀌며 초점을 잃으면 다시 */
      requestAnimationFrame(() => requestAnimationFrame(() => t.isConnected && t.focus()));
    };
    /* 터치 중 끌기면 화면 스크롤 막기 (손가락을 대기 전부터 막을 수 있는 리스너) */
    const touch = (e: TouchEvent) => {
      if (st.current?.active) e.preventDefault();
    };
    el.addEventListener('pointerdown', down);
    el.addEventListener('keydown', alt);
    window.addEventListener('keydown', key, true);
    document.addEventListener('touchmove', touch, { passive: false });
    return () => {
      el.removeEventListener('pointerdown', down);
      el.removeEventListener('keydown', alt);
      window.removeEventListener('keydown', key, true);
      document.removeEventListener('touchmove', touch);
      if (st.current) end(false);
    };
  }, [box, ready]);

  /** 방금 끌기를 끝냈으면 그 클릭은 무시 (원본 suppress) */
  const justDropped = () => Date.now() - dropped.current < 150;
  return { drag, justDropped };
}

/** 우클릭: data-bkey 가 붙은 칸에서 (key, 화면 좌표) */
export function useContextMenuWeb(box: { current: unknown }, ready: boolean, onMenu: (key: string, at: { x: number; y: number }) => void) {
  const cb = useRef(onMenu);
  useEffect(() => {
    cb.current = onMenu;
  });
  useEffect(() => {
    const el = box.current as HTMLElement | null;
    if (!el) return;
    const f = (e: MouseEvent) => {
      const slot = (e.target as HTMLElement).closest<HTMLElement>('[data-bkey]');
      if (!slot || !el.contains(slot)) return;
      e.preventDefault();
      cb.current(slot.dataset.bkey!, { x: e.clientX, y: e.clientY });
    };
    el.addEventListener('contextmenu', f);
    return () => el.removeEventListener('contextmenu', f);
  }, [box, ready]);
}

/** Esc 키 */
export function useEscapeWeb(on: boolean, onEscape: () => void) {
  const cb = useRef(onEscape);
  useEffect(() => {
    cb.current = onEscape;
  });
  useEffect(() => {
    if (!on) return;
    const f = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cb.current();
    };
    window.addEventListener('keydown', f);
    return () => window.removeEventListener('keydown', f);
  }, [on]);
}
