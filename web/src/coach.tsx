/* 첫 진입 코치마크 (11.14 멘토링 반영) — 실제 화면을 따라가며 진짜 버튼을 하나씩 밝힘
   ① 메모 쓰기(+ 버튼) → ② AI 연결(메모 창 토글) → ③ 쌓인 소식(AI 업데이트) → ④ 스튜디오
   Lucian UX/UI Prompt #197 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#197 — 화면 안내 스포트라이트
   (구멍 경로 · 넘쳤다 멈추는 이동 520ms · 맥박 고리 · 꼬리 달린 말풍선 · 점 표시 · 화살표 키/Esc 를 그대로 옮김. 금색 → 검정/흰색, 크기는 화면 전체용으로 키움) */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cx, useSnack } from "./kit";
import { useApp } from "./store";
import type { Memo, Stock } from "./data";

type Side = "rt" | "lt" | "dn" | "up";
type Step = { sel: string; pad: number; round?: boolean; prefer: Side[]; t: string; d: string };
export const COACH_STEPS: Step[] = [
  { sel: '[data-coach="fab"]', pad: 8, round: true, prefer: ["lt", "up"], t: "생각을 한 줄 적어 보세요", d: "형식은 없어요. 궁금한 점, 산 이유, 걱정 무엇이든 괜찮아요." },
  { sel: '[data-coach="ai"]', pad: 6, prefer: ["rt", "lt", "up"], t: "AI 연결을 켜면 대신 지켜봐요", d: "하루 한 번 공시·뉴스·주가를 확인해 이 메모에 붙여 드려요." },
  { sel: '[data-coach="feed"]', pad: 4, prefer: ["rt", "lt", "up"], t: "내 생각 아래 소식이 쌓여요", d: "처음 생각과 새 소식을 나란히 보며 판단을 이어가세요." },
  { sel: '[data-coach="studio"]', pad: 6, prefer: ["lt", "up"], t: "읽기 바쁠 땐 스튜디오", d: "쌓인 소식을 라디오·보고서로 바꿔 드려요. 퀴즈는 무료예요." },
];
const N = COACH_STEPS.length;
const TIP_W = 320, EDGE = 16;

/* 코치마크를 보여 줄 종목과 메모: 소식이 붙은 AI 연결 메모가 있는 종목을 먼저 */
const newsCount = (m: Memo) => (m.ai ? (m.timeline ?? []).filter((x) => x.kind === "뉴스" || x.kind === "공시" || x.kind === "주가").length : 0);
export function coachMemo(memos: Memo[], code: string) {
  const mine = memos.filter((m) => m.stock_code === code && newsCount(m) > 0);
  return mine.find((m) => newsCount(m) >= 2) ?? mine[0];
}
export function coachStock(stocks: Stock[], memos: Memo[]) {
  return stocks.find((s) => coachMemo(memos, s.stock_code)) ?? stocks[0];
}

type Box = { x: number; y: number; w: number; h: number };
const kk = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--k")) || 1;

