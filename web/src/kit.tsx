import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { X } from "lucide-react";
import { createPortal } from "react-dom";
import { LOGO_D, LOGO_VB } from "./logo";

export const cx = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(" ");
export const won = (n: number) => n.toLocaleString("ko-KR");
export const fmt = (v: number, d = 2) => v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
export const UP = "#E5484D", DOWN = "#2F6BDB";

export function Logo({ w = 104, white }: { w?: number; white?: boolean }) {
  return <svg role="img" aria-label="MEMO'S" width={w} height={w * 0.3} viewBox={LOGO_VB}><path fillRule="evenodd" fill={white ? "#fff" : "#111"} d={LOGO_D} /></svg>;
}

/* ---------- 버튼 ---------- */
type BtnKind = "ink" | "gray" | "line" | "danger" | "ghost" | "white";
export function Btn({ kind = "ink", size = "md", className, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { kind?: BtnKind; size?: "sm" | "md" | "lg" }) {
  const k = { ink: "bg-[#111] text-white hover:bg-zinc-800 disabled:bg-zinc-200 disabled:text-zinc-400", gray: "bg-zinc-100 text-zinc-900 hover:bg-zinc-200 disabled:text-zinc-400", line: "border border-zinc-200 bg-white text-zinc-900 hover:bg-zinc-50", danger: "bg-red-600 text-white hover:bg-red-700", ghost: "text-zinc-600 hover:bg-zinc-100", white: "bg-white text-zinc-950 hover:bg-zinc-100" }[kind];
  const s = { sm: "h-8 px-3 text-[13px] rounded-lg", md: "h-10 px-4 text-[14px] rounded-[10px]", lg: "h-12 px-5 text-[15px] rounded-xl" }[size];
  return <button {...p} className={cx("m-press inline-flex items-center justify-center gap-1.5 font-bold transition-colors disabled:cursor-not-allowed", k, s, className)} />;
}

/* 알약 탭 (예빈 앱의 기간 알약: 스프링으로 미끄러짐) */
export function Seg<T extends string>({ value, options, onChange, size = "md", full }: { value: T; options: readonly (readonly [T, string])[]; onChange: (v: T) => void; size?: "sm" | "md"; full?: boolean }) {
  const i = Math.max(0, options.findIndex(([k]) => k === value));
  return (
    <div role="radiogroup" className={cx("relative flex rounded-[11px] bg-zinc-100 p-[3px]", full ? "w-full" : "inline-flex")}>
      <span className="m-pill absolute bottom-[3px] left-[3px] top-[3px] rounded-[9px] bg-white shadow-[0_1px_3px_rgba(0,0,0,.08)]" style={{ width: `calc((100% - 6px) / ${options.length})`, transform: `translateX(${i * 100}%)` }} />
      {options.map(([k, l]) => (
        <button key={k} role="radio" aria-checked={value === k} onClick={() => onChange(k)} className={cx("relative z-10 flex-1 whitespace-nowrap px-3 transition-colors", size === "sm" ? "h-7 text-[13px]" : "h-9 text-[14px]", value === k ? "font-bold text-zinc-950" : "text-zinc-500 hover:text-zinc-800")}>{l}</button>
      ))}
    </div>
  );
}

export function Toggle({ on, onChange, label, disabled }: { on: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} disabled={disabled} onClick={(e) => { e.stopPropagation(); onChange(!on); }} className={cx("relative h-[26px] w-[44px] shrink-0 rounded-full transition-colors disabled:opacity-40", on ? "bg-[#111]" : "bg-zinc-300")}>
      <i className="absolute left-[3px] top-[3px] h-5 w-5 rounded-full bg-white shadow" style={{ transform: on ? "translateX(18px)" : "", transition: "transform calc(.4s * var(--k)) var(--spring)" }} />
    </button>
  );
}

export function Check({ on, onChange, label, round }: { on: boolean; onChange?: (v: boolean) => void; label?: string; round?: boolean }) {
  return (
    <span role="checkbox" aria-checked={on} aria-label={label} tabIndex={onChange ? 0 : -1} onClick={(e) => { if (onChange) { e.stopPropagation(); onChange(!on); } }} onKeyDown={(e) => { if (onChange && (e.key === " " || e.key === "Enter")) { e.preventDefault(); onChange(!on); } }}
      className={cx("m-check grid h-5 w-5 shrink-0 cursor-pointer place-items-center", round ? "rounded-full" : "rounded-[6px]", on ? "bg-[#111]" : "bg-white shadow-[inset_0_0_0_1.5px_#C9CDD4]", on && "m-on")}>
      <svg width="12" height="12" viewBox="0 0 14 14"><path d="M3 7.3 5.8 10 11 4.3" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ strokeDasharray: 14, strokeDashoffset: on ? 0 : 14, transition: "stroke-dashoffset calc(.25s * var(--k)) var(--ease)" }} /></svg>
    </span>
  );
}

