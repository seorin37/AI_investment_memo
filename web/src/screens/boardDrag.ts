/* 보드 위치 바꾸기 (11.18) — 메모·체크리스트를 위젯처럼 끌어서 옮겨요.
   - 마우스: 누른 채 6px 이상 움직이면 바로 집어요. 0.35초 꾹 눌러도 집어요.
   - 터치: 0.35초 꾹 누르면 집어요 (그 전에 움직이면 화면 스크롤로 봐요).
   - 보드는 3칸 격자이고 카드 순서는 왼쪽→오른쪽, 위→아래예요 (11.18 오후: 앱 홈 화면처럼).
   - 집은 카드는 손가락·커서를 따라오고, 놓일 자리에는 점선 칸이 생겨요. 다른 카드는 옆으로 한 칸씩 밀려요(줄 끝이면 다음 줄 처음으로). 움직임은 useFlip.
   - 집은 카드는 끄는 동안 DOM에서 자리를 옮기지 않아요 (터치는 처음 누른 요소로 이벤트가 가서, 옮기면 끌기가 끊김).
   - Esc를 누르면 취소돼요. 화면 위·아래 끝으로 가면 자동으로 스크롤돼요. */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

export type Order = string[];
export const HOLE = "__hole";
const COLS = 3;
type St = {
  key: string; pid: number; touch: boolean; sx: number; sy: number; px: number; py: number;
  gx: number; gy: number; h: number; w: number; active: boolean; timer: number; scroller: HTMLElement | null; raf: number;
};

const HOLD = 350, SLOP = 6, EDGE = 64;

function scrollParent(el: HTMLElement | null): HTMLElement | null {
  for (let n = el?.parentElement ?? null; n; n = n.parentElement) {
    const o = getComputedStyle(n).overflowY;
    if ((o === "auto" || o === "scroll") && n.scrollHeight > n.clientHeight + 1) return n;
  }
  return null;
}