export function Coach() {
  const { coach, setCoach, act, go, setOverlay, setStudio, stocks, memos, setMemoOpen } = useApp();
  const snack = useSnack();
  const step = coach?.step ?? null;
  const [vp, setVp] = useState({ w: window.innerWidth, h: window.innerHeight });
  const [target, setTarget] = useState<Box | null>(null); // 찾은 대상 (여백 포함)
  const [ready, setReady] = useState(false);              // 대상 찾기가 끝남 (없으면 가운데 카드)
  const [pos, setPos] = useState<{ left: number; top: number; side: Side | "no"; ax: number; ay: number } | null>(null);
  const [tour, setTour] = useState(false);
  const firstPos = useRef(true);
  const pathRef = useRef<SVGPathElement>(null), ringRef = useRef<HTMLElement>(null), tipRef = useRef<HTMLDivElement>(null), nxRef = useRef<HTMLButtonElement>(null);
  const hole = useRef<Box | null>(null), anim = useRef(0);

  /* ---- 구멍 그리기 (Lucian #197 shape/paint/moveHole) ---- */
  const radius = useCallback((b: Box, round?: boolean) => (round ? Math.min(b.w, b.h) / 2 : Math.min(14, b.h / 2, b.w / 2)), []);
  const paint = useCallback((b: Box, round?: boolean) => {
    const W = window.innerWidth, H = window.innerHeight, r = radius(b, round), { x, y, w, h } = b;
    const d = `M0 0H${W}V${H}H0Z` + (w > 0.5 && h > 0.5 ? ` M${x + r} ${y}H${x + w - r}A${r} ${r} 0 0 1 ${x + w} ${y + r}V${y + h - r}A${r} ${r} 0 0 1 ${x + w - r} ${y + h}H${x + r}A${r} ${r} 0 0 1 ${x} ${y + h - r}V${y + r}A${r} ${r} 0 0 1 ${x + r} ${y}Z` : "");
    pathRef.current?.setAttribute("d", d);
    const ring = ringRef.current;
    if (ring) { ring.style.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px)`; ring.style.width = `${w.toFixed(1)}px`; ring.style.height = `${h.toFixed(1)}px`; ring.style.borderRadius = `${r}px`; }
  }, [radius]);
  const moveHole = useCallback((to: Box, round?: boolean) => {
    cancelAnimationFrame(anim.current);
    const from = hole.current ?? { x: to.x + to.w / 2, y: to.y + to.h / 2, w: 0, h: 0 }, t0 = performance.now(), dur = 520 * kk();
    const f = (now: number) => {
      const k = dur < 20 ? 1 : Math.max(0, Math.min(1, (now - t0) / dur)), c = 1.4, e = 1 + (c + 1) * Math.pow(k - 1, 3) + c * Math.pow(k - 1, 2);
      hole.current = { x: from.x + (to.x - from.x) * e, y: from.y + (to.y - from.y) * e, w: Math.max(0, from.w + (to.w - from.w) * e), h: Math.max(0, from.h + (to.h - from.h) * e) };
      paint(hole.current, round);
      if (k < 1) anim.current = requestAnimationFrame(f);
    };
    f(t0);
  }, [paint]);

  /* ---- 단계마다 화면 준비 ---- */
  const code = (coachStock(stocks, memos) ?? stocks[0])?.stock_code;
  useEffect(() => {
    if (step == null) return;
    setOverlay(null); setMemoOpen(null);
    if (step === -1) { go({ name: "home" }); return; }
    if (step <= 2) { if (code) go({ name: "stock", code, tab: "board" }); return; }
    go({ name: "home" }); setStudio((s) => ({ ...s, open: true, view: "home", dir: "pop" }));
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ④ 도중에 창이 좁아져 스튜디오가 저절로 접히면 다시 펼침 */
  const stOpen = useApp().studio.open;
  useEffect(() => { if (step === 3 && !stOpen) { const t = window.setTimeout(() => setStudio((s) => ({ ...s, open: true, view: "home" })), 60); return () => window.clearTimeout(t); } }, [step, stOpen, vp.w, setStudio]);

  /* ---- 대상 찾기: 자리가 멈출 때까지 기다렸다가 잼. 못 찾으면 가운데 카드 ---- */
  useEffect(() => {
    if (step == null) return;
    setReady(false);
    if (step < 0 || (step === 2 && !(code && coachMemo(memos, code)))) { setTarget(null); setReady(true); return; }
    const S = COACH_STEPS[step];
    let raf = 0, stable = 0, last = "", dead = false;
    const t0 = performance.now();
    const read = (): Box | null => {
      const el = document.querySelector<HTMLElement>(S.sel); if (!el) return null;
      const r = el.getBoundingClientRect(); if (r.width < 4 || r.height < 4) return null;
      const x = Math.max(4, r.left - S.pad), y = Math.max(4, r.top - S.pad);
      return { x, y, w: Math.min(window.innerWidth - 4, r.right + S.pad) - x, h: Math.min(window.innerHeight - 4, r.bottom + S.pad) - y };
    };
    const tick = () => {
      if (dead) return;
      const b = read(), key = b ? [b.x, b.y, b.w, b.h].map((v) => Math.round(v)).join(",") : "";
      if (b && key === last) stable++; else stable = 0;
      last = key;
      const waited = performance.now() - t0;
      if (b && stable >= 8 && waited > 240) { setTarget(b); setReady(true); return; }
      if (waited > 2600) { setTarget(b); setReady(true); return; }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    /* 찾은 뒤에도 창 크기·화면이 바뀌면 다시 잼 */
    const again = window.setInterval(() => { const b = read(); if (!b) return; setTarget((p) => (p && Math.abs(p.x - b.x) < 1 && Math.abs(p.y - b.y) < 1 && Math.abs(p.w - b.w) < 1 && Math.abs(p.h - b.h) < 1 ? p : (stable >= 8 || performance.now() - t0 > 2600 ? b : p))); }, 300);
    return () => { dead = true; cancelAnimationFrame(raf); clearInterval(again); };
  }, [step, vp.w, vp.h, step === 3 && stOpen]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const f = () => setVp({ w: window.innerWidth, h: window.innerHeight }); window.addEventListener("resize", f); return () => window.removeEventListener("resize", f); }, []);

  /* ---- 구멍 옮기기 + 말풍선 자리 (대상의 오른쪽 → 왼쪽 → 아래 → 위 가운데 들어가는 첫 자리) ---- */
  useLayoutEffect(() => {
    if (step == null || !ready) return;
    const W = window.innerWidth, H = window.innerHeight, S = step >= 0 ? COACH_STEPS[step] : null;
    if (target && S) moveHole(target, S.round); else { const c = hole.current ? { x: hole.current.x + hole.current.w / 2, y: hole.current.y + hole.current.h / 2, w: 0, h: 0 } : { x: W / 2, y: H / 2, w: 0, h: 0 }; moveHole(c); }
    const tip = tipRef.current; if (!tip) return;
    const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
    let p: { left: number; top: number; side: Side | "no"; ax: number; ay: number } | null = null;
    tip.style.width = "";
    let tw = Math.min(TIP_W, W - EDGE * 2), th = tip.offsetHeight;
    if (target && S) {
      const t = target, cx0 = t.x + t.w / 2, cy0 = t.y + t.h / 2;
      /* 기본 폭(320)으로 자리가 없으면 좁은 폭(280)·좁은 간격으로 한 번 더 찾음 — 화면이 좁아도 밝힌 곳을 가리지 않게 */
      for (const [w0, GAP, EDGE] of [[tw, 16, 16], [Math.min(280, W - 24), 12, 12]] as const) {
       if (p) break;
       if (w0 !== tw) { tip.style.width = `${w0}px`; tw = w0; th = tip.offsetHeight; }
       for (const side of S.prefer) {
        if (side === "rt" && t.x + t.w + GAP + tw <= W - EDGE) { const top = clamp(cy0 - th / 2, EDGE, H - th - EDGE); p = { left: t.x + t.w + GAP, top, side, ax: 0, ay: clamp(cy0 - top, 24, th - 24) }; break; }
        if (side === "lt" && t.x - GAP - tw >= EDGE) { const top = clamp(cy0 - th / 2, EDGE, H - th - EDGE); p = { left: t.x - GAP - tw, top, side, ax: 0, ay: clamp(cy0 - top, 24, th - 24) }; break; }
        if (side === "dn" && t.y + t.h + GAP + th <= H - EDGE) { const left = clamp(cx0 - tw / 2, EDGE, W - tw - EDGE); p = { left, top: t.y + t.h + GAP, side, ax: clamp(cx0 - left, 24, tw - 24), ay: 0 }; break; }
        if (side === "up" && t.y - GAP - th >= EDGE) { const left = clamp(cx0 - tw / 2, EDGE, W - tw - EDGE); p = { left, top: t.y - GAP - th, side, ax: clamp(cx0 - left, 24, tw - 24), ay: 0 }; break; }
      }
      }
      /* 어느 쪽에도 자리가 없으면 대상 안쪽 아래에 */
      if (!p) { tip.style.width = ""; tw = Math.min(TIP_W, W - EDGE * 2); th = tip.offsetHeight; }
      if (!p) p = { left: clamp(cx0 - tw / 2, EDGE, W - tw - EDGE), top: clamp(t.y + t.h - th - 24, EDGE, H - th - EDGE), side: "no", ax: 0, ay: 0 };
    } else p = { left: (W - tw) / 2, top: Math.max(EDGE, (H - th) / 2), side: "no", ax: 0, ay: 0 };
    setPos(p);
    const id = requestAnimationFrame(() => { firstPos.current = false; nxRef.current?.focus({ preventScroll: true }); });
    return () => cancelAnimationFrame(id);
  }, [step, ready, target, vp.w, vp.h, moveHole]);

  /* ---- 시작 · 끝 ---- */
  useEffect(() => {
    if (step == null) { setTour(false); hole.current = null; firstPos.current = true; setPos(null); cancelAnimationFrame(anim.current); return; }
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setTour(true)));
    return () => cancelAnimationFrame(id);
  }, [step == null]); // eslint-disable-line react-hooks/exhaustive-deps
  const end = useCallback((finished: boolean) => {
    setCoach(null); act.coachDone(); setOverlay(null); go({ name: "home" });
    snack(finished ? "준비됐어요. 떠오른 생각 한 줄부터 적어 보세요" : "사용법은 설정 › 정보에서 다시 볼 수 있어요", finished ? { check: true } : {});
  }, [setCoach, act, setOverlay, go, snack]);
  const next = useCallback(() => { if (step == null) return; if (step < N - 1) setCoach({ step: step + 1 }); else end(true); }, [step, setCoach, end]);
  const prev = useCallback(() => { if (step != null && step > 0) setCoach({ step: step - 1 }); }, [step, setCoach]);
  /* 키보드: 화면 뒤 입력칸으로 글자가 들어가지 않게 막고, → 다음 · ← 이전 · Esc 끝 */
  useEffect(() => {
    if (step == null) return;
    const f = (e: KeyboardEvent) => {
      const inTip = tipRef.current?.contains(e.target as Node);
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); end(false); return; }
      if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); next(); return; }
      if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); prev(); return; }
      if (inTip && (e.key === "Enter" || e.key === " " || e.key === "Tab")) return;
      e.preventDefault(); e.stopPropagation();
    };
    window.addEventListener("keydown", f, true);
    (document.activeElement as HTMLElement | null)?.blur?.();
    return () => window.removeEventListener("keydown", f, true);
  }, [step, next, prev, end]);

  if (step == null) return null;
  const S = step >= 0 ? COACH_STEPS[step] : null;
  const shown = tour && ready && !!pos;
  return createPortal(
    <div className={cx("u197", tour && "is-tour")} role="presentation" data-coach-root data-step={step} data-ready={shown ? "1" : "0"}>
      <svg className="u197-ov" aria-hidden><path ref={pathRef} fillRule="evenodd" d={`M0 0H${vp.w}V${vp.h}H0Z`} /></svg>
      <div className="u197-block" onMouseDown={(e) => e.preventDefault()} />
      <i ref={ringRef} className={cx("u197-ring", shown && target && S && "on")} aria-hidden />
      <div ref={tipRef} role="dialog" aria-label="화면 안내" className={cx("u197-tip", pos?.side ?? "no", shown && "on", firstPos.current && "first")}
        style={{ left: pos?.left ?? (vp.w - TIP_W) / 2, top: pos?.top ?? vp.h / 2 - 90, ["--ax" as string]: `${pos?.ax ?? 30}px`, ["--ay" as string]: `${pos?.ay ?? 30}px` }}>
        {step >= 0 && <button className="u197-x" type="button" onClick={() => end(false)}>건너뛰기</button>}
        <div key={step} className="ct">
          {S ? <><small>{step + 1} / {N}</small><b>{S.t}</b><p>{S.d}</p></>
            : <><small>처음 오셨네요</small><b>30초만 둘러볼까요?</b><p>메모 쓰기부터 스튜디오까지, 꼭 필요한 4가지만 알려 드릴게요.</p></>}
        </div>
        <div className="u197-tf">
          {S ? <span className="u197-dots" aria-hidden>{COACH_STEPS.map((_, i) => <i key={i} className={i === step ? "on" : undefined} />)}</span> : <span className="u197-dots" />}
          {S ? (step > 0 && <button className="u197-pv" type="button" onClick={prev}>이전</button>) : <button className="u197-pv" type="button" onClick={() => end(false)}>나중에</button>}
          <button ref={nxRef} className="u197-nx" type="button" onClick={S ? next : () => setCoach({ step: 0 })}>{S ? (step === N - 1 ? "완료" : "다음") : "둘러보기"}</button>
        </div>
      </div>
    </div>, document.body);
}