/* 플러그 (AI 연결 표시 · 11.11 확정) */
export function Plug({ size = 14, filled = true, color = "currentColor", className }: { size?: number; filled?: boolean; color?: string; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} aria-hidden>
      <path d="M9 3v4M15 3v4" stroke={color} strokeWidth="2" strokeLinecap="round" />
      {filled ? <path d="M6.5 7h11v4a5.5 5.5 0 0 1-11 0z" fill={color} /> : <path d="M6.5 7h11v4a5.5 5.5 0 0 1-11 0z" stroke={color} strokeWidth="2" strokeLinejoin="round" />}
      <path d="M12 16.5V21" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function StockLogo({ s, size = 28 }: { s: { logo: string; logoBg: string }; size?: number }) {
  return <span className="dk-keep grid shrink-0 place-items-center rounded-[8px] font-black text-white" style={{ width: size, height: size, background: s.logoBg, fontSize: s.logo.length > 1 ? size * 0.34 : size * 0.44 }}>{s.logo}</span>;
}

export function KindTag({ k }: { k: string }) {
  const c = k === "공시" ? "bg-red-50 text-red-600" : k === "뉴스" ? "bg-sky-50 text-sky-700" : k === "주가" ? "bg-emerald-50 text-emerald-700" : "bg-zinc-100 text-zinc-600";
  return <span className={cx("inline-flex h-5 shrink-0 items-center rounded px-1.5 text-[13px] font-bold", c)}>{k}</span>;
}

/* ---------- 모달 (예빈 앱의 시트 곡선으로 튀어 오름 · 닫힐 때도 모션) ---------- */
export function useMounted(open: boolean, ms = 260) {
  const [m, setM] = useState(open);
  useEffect(() => { if (open) setM(true); else { const t = setTimeout(() => setM(false), ms); return () => clearTimeout(t); } }, [open, ms]);
  return m;
}
export function Modal({ open, onClose, children, label, z = 60, scrim = "rgba(0,0,0,0.45)", width, top }: { open: boolean; onClose: () => void; children: ReactNode; label: string; z?: number; scrim?: string; width?: number; top?: string }) {
  const mounted = useMounted(open);
  const [on, setOn] = useState(false);
  useEffect(() => { if (open) { const r = requestAnimationFrame(() => requestAnimationFrame(() => setOn(true))); return () => cancelAnimationFrame(r); } setOn(false); }, [open]);
  useEffect(() => { if (!open) return; const k = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, [open, onClose]);
  if (!mounted) return null;
  return createPortal(
    <div className={cx("m-scrim fixed inset-0 overflow-y-auto", top ? "flex items-start justify-center px-4" : "grid place-items-center p-4", on && "on")} style={{ zIndex: z, background: scrim }} onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label={label} onMouseDown={(e) => e.stopPropagation()} style={{ ...(width ? { width, maxWidth: "100%" } : {}), ...(top ? { marginTop: top } : {}) }} className="m-modal max-h-[calc(100vh-32px)]">
        {children}
      </div>
    </div>,
    document.body
  );
}
export function ModalHead({ title, sub, onClose, right }: { title: ReactNode; sub?: string; onClose: () => void; right?: ReactNode }) {
  return (
    <div className="flex items-start gap-3 px-6 pb-3 pt-6">
      <div className="min-w-0 flex-1">{sub && <p className="mb-0.5 text-[13px] text-zinc-500">{sub}</p>}<h2 className="flex items-center gap-1.5 text-[20px] font-black tracking-[-0.02em]">{title}</h2></div>
      {right}
      <button aria-label="닫기" onClick={onClose} className="m-press grid h-9 w-9 place-items-center rounded-full hover:bg-zinc-100"><X className="h-5 w-5" /></button>
    </div>
  );
}

/* ---------- 화면 제목 (11.16 · 모든 화면 같은 자리): 틀 위 32 + 24 = 56에 제목 26, 그 아래 부제 14. 다음 줄은 제목 묶음 아래 32 ---------- */
export function PageTitle({ title, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div data-pagetitle className="relative flex w-full shrink-0 items-start gap-4 pt-6">
      <div className="flex h-[52px] min-w-0 flex-1 flex-col items-start gap-1">
        <p className="w-full whitespace-nowrap text-[26px] font-bold leading-[35px] tracking-[-0.01em] text-[#16171a]">{title}</p>
        {sub && <p className="w-full whitespace-nowrap text-[14px] leading-[21px] text-[#575b63]">{sub}</p>}
      </div>
      {right && <div className="absolute right-0 top-[25px] flex items-center gap-2">{right}</div>}
    </div>
  );
}

/* ---------- 하단 토스트 (Figma 'toast · 완료': 검정 알약, 사이드바 오른쪽 영역 가운데, 아래 30) ---------- */
type SnackOpt = { undo?: () => void; action?: { label: string; run: () => void }; star?: boolean; check?: boolean };
type Snack = SnackOpt & { msg: string; key: number };
const SnackCtx = createContext<(msg: string, opt?: SnackOpt) => void>(() => {});
export const useSnack = () => useContext(SnackCtx);
/* 11.16: 가운데 화면 중 스튜디오에 가려지지 않은 부분의 가운데 (넛지와 같은 기준). 가운데 화면이 없는 화면(소개·로그인)은 null */
export function mainCenter(): number | null {
  const main = document.querySelector("main"); if (!main) return null;
  const r = main.getBoundingClientRect(); if (!r.width) return null;
  const st = document.querySelector('aside[aria-label="스튜디오"]')?.getBoundingClientRect();
  const right = st && st.width > 0 && st.left > r.left && st.left < r.right ? st.left : r.right;
  return r.left + (right - r.left) / 2;
}
export function SnackHost({ children }: { children: ReactNode }) {
  const [s, setS] = useState<Snack | null>(null);
  const [left, setLeft] = useState<number | null>(null);
  const t = useRef(0);
  /* 떠 있는 동안 사이드바·스튜디오가 움직여도 계속 가운데를 따라감 */
  useLayoutEffect(() => {
    if (!s) return;
    let raf = 0; const f = () => { const c = mainCenter(); setLeft((l) => (c === null ? null : l !== null && Math.abs(l - c) < 0.25 ? l : c)); raf = requestAnimationFrame(f); };
    f(); return () => cancelAnimationFrame(raf);
  }, [s]);
  const show = (msg: string, opt: SnackOpt = {}) => {
    clearTimeout(t.current); setS({ msg, ...opt, key: Date.now() });
    t.current = window.setTimeout(() => setS(null), opt.undo ? 5000 : opt.action ? 4200 : 2600);
  };
  useEffect(() => { document.documentElement.dataset.snack = s ? "1" : "0"; }, [s]); // v2: 넛지가 토스트를 피해 올라가도록 알림
  const btn = s?.undo ? { label: "되돌리기", run: s.undo } : s?.action;
  return (
    <SnackCtx.Provider value={show}>
      {children}
      <div role="status" aria-live="polite" className={cx("m-snack fixed bottom-[30px] z-[90] flex items-center gap-[10px] whitespace-nowrap min-h-[46px] rounded-full bg-[#15171a] py-2 pr-2 shadow-[0px_12px_30px_0px_rgba(20,23,26,0.25)]", s && "on", btn ? "pl-5" : "pl-5 pr-5", !s && "pointer-events-none")}
        style={{ left: left ?? "calc(var(--side, 250px) + (100vw - var(--side, 250px)) / 2)" }}>
        {s?.check && <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="10" fill="#22c55e" /><path d="M6 10.2L8.6 12.8L14 7.4" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>}
        {s?.star && <svg width="18" height="18" viewBox="0 0 16 16" fill="none"><path d="M7.33317 2C7.73317 4.86667 9.13317 6.26667 11.9998 6.66667C9.13317 7.06667 7.73317 8.46667 7.33317 11.3333C6.93317 8.46667 5.53317 7.06667 2.6665 6.66667C5.53317 6.26667 6.93317 4.86667 7.33317 2Z" fill="white" /><path d="M12.6668 10V12.6667M11.3335 11.3333H14.0002" stroke="white" strokeWidth="1.8" strokeLinecap="round" /></svg>}
        <span className="text-[17px] font-bold leading-none tracking-[-0.2px] text-white">{s?.msg}</span>
        {btn && <button onClick={() => { btn.run(); setS(null); }} className="flex h-[32px] items-center gap-[6px] rounded-full bg-white px-3 text-[14px] font-bold leading-none tracking-[-0.2px] text-[#15171a]">{s?.undo && <svg key={s.key} width="16" height="16" viewBox="0 0 16 16" className="undo-ring -rotate-90" aria-hidden><circle cx="8" cy="8" r="6" fill="none" stroke="#e5e7eb" strokeWidth="2" /><circle cx="8" cy="8" r="6" fill="none" stroke="#15171a" strokeWidth="2" strokeDasharray="37.7" style={{ animation: "undo-ring 5s linear forwards" }} /></svg>}{btn.label}</button>}
      </div>
    </SnackCtx.Provider>
  );
}

/* ---------- 숫자 ---------- */
export function Odo({ n }: { n: number }) {
  const s = String(n);
  return <span className="m-odo" aria-label={s}>{s.split("").map((d, i) => <span key={s.length + "-" + i} style={{ transform: `translateY(-${+d * 1.3}em)` }}>{Array.from({ length: 10 }, (_, k) => <span key={k}>{k}</span>)}</span>)}</span>;
}
export function CountUp({ to, d = 0, dur = 650, comma = true }: { to: number; d?: number; dur?: number; comma?: boolean }) {
  const [v, setV] = useState(0); const from = useRef(0);
  useEffect(() => {
    const a = from.current, t0 = performance.now(); let raf = 0;
    const f = (t: number) => { const k = Math.min(1, (t - t0) / dur); setV(a + (to - a) * (1 - Math.pow(1 - k, 3))); if (k < 1) raf = requestAnimationFrame(f); else from.current = to; };
    raf = requestAnimationFrame(f); return () => cancelAnimationFrame(raf);
  }, [to, dur]);
  return <>{d ? fmt(v, d) : comma ? won(Math.round(v)) : Math.round(v)}</>;
}

/* ---------- 차트 도구 ---------- */
export function series(seed: number, n: number, end: number, vol: number) {
  let x = seed * 9301 + 49297; const r = () => { x = (x * 9301 + 49297) % 233280; return x / 233280; };
  const a = [end]; for (let i = 1; i < n; i++) a.unshift(a[0] * (1 + (r() - 0.48) * vol)); return a;
}
export function linePath(arr: number[], w: number, h: number, pad = 4) {
  const mn = Math.min(...arr), mx = Math.max(...arr);
  const pts = arr.map((v, i) => [(i / (arr.length - 1)) * w, h - pad - ((v - mn) / (mx - mn || 1)) * (h - pad * 2)] as const);
  const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  return { d, area: d + ` L${w} ${h} L0 ${h}Z`, pts, mn, mx };
}
export function Spark({ data, color, w = 160, h = 44, id, area = true, dot }: { data: number[]; color: string; w?: number; h?: number; id: string; area?: boolean; dot?: boolean }) {
  const p = linePath(data, w, h);
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="overflow-visible" aria-hidden>
      <defs><linearGradient id={id} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".2" /><stop offset="1" stopColor={color} stopOpacity="0" /></linearGradient></defs>
      {area && <path d={p.area} fill={`url(#${id})`} />}
      <path className="m-line" d={p.d} fill="none" stroke={color} strokeWidth="1.7" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
      {dot && <circle cx={p.pts[p.pts.length - 1][0]} cy={p.pts[p.pts.length - 1][1]} r="3.5" fill={color} stroke="#fff" strokeWidth="2" vectorEffect="non-scaling-stroke" />}
    </svg>
  );
}

export function Skel({ className, style }: { className?: string; style?: React.CSSProperties }) { return <div className={cx("m-sk", className)} style={style} />; }

export function Empty({ icon, title, body, children }: { icon: ReactNode; title: string; body: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <span className="grid h-14 w-14 place-items-center rounded-2xl bg-zinc-100 text-zinc-500">{icon}</span>
      <h3 className="mt-4 text-[17px] font-bold">{title}</h3>
      <p className="mt-1.5 max-w-sm text-[14px] leading-relaxed text-zinc-500">{body}</p>
      {children && <div className="mt-5 flex gap-2">{children}</div>}
    </div>
  );
}

/* 등장 시 차례로 (예빈 앱 stagger 70ms) */
export function Reveal({ i = 0, children, className, as: Tag = "div" }: { i?: number; children: ReactNode; className?: string; as?: "div" | "section" | "li" }) {
  return <Tag className={cx("m-reveal", className)} style={{ ["--i" as string]: i }}>{children}</Tag>;
}