export function useBoardDrag(box: React.RefObject<HTMLDivElement | null>, cols: Order, enabled: boolean, onDrop: (order: Order) => void) {
  const [drag, setDrag] = useState<{ key: string; to: number } | null>(null), [holeH, setHoleH] = useState(0);
  const st = useRef<St | null>(null);
  const dragRef = useRef(drag); dragRef.current = drag;
  const colsRef = useRef(cols); colsRef.current = cols;
  const dropRef = useRef(onDrop); dropRef.current = onDrop;
  const suppress = useRef(false);
  /* 창에 붙이는 이벤트는 한 번 만든 함수로 (렌더마다 새 함수면 떼어낼 수 없음) */
  const H = useRef<{ move: (e: PointerEvent) => void; up: (e: PointerEvent) => void; cancel: (e: PointerEvent) => void; key: (e: KeyboardEvent) => void; touch: (e: TouchEvent) => void } | null>(null);
  const L = useRef<NonNullable<typeof H.current> | null>(null);
  if (!L.current) L.current = { move: (e) => H.current?.move(e), up: (e) => H.current?.up(e), cancel: (e) => H.current?.cancel(e), key: (e) => H.current?.key(e), touch: (e) => H.current?.touch(e) };

  /* 놓으면 될 순서 */
  const next = (d: { key: string; to: number } | null, list: Order) => {
    if (!d) return list;
    const o = list.filter((k) => k !== d.key);
    o.splice(Math.min(d.to, o.length), 0, d.key);
    return o;
  };
  /* 끄는 동안 그리는 순서: 집은 카드는 원래 자리에 그대로(떠 있음, 격자 칸은 차지하지 않음), 놓일 자리에 HOLE */
  const view = useMemo(() => {
    if (!drag) return cols;
    const others = cols.filter((k) => k !== drag.key), before = others[drag.to];
    const out = [...cols]; out.splice(before === undefined ? out.length : out.indexOf(before), 0, HOLE);
    return out;
  }, [cols, drag]);
  const slotOf = (key: string) => box.current?.querySelector<HTMLElement>(`[data-bkey="${CSS.escape(key)}"]`) ?? null;

  /* 집은 카드를 포인터 자리로: 보드 틀 기준 절대 위치 (고정 틀 축소 비율 반영) */
  const paint = useCallback(() => {
    const s = st.current, b = box.current; if (!s?.active || !b) return;
    const slot = slotOf(s.key); if (!slot) return;
    const r = b.getBoundingClientRect(), z = r.width / (b.offsetWidth || 1);
    Object.assign(slot.style, { position: "absolute", zIndex: "50", width: `${s.w}px`, left: `${(s.px - s.gx - r.left) / z - b.clientLeft}px`, top: `${(s.py - s.gy - r.top) / z - b.clientTop}px` });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* 놓일 자리: 집은 카드 가운데가 들어간 격자 칸 (행 × 3 + 열) */
  const target = (): number | null => {
    const s = st.current, b = box.current; if (!s || !b) return null;
    const r = b.getBoundingClientRect(), z = r.width / (b.offsetWidth || 1), cs = getComputedStyle(b);
    const gx = parseFloat(cs.columnGap) || 0, gy = parseFloat(cs.rowGap) || 0;
    const cw = (b.clientWidth - gx * (COLS - 1)) / COLS, rh = s.h / z;
    const cx = (s.px - s.gx - r.left) / z + s.w / 2, cy = (s.py - s.gy - r.top) / z + rh / 2;
    const col = Math.max(0, Math.min(COLS - 1, Math.floor((cx + gx / 2) / (cw + gx))));
    const row = Math.max(0, Math.floor((cy + gy / 2) / (rh + gy)));
    const n = colsRef.current.filter((k) => k !== s.key).length;
    return Math.max(0, Math.min(n, row * COLS + col));
  };
  const retarget = () => {
    const t = target(), d = dragRef.current;
    if (t !== null && d && t !== d.to) setDrag({ key: d.key, to: t });
    else paint();
  };

  const stopAuto = () => { const s = st.current; if (s?.raf) cancelAnimationFrame(s.raf); if (s) s.raf = 0; };
  const auto = () => {
    const s = st.current; if (!s?.active) return;
    const sc = s.scroller, r = sc ? sc.getBoundingClientRect() : { top: 0, bottom: innerHeight };
    const v = s.py < r.top + EDGE ? -Math.ceil((r.top + EDGE - s.py) / 6) : s.py > r.bottom - EDGE ? Math.ceil((s.py - (r.bottom - EDGE)) / 6) : 0;
    if (v) { if (sc) sc.scrollTop += v; else window.scrollBy(0, v); retarget(); }
    s.raf = requestAnimationFrame(auto);
  };

  const activate = () => {
    const s = st.current; if (!s || s.active) return;
    const slot = slotOf(s.key); if (!slot) return;
    const r = slot.getBoundingClientRect();
    s.gx = s.sx - r.left; s.gy = s.sy - r.top; s.h = r.height; s.w = slot.offsetWidth; s.active = true;
    setHoleH(slot.offsetHeight);
    s.scroller = scrollParent(box.current);
    suppress.current = true;
    document.documentElement.classList.add("b-dragging");
    try { navigator.vibrate?.(12); } catch { /* 무시 */ }
    setDrag({ key: s.key, to: Math.max(0, colsRef.current.indexOf(s.key)) });
    s.raf = requestAnimationFrame(auto);
  };

  const end = (commit: boolean) => {
    const s = st.current; if (!s) return;
    clearTimeout(s.timer); stopAuto();
    const l = L.current!;
    window.removeEventListener("pointermove", l.move); window.removeEventListener("pointerup", l.up); window.removeEventListener("pointercancel", l.cancel);
    window.removeEventListener("keydown", l.key, true); window.removeEventListener("touchmove", l.touch);
    document.documentElement.classList.remove("b-dragging");
    st.current = null;
    if (!s.active) return;
    const slot = slotOf(s.key);
    if (slot) Object.assign(slot.style, { position: "", zIndex: "", width: "", left: "", top: "" });
    if (commit) {
      const n = next(dragRef.current, colsRef.current);
      if (JSON.stringify(n) !== JSON.stringify(colsRef.current)) dropRef.current([...n]);
    }
    setDrag(null);
    const k = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--k")) || 1;
    requestAnimationFrame(() => {
      /* 놓은 자리로 내려앉기 (취소면 원래 자리로) */
      const slot2 = slotOf(s.key), lift2 = slot2?.querySelector<HTMLElement>("[data-blift]");
      if (!slot2 || !lift2) return;
      const r = slot2.getBoundingClientRect(), z = r.width / (slot2.offsetWidth || 1);
      const dx = (s.px - s.gx - r.left) / z, dy = (s.py - s.gy - r.top) / z;
      lift2.animate([{ transform: `translate(${dx}px, ${dy}px) scale(1.03) rotate(-1deg)` }, { transform: "none" }], { duration: 260 * k, easing: "cubic-bezier(.2,.8,.2,1)" });
    });
    window.setTimeout(() => { suppress.current = false; }, 0);
  };

  function onMove(e: PointerEvent) {
    const s = st.current; if (!s || e.pointerId !== s.pid) return;
    s.px = e.clientX; s.py = e.clientY;
    if (!s.active) {
      if (Math.hypot(s.px - s.sx, s.py - s.sy) > SLOP) {
        if (s.touch) end(false); /* 꾹 누르기 전에 움직이면 스크롤 */
        else activate();
      }
      return;
    }
    e.preventDefault();
    retarget();
  }
  function onUp(e: PointerEvent) { if (st.current && e.pointerId === st.current.pid) end(true); }
  function onCancel(e: PointerEvent) { if (st.current && e.pointerId === st.current.pid) end(false); }
  function onKey(e: KeyboardEvent) { if (e.key === "Escape" && st.current?.active) { e.preventDefault(); e.stopPropagation(); setDrag(null); end(false); } }
  function onTouch(e: TouchEvent) { if (st.current?.active) e.preventDefault(); }
  H.current = { move: onMove, up: onUp, cancel: onCancel, key: onKey, touch: onTouch };

  useLayoutEffect(() => { if (drag) paint(); }, [drag, paint]);
  /* 터치: 스크롤을 막으려면 손가락을 대기 전부터 '막을 수 있는' 리스너가 붙어 있어야 해요 (브라우저가 터치 시작 때 정함) */
  useEffect(() => {
    const f = (e: TouchEvent) => { if (st.current?.active) e.preventDefault(); };
    document.addEventListener("touchmove", f, { passive: false });
    return () => document.removeEventListener("touchmove", f);
  }, []);
  useEffect(() => () => { if (st.current) end(false); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const slot = (key: string) => ({
    "data-bkey": key,
    onPointerDown: (e: React.PointerEvent) => {
      if (!enabled || st.current || (e.pointerType === "mouse" && e.button !== 0)) return;
      if ((e.target as HTMLElement).closest("[data-nodrag]")) return;
      const touch = e.pointerType !== "mouse";
      st.current = { key, pid: e.pointerId, touch, sx: e.clientX, sy: e.clientY, px: e.clientX, py: e.clientY, gx: 0, gy: 0, h: 0, w: 0, active: false, timer: 0, scroller: null, raf: 0 };
      st.current.timer = window.setTimeout(activate, HOLD);
      const l = L.current!;
      window.addEventListener("pointermove", l.move, { passive: false }); window.addEventListener("pointerup", l.up); window.addEventListener("pointercancel", l.cancel);
      window.addEventListener("keydown", l.key, true); window.addEventListener("touchmove", l.touch, { passive: false });
    },
    onClickCapture: (e: React.MouseEvent) => { if (suppress.current) { e.stopPropagation(); e.preventDefault(); suppress.current = false; } },
    onContextMenuCapture: (e: React.MouseEvent) => { if (st.current?.touch || st.current?.active) { e.preventDefault(); e.stopPropagation(); } },
  });

  return { view, holeH, dragKey: drag?.key ?? null, slot };
}

/* 보드 순서: 저장된 순서 + 아직 순서에 없는 것(새 메모·새 체크리스트)은 맨 앞에.
   예전(11.18 오전) 3칸 세로 배치로 저장된 것은 왼쪽→오른쪽, 위→아래 순서로 바꿔 읽어요 */
export function flatRows(cols: string[][]): Order {
  const out: string[] = [], n = Math.max(0, ...cols.map((c) => c.length));
  for (let i = 0; i < n; i++) for (const c of cols) if (c[i] !== undefined) out.push(c[i]);
  return out;
}
export function arrange(saved: Order | string[][] | undefined, keys: string[], legacy: Order): Order {
  const has = new Set(keys);
  const list = !saved ? [] : Array.isArray(saved[0]) ? flatRows(saved as string[][]) : (saved as Order);
  const placed = list.filter((k) => has.has(k)), inLay = new Set(placed);
  return [...legacy.filter((k) => !inLay.has(k)), ...placed];
}
