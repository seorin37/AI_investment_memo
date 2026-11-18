/* 6 · 기업 메모장 (보드) + 메모 카드 웹 컴포넌트(테이프·플러그) + 메모 팝업 1~5 · AI 업데이트 · 6.1 새 메모 · 6.2 체크리스트 — Figma 2.5 그대로 */
import { createPortal } from "react-dom";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Modal, cx, series } from "../kit";
import { PAPER, type ColorKey, type Memo, type TL, type Stock } from "../data";
import { useApp, useChecklist } from "../store";
import { API_MODE } from "../api/config";
import { mmdd } from "../api/map";
import { coachMemo } from "../coach";
import { Spark, Arrow, Cross, useStudioOpen } from "../nudge";
import { BoardHead, MemoList, SelectBar, ConnectDialog, CtxMenu, Pick, Dots, useMemoActions, type BoardFilter } from "./memox";
import { SpentBox, Disclaimer } from "../x";
import { useSnack } from "../kit";

const TR = "tracking-[-0.01em]";
const COLORS: ColorKey[] = ["yellow", "blue", "pink", "green", "purple"];
const plugPaths = (on: boolean) => on ? (
  <><path d="M5.25 1.75V4.08333M8.75 1.75V4.08333" stroke="black" strokeWidth="1.2" strokeLinecap="round" /><path d="M3.7915 4.08301H10.2082V6.41634C10.2082 7.26724 9.87015 8.0833 9.26847 8.68498C8.66679 9.28665 7.85074 9.62467 6.99984 9.62467C6.14893 9.62467 5.33288 9.28665 4.7312 8.68498C4.12952 8.0833 3.7915 7.26724 3.7915 6.41634V4.08301Z" fill="#16161C" /><path d="M7 9.625V12.25" stroke="black" strokeWidth="1.2" strokeLinecap="round" /></>
) : (
  <><path d="M5.25 1.75V4.08333M8.75 1.75V4.08333" stroke="#16161C" strokeOpacity="0.45" strokeWidth="1.2" strokeLinecap="round" /><path d="M3.7915 4.08301H10.2082V6.41634C10.2082 7.26724 9.87015 8.0833 9.26847 8.68498C8.66679 9.28665 7.85074 9.62467 6.99984 9.62467C6.14893 9.62467 5.33288 9.28665 4.7312 8.68498C4.12952 8.0833 3.7915 7.26724 3.7915 6.41634V4.08301Z" stroke="#16161C" strokeOpacity="0.45" strokeWidth="1.2" strokeLinejoin="round" /><path d="M7 9.625V12.25" stroke="#16161C" strokeOpacity="0.45" strokeWidth="1.2" strokeLinecap="round" /></>
);
const TAPE_ON = "M0 3.76855L71.9013 0.000365913L68.5998 3.87847L72.2834 7.29036L68.9818 11.1685L72.6707 14.6802L69.3639 18.4585L73.0527 21.9702L1.15139 25.7384L4.45295 21.8603L0.769339 18.4484L4.0709 14.5703L0.382052 11.0586L3.68885 7.28031L0 3.76855Z";
const TAPE_LIFT = "M6 12L76.9062 -0.50267L74.1018 3.74889L78.1738 6.68643L75.3695 10.938L79.4588 13.974L76.6371 18.1271L80.7264 21.1631L9.82026 33.6658L12.6246 29.4142L8.55263 26.4767L11.357 22.2251L7.26763 19.1891L10.0893 15.036L6 12Z";
const TAPE_DASH = "M69.499 4.72852L71 6.27051V6.27148L70.4619 6.79395L70.96 7.30664L70.4551 7.8418L70.999 8.35645L69.5 9.94238L68.9551 9.42773L67.9551 10.4844L67.4678 11L67.9551 11.5156L68.9551 12.5723L69.5 12.0576V12.0566L70.999 13.6426H71L70.4551 14.1582L70.96 14.6924L70.4619 15.2061L71 15.7285L69.499 17.2705L68.9619 16.749L67.9619 17.7773L67.4609 18.293L67.9551 18.8154L68.9551 19.8721L69.5 19.3574V19.3564L70.999 20.9424H71L70.6748 21.25H69.9424V22H66.8574V21.25H62.7432V22H59.6572V21.25H55.543V22H52.457V21.25H48.3428V22H45.2568V21.25H41.1426V22H38.0576V21.25H33.9424V22H30.8574V21.25H26.7432V22H23.6572V21.25H19.543V22H16.457V21.25H12.3428V22H9.25684V21.25H5.14258V22H2.05762V21.25H1.3252L1 20.9424L2.49902 19.3564L2.5 19.3574L3.04492 19.8721L4.04492 18.8154L4.53906 18.293L4.03809 17.7773L3.03809 16.749L2.5 17.2705L0.999023 15.7285L1.53809 15.2061L1.03906 14.6924L1.54492 14.1582L1 13.6426L2.49902 12.0566L2.5 12.0576L3.04492 12.5723L4.04492 11.5156L4.53223 11L4.04492 10.4844L3.04492 9.42773L2.49902 9.94238L1 8.35645L1.54492 7.8418L1.03906 7.30664L1.53809 6.79395L1 6.27148L0.999023 6.27051L2.5 4.72852L3.03809 5.25098L4.03809 4.22266L4.53906 3.70703L4.04492 3.18457L3.04492 2.12793L2.49902 2.64258L1 1.05664L1.3252 0.75H2.05762V0H5.14258V0.75H9.25684V0H12.3428V0.75H16.457V0H19.543V0.75H23.6572V0H26.7432V0.75H30.8574V0H33.9424V0.75H38.0576V0H41.1426V0.75H45.2568V0H48.3428V0.75H52.457V0H55.543V0.75H59.6572V0H62.7432V0.75H66.8574V0H69.9424V0.75H70.6748L70.999 1.05664L69.5 2.64258L68.9551 2.12793L67.9551 3.18457L67.4609 3.70703L67.9619 4.22266L68.9619 5.25098L69.499 4.72852Z";

/* ---------- 머리 (기업명 · 가격 · 작은 차트) ---------- */
const SK_LINE = "M0 42.8L3.5 41.4L7.1 39.7L10.6 37.5L14.1 35.5L17.7 30.9L21.2 29.3L24.7 31.9L28.3 30.3L31.8 28.1L35.3 27.2L38.9 26.1L42.4 21.7L45.9 21.1L49.5 18.2L53 15.3L56.5 17.2L60.1 18.7L63.6 19.4L67.1 19.1L70.7 19L74.2 16.9L77.7 19L81.3 16.9L84.8 14.9L88.3 14.3L91.9 9.9L95.4 5.8L98.9 2L102.5 2.5L106 0";
function MiniChart({ s }: { s: Stock }) {
  const d = useMemo(() => {
    if (s.code === "000660") return SK_LINE;
    const a = series(s.seed + 7, 31, s.price, 0.02), mn = Math.min(...a), mx = Math.max(...a);
    return a.map((v, i) => (i ? "L" : "M") + ((i / 30) * 106).toFixed(1) + " " + (((mx - v) / (mx - mn || 1)) * 42.8).toFixed(1)).join("");
  }, [s]);
  const up = s.chg >= 0, c = up ? "#E5484D" : "#2F6BDB";
  const endY = Number(d.split(/[ML]/).filter(Boolean).pop()!.split(" ")[1]);
  return (
    <div className="relative h-16 w-[116px] shrink-0">
      <svg className="absolute left-0 top-[53.9px]" width="116" height="1" viewBox="0 0 116 1" fill="none"><path d="M0 0.5H116" stroke="#8E8A97" strokeOpacity="0.5" strokeDasharray="2 4" /></svg>
      <svg className="absolute left-0 top-[11.1px] overflow-visible" width="106" height="52.9" viewBox="0 0 106 52.9" fill="none">
        <defs><linearGradient id={"mc" + s.code} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={c} stopOpacity="0.22" /><stop offset="1" stopColor={c} stopOpacity="0" /></linearGradient></defs>
        <path d={d + "V52.9H0Z"} fill={`url(#mc${s.code})`} />
        <path className="m-line" pathLength={400} d={d} stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {s.code === "000660" && <div className="absolute left-[14.17px] top-[38.55px] h-[7px] w-[7px] rounded-full border-[1.5px] border-[#57535f] bg-white" />}
      <div className="absolute left-[98px] h-4 w-4 rounded-full border-[1.5px] opacity-[0.35]" style={{ top: 11.1 + endY - 8, borderColor: c }} />
      <div className="absolute left-[102px] h-2 w-2 rounded-full border-2 border-white" style={{ top: 11.1 + endY - 4, background: c }} />
    </div>
  );
}
export function StockHead({ s }: { s: Stock }) {
  const up = s.chg >= 0;
  return (
    <div className="relative top-[-1px] flex h-16 w-full shrink-0 items-start justify-between pr-2">
      <div className="flex flex-col items-start gap-[6px]">
        <div className="flex h-[34px] items-center gap-[10px]">
          <div className="dk-keep flex h-8 w-8 items-center justify-center rounded-[9.6px]" style={{ background: s.logoBg }}><p className="text-center font-bold leading-none text-white" style={{ fontSize: s.logo.length > 1 ? 10.9 : 13.6 }}>{s.logo}</p></div>
          <p className="whitespace-nowrap text-[30px] font-bold leading-[40px] text-[#191f28]">{s.name}</p>
        </div>
        <div className="flex h-5 items-center gap-2">
          <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">{s.code} · {s.market}</p>
          <div className="flex items-center rounded-[6px] bg-[#e8edf5] px-2 py-[3px]"><p className="whitespace-nowrap text-[13px] font-medium leading-[20px] text-black">{s.hold === "보유" ? "보유 중" : "관심"}</p></div>
        </div>
      </div>
      {API_MODE ? (
        /* 시세 API가 아직 없어(분류 C) 예시 가격을 실제처럼 보이지 않게 비워 둠 */
        <div data-price-pending className="flex flex-col items-end gap-[2px]">
          <p className="whitespace-nowrap text-[26px] font-bold leading-[35px] text-[#c4c9d0]">—</p>
          <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">시세 준비 중</p>
        </div>
      ) : (
      <div className="flex items-start gap-6">
        <div className="flex flex-col items-end gap-[2px]">
          <p className="whitespace-nowrap text-[26px] font-bold leading-[35px] text-[#191f28]">{s.price.toLocaleString("ko-KR")}원</p>
          <p className="whitespace-pre text-[13px] font-bold leading-[20px]" style={{ color: up ? "#e5484d" : "#2f6bdb" }}>{up ? "+" : "-"}{Math.abs(s.chg).toLocaleString("ko-KR")}  {up ? "+" : "-"}{Math.abs(s.pct).toFixed(2)}%</p>
          <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">10.11 15:30 기준</p>
        </div>
        <MiniChart s={s} />
      </div>
      )}
    </div>
  );
}

/* ---------- 위치 바뀔 때 미끄러지듯 (FLIP) ---------- */
export function useFlip(ref: React.RefObject<HTMLDivElement | null>) {
  const prev = useRef(new Map<string, { x: number; y: number }>());
  useLayoutEffect(() => {
    const box = ref.current; if (!box) return;
    const o = box.getBoundingClientRect(), z = o.width / (box.offsetWidth || 1); // 고정 틀이 축소돼 있으면 화면 px → 틀 px
    const next = new Map<string, { x: number; y: number }>();
    box.querySelectorAll<HTMLElement>("[data-flip]").forEach((el) => {
      const r = el.getBoundingClientRect(), k = el.dataset.flip!, p = { x: (r.left - o.left) / z, y: (r.top - o.top) / z };
      next.set(k, p);
      const q = prev.current.get(k);
      if (q && (Math.abs(q.x - p.x) > 1 || Math.abs(q.y - p.y) > 1)) {
        const kk = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--k")) || 1;
        el.animate([{ transform: `translate(${q.x - p.x}px, ${q.y - p.y}px)` }, { transform: "none" }], { duration: 460 * kk, easing: "cubic-bezier(.2,.8,.2,1)" });
      }
    });
    prev.current = next;
  });
}

/* ---------- 메모 카드 (웹 컴포넌트) ---------- */
const Tip = ({ children, className, style }: { children: ReactNode; className?: string; style?: React.CSSProperties }) => (
  <div className={cx("pointer-events-none absolute z-30 flex whitespace-nowrap rounded-[8px] bg-[#16161c] px-[10px] py-[6px]", className)} style={style}><p className="text-[13px] font-medium leading-[20px] text-white">{children}</p></div>
);
function MemoCard({ m, onOpen, onPin, onAi, fresh }: { m: Memo; onOpen: () => void; onPin: () => void; onAi: () => void; fresh?: boolean }) {
  const P = PAPER[m.color];
  const [hov, setHov] = useState(false), [tape, setTape] = useState(false), [plug, setPlug] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const t = useRef(0);
  const toggleAi = (e: React.MouseEvent) => {
    e.stopPropagation(); onAi(); setPlug(false);
    clearTimeout(t.current); setNote(m.ai ? "AI 연결을 껐어요." : "이제 AI가 이 메모를 지켜봐요. 새 소식이 오면 알려 드릴게요.");
    t.current = window.setTimeout(() => setNote(null), 2600);
  };
  useEffect(() => () => clearTimeout(t.current), []);
  return (
    <div data-flip={"m" + m.id} className={cx("dk-keep relative h-[200px] w-full shrink-0 cursor-pointer", fresh && "m-new", (tape || plug || note) && "z-20")} onMouseEnter={() => setHov(true)} onMouseLeave={() => { setHov(false); setTape(false); setPlug(false); }} onClick={onOpen}>
      <div className="flex h-full w-full flex-col items-start gap-2 rounded-[16px_16px_0px_16px] pb-10 pl-5 pr-5 pt-[18px]" style={{ background: P.bg }}>
        <div className="flex w-full shrink-0 items-center justify-between">
          <p className="whitespace-nowrap text-[13px] font-medium leading-[20px] text-[#4a4a55]">{m.date} 작성</p>
          <button aria-label={m.ai ? "AI 연결 끄기" : "AI 연결 켜기"} aria-pressed={m.ai} onClick={toggleAi} onMouseEnter={() => setPlug(true)} onMouseLeave={() => setPlug(false)}
            className="relative h-7 w-7 shrink-0 rounded-full" style={{ background: m.ai ? "rgba(255,255,255,0.8)" : "rgba(255,255,255,0.4)", boxShadow: plug ? "inset 0 0 0 1px rgba(22,22,28,0.25)" : undefined }}>
            <svg key={String(m.ai)} className={cx("absolute left-[7px] top-[7px]", m.ai && "m-pop")} width="14" height="14" viewBox="0 0 14 14" fill="none">{plugPaths(m.ai)}</svg>
          </button>
        </div>
        <p className="line-clamp-2 w-full shrink-0 break-keep text-[20px] font-bold leading-[1.36] text-[#16161c]">{m.title}</p>
        <p className="line-clamp-2 w-full shrink-0 break-keep text-[14px] leading-[1.5] text-[#2e2e38]">{m.body.replace(/\n/g, " ")}</p>
      </div>
      <svg className="absolute bottom-0 right-0" width="30" height="30" viewBox="0 0 30 30" fill="none"><path className="memo-fold" d="M30 0V30H0L30 0Z" fill="#F3F4F6" /><path d="M0 9C0 3 3 0 9 0H30L0 30V9Z" fill={P.accent} /></svg>
      {/* 테이프 (84×34, 가운데 · 위 -16) */}
      <button aria-label={m.pinned ? "테이프 떼기 · 고정 풀기" : "테이프 붙이기 · 맨 위에 고정"} onClick={(e) => { e.stopPropagation(); setTape(false); onPin(); }} onMouseEnter={() => setTape(true)} onMouseLeave={() => setTape(false)}
        className="absolute left-1/2 top-[-16px] z-10 h-[34px] w-[84px] -translate-x-1/2">
        {m.pinned ? (tape
          ? <svg className="absolute left-0 top-[-6.5px] overflow-visible" width="86" height="43" viewBox="0 0 86 43" fill="none" style={{ filter: "drop-shadow(0 3px 6px rgba(0,0,0,0.18))" }}><path opacity="0.85" d={TAPE_LIFT} fill={P.accent} /></svg>
          : <svg key="on" className="m-pop absolute left-[6px] top-[5.23px]" width="74" height="26" viewBox="0 0 74 26" fill="none"><path opacity="0.95" d={TAPE_ON} fill={P.accent} /></svg>
        ) : hov && <svg className="m-pop absolute left-[6px] top-[6px]" width="72" height="22" viewBox="0 0 72 22" fill="none"><path d={TAPE_DASH} fill={P.accent} fillOpacity="0.22" stroke={P.accent} strokeWidth="1.5" strokeDasharray="4 3" /></svg>}
      </button>
      {tape && <Tip className="left-1/2 top-[-56px] -translate-x-1/2">{m.pinned ? "눌러서 테이프 떼기 · 고정 풀기" : "눌러서 테이프 붙이기 · 맨 위에 고정"}</Tip>}
      {plug && !m.ai && <Tip className="right-0 top-[-28px]">AI 연결 켜기</Tip>}
      {m.badge > 0 && <div className="m-pop absolute right-[-10px] top-[-10px] z-10 flex h-6 w-6 items-center justify-center rounded-full border-2 border-white bg-[#e5484d]"><p className="text-[13px] font-medium leading-[20px] text-white">{m.badge}</p></div>}
      {note && <div key={note} className="m-pop pointer-events-none absolute left-0 top-[212px] z-30 flex rounded-[10px] bg-[#16161c] px-3 py-[9px]"><p className="w-[220px] text-[13px] font-medium leading-[20px] text-white">{note}</p></div>}
    </div>
  );
}

/* 진행 고리 (34) */
function Ring({ done, n, track, arc, text }: { done: number; n: number; track: string; arc: string; text: string }) {
  const C = 2 * Math.PI * 14;
  return (
    <div className="relative flex h-[34px] w-[34px] shrink-0 items-center justify-center">
      <svg className="absolute inset-0" width="34" height="34" viewBox="0 0 34 34" fill="none"><circle cx="17" cy="17" r="14" stroke={track} strokeWidth="3" /><circle cx="17" cy="17" r="14" stroke={arc} strokeWidth="3" strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * (1 - (n ? done / n : 0))} transform="rotate(-90 17 17)" style={{ transition: "stroke-dashoffset calc(.5s * var(--k)) var(--ease)", opacity: done ? 1 : 0 }} /></svg>
      <p className="relative text-[11px] font-medium leading-[16px]" style={{ color: text }}>{done}/{n}</p>
    </div>
  );
}
const CheckDot = ({ on, onClick, off = "#d8d4de", fill = "#ada0c5", w = 1.4 }: { on: boolean; onClick?: (e: React.MouseEvent) => void; off?: string; fill?: string; w?: number }) => (
  <button role="checkbox" aria-checked={on} onClick={onClick} className="flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full transition-colors" style={on ? { background: fill } : { boxShadow: `inset 0 0 0 ${w}px ${off}` }}>
    {on && <svg className="m-pop" width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2.5 6L4.8 8.3L9.5 3.5" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>}
  </button>
);
function ChecklistCard({ code, onOpen }: { code: string; onOpen: () => void }) {
  const { checklist, setChecklist, clTitle } = useChecklist(code);
  const done = checklist.filter((c) => c.d).length;
  return (
    <div data-flip="check" onClick={onOpen} className="flex min-h-[200px] w-full shrink-0 cursor-pointer flex-col items-start overflow-hidden rounded-[16px] border border-[#ebe9ed] bg-white px-5 pb-3 pt-4">
      <div className="flex w-full items-center justify-between pb-2">
        <div className="flex flex-col items-start gap-[1px]"><p className="text-[17px] font-bold leading-[26px] text-[#191f28]">{clTitle}</p><p className="text-[13px] leading-[20px] text-[#8a8592]">하나씩 확인해 보세요</p></div>
        <Ring done={done} n={checklist.length} track="#ECEAF1" arc="#AB98CD" text="#777080" />
      </div>
      {checklist.map((c, i) => (
        <div key={i} className="flex h-[40px] w-full items-center gap-[10px] border-t border-[#f0eef2]">
          <CheckDot on={c.d} onClick={(e) => { e.stopPropagation(); setChecklist((l) => l.map((x, j) => (j === i ? { ...x, d: !x.d } : x))); }} />
          <p className={cx("truncate text-[15px] leading-[23px] transition-colors", c.d ? "text-[#a29da9] line-through" : "text-[#3d3945]")}>{c.t}</p>
        </div>
      ))}
    </div>
  );
}

/* 새 메모 + 버튼 (11.13): 스크롤해도 메인 칸 오른쪽 아래에 떠 있음. 검정 */
function NewMemoFab({ onClick }: { onClick: () => void }) {
  const [pos, setPos] = useState<{ right: number; bottom: number } | null>(null);
  useEffect(() => {
    const main = document.querySelector("main"); if (!main) return;
    const f = () => { const r = main.getBoundingClientRect(); setPos({ right: window.innerWidth - r.right + 32, bottom: window.innerHeight - r.bottom + 32 }); };
    f(); const ro = new ResizeObserver(f); ro.observe(main); window.addEventListener("resize", f);
    return () => { ro.disconnect(); window.removeEventListener("resize", f); };
  }, []);
  if (!pos) return null;
  return createPortal(
    <button data-coach="fab" aria-label="새 메모" title="새 메모" onClick={onClick} style={{ right: pos.right, bottom: pos.bottom }}
      className="m-pop fixed z-40 flex h-14 w-14 items-center justify-center rounded-full bg-[#111] shadow-[0_8px_20px_-6px_rgba(0,0,0,0.45),0_2px_6px_rgba(0,0,0,0.12)] transition-transform hover:scale-105 active:scale-95">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 5V19M5 12H19" stroke="white" strokeWidth="2.2" strokeLinecap="round" /></svg>
    </button>, document.body);
}

/* ---------- 보드 ---------- */
export function Board({ s }: { s: Stock }) {
  const { memos, setMemos, memoOpen, setMemoOpen, overlay, coach, hideNudge, studio, x, setX, loadTimeline } = useApp();
  const hasCheck = useChecklist(s.code).has;
  const studioOpen = useStudioOpen();
  const snack = useSnack();
  const act = useMemoActions();
  const [filter, setFilter] = useState<BoardFilter>("all"), [view, setView] = useState<"grid" | "list">("grid");
  const [sel, setSel] = useState<Set<number> | null>(null);
  const [menu, setMenu] = useState<{ m: Memo; at: { x: number; y: number } } | null>(null);
  const [connect, setConnect] = useState<{ id: number; title: string; body: string; isNew?: boolean } | null>(null);
  useEffect(() => { setSel(null); setFilter("all"); }, [s.code]);
  const toggleSel = (m: Memo) => setSel((x) => { const n = new Set(x ?? []); if (n.has(m.id)) n.delete(m.id); else n.add(m.id); return n; });
  const startAi = (m: Memo) => setConnect({ id: m.id, title: m.title, body: m.body });
  const aiOn = (m: Memo, items: string[]) => ({ ai: true, tracks: items.join(" · "), timeline: m.timeline?.some((x) => x.kind === "start") ? m.timeline : [...(m.timeline ?? firstOnly(m)), { kind: "start" as const, date: "11월 16일" }] });
  const [dlg, setDlg] = useState<null | { mode: "edit"; id: number } | { mode: "new"; tab: "memo" | "check"; init?: string }>(null);
  /* v2 코치마크: ② 새 메모 창(AI 연결) → ③ 소식이 붙은 메모의 AI 업데이트 → 그 밖에는 창을 닫음 */
  const wasCoach = useRef(false);
  useEffect(() => {
    if (!coach) { if (wasCoach.current) { wasCoach.current = false; setDlg(null); } return; }
    wasCoach.current = true;
    if (coach.step === 1) setDlg({ mode: "new", tab: "memo" });
    else if (coach.step === 2) { const m = coachMemo(memos, s.code); setDlg(m ? { mode: "edit", id: m.id } : null); }
    else setDlg(null);
  }, [coach?.step, !coach]); // eslint-disable-line react-hooks/exhaustive-deps
  /* 다른 곳에서 '메모 쓰기'(-1) 또는 특정 메모 열기 요청 (11.13) */
  useEffect(() => {
    if (memoOpen == null) return;
    const t = window.setTimeout(() => {
      if (memoOpen === -1) setDlg({ mode: "new", tab: "memo" });
      else if (memos.some((m) => m.id === memoOpen && m.code === s.code)) setDlg({ mode: "edit", id: memoOpen });
      setMemoOpen(null);
    }, 350);
    return () => window.clearTimeout(t);
  }, [memoOpen, s.code]); // eslint-disable-line react-hooks/exhaustive-deps
  const [fresh, setFresh] = useState<number | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  useFlip(ref);
  const mine = memos.filter((m) => m.code === s.code);
  /* 빈 보드: 메모도 체크리스트도 없을 때 (시연 모드는 지금처럼 SK하이닉스만 체크리스트가 있음) */
  const empty = mine.length === 0 && !hasCheck;
  const shown = mine.filter((m) => filter === "all" || (filter === "ai" ? m.ai : m.badge > 0));
  const cols = [0, 1, 2].map((c) => {
    const inCol = shown.filter((m) => (m.col ?? 0) % 3 === c);
    const recent = inCol.filter((m) => m.pinnedAt).sort((a, b) => b.pinnedAt! - a.pinnedAt!);
    const rest = inCol.filter((m) => !m.pinnedAt).sort((a, b) => Number(b.pinned) - Number(a.pinned));
    return [...recent, ...rest];
  });
  const upd = (id: number, p: Partial<Memo>) => setMemos((a) => a.map((m) => (m.id === id ? { ...m, ...p } : m)));
  const open = dlg?.mode === "edit" ? memos.find((m) => m.id === dlg.id) : undefined;
  useEffect(() => { if (API_MODE && open) loadTimeline(open.id); }, [open?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="flex min-h-0 w-full flex-1 flex-col items-start gap-4">
      {studio.creditOut && <SpentBox title="AI 연결이 잠시 멈췄어요" sub={"이번 달 AI 사용량을 다 썼어요. 12월 1일에 다시 찾아요.\n메모는 계속 쓸 수 있어요."} />}
      {!empty && <BoardHead mine={mine} filter={filter} setFilter={(f) => { setFilter(f); }} view={view} setView={setView} />}
      {view === "list" && !empty && <MemoList list={[...shown].sort((a, b) => Number(b.pinned) - Number(a.pinned))} sel={sel} onOpen={(m) => setDlg({ mode: "edit", id: m.id })} onPick={toggleSel} onMenu={(m, at) => setMenu({ m, at })} />}
      <div className={cx("flex min-h-0 w-full flex-1 items-start gap-6", view === "list" && !empty && "hidden")}>
      <div ref={ref} className="flex min-w-0 flex-1 items-start gap-4 pb-10 pt-[14px]">
        {empty && (
          <div data-empty-board className="m-in flex w-full flex-col items-center gap-5 rounded-[20px] border border-dashed border-[#cfd3d9] bg-white px-8 py-12">
            <span className="dk-keep relative block h-[52px] w-[60px]"><span className="block h-full w-full rounded-[10px_10px_0px_10px] bg-[#fceaaa]" /><svg className="absolute bottom-0 right-0" width="16" height="16" viewBox="0 0 30 30" fill="none"><path d="M30 0V30H0L30 0Z" fill="#FFFFFF" /><path d="M0 9C0 3 3 0 9 0H30L0 30V9Z" fill="#efbf2a" /></svg></span>
            <div className="flex flex-col items-center gap-2">
              <p className="text-center text-[22px] font-bold leading-[31px] text-[#191f28]">투자가 막연하세요?</p>
              <p className="break-keep text-center text-[15px] leading-[23px] text-[#6b7684]">떠오른 생각 한 줄부터 적어 보세요.<br />AI 연결을 켜 두면 관련 공시·뉴스를 대신 확인해 드려요.</p>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-2">
              {["실적 나오면 다시 보기", "많이 빠지면 다시 생각해 보기", "요즘 분위기 좋아 보여"].map((t) => (
                <button key={t} onClick={() => setDlg({ mode: "new", tab: "memo", init: t })} className="flex h-10 items-center rounded-full border border-[#e5e7eb] bg-white px-4 text-[15px] font-medium leading-[23px] text-[#333d4b] hover:bg-[#f9f9f9]">{t}</button>
              ))}
            </div>
            <button onClick={() => setDlg({ mode: "new", tab: "memo" })} className="flex h-12 items-center justify-center rounded-[14px] bg-[#111] px-6 text-[17px] font-bold leading-[26px] text-white hover:bg-[#2a2a2a]">첫 메모 쓰기</button>
          </div>
        )}
        {!empty && cols.map((col, ci) => (
          <div key={ci} className="flex w-[276px] shrink-0 flex-col items-start gap-6">
            {col.map((m) => (
              <div key={m.id} className="relative w-full" onContextMenu={(e) => { e.preventDefault(); if (!sel) setMenu({ m, at: { x: e.clientX, y: e.clientY } }); }}>
                <MemoCard m={m} fresh={fresh === m.id} onOpen={() => (sel ? toggleSel(m) : setDlg({ mode: "edit", id: m.id }))}
                  onPin={() => upd(m.id, m.pinned ? { pinned: false, pinnedAt: undefined } : { pinned: true, pinnedAt: Date.now() })}
                  onAi={() => (m.ai ? upd(m.id, { ai: false }) : startAi(m))} />
                {sel && <button data-pick={m.id} aria-label={`${m.title} 선택`} aria-pressed={sel.has(m.id)} onClick={() => toggleSel(m)} className={cx("absolute inset-0 z-20 rounded-[16px_16px_0px_16px] transition-colors", sel.has(m.id) ? "shadow-[inset_0_0_0_2.5px_#111]" : "hover:bg-black/[.03]")}><span className="absolute bottom-3 left-3"><Pick on={sel.has(m.id)} /></span></button>}
                {!sel && <button aria-label="메모 메뉴" data-memo-menu={m.id} onClick={(e) => { e.stopPropagation(); const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); setMenu({ m, at: { x: r.left, y: r.bottom + 6 } }); }} className="absolute bottom-2 left-3 z-10 grid h-7 w-7 place-items-center rounded-[8px] text-[#4a4a55] opacity-0 transition-opacity hover:bg-white/60 focus-visible:opacity-100 [div:hover>&]:opacity-100"><Dots /></button>}
              </div>
            ))}
            {ci === 0 && hasCheck && filter === "all" && <ChecklistCard code={s.code} onOpen={() => setDlg({ mode: "new", tab: "check" })} />}
          </div>
        ))}
      </div>
      </div>
      {!dlg && !overlay && !sel && <NewMemoFab onClick={() => setDlg({ mode: "new", tab: "memo" })} />}
      {sel && (() => { const list = mine.filter((m) => sel.has(m.id)); return <SelectBar n={sel.size} total={shown.length} all={sel.size === shown.length && shown.length > 0} onAll={() => setSel(sel.size === shown.length ? new Set() : new Set(shown.map((m) => m.id)))} onPin={() => { act.pin(list, true); setSel(null); }} onCopy={() => { act.copy(list); setSel(null); }} onTrash={() => { act.trash(list); setSel(null); }} onEnd={() => setSel(null)} />; })()}
      <CtxMenu at={menu?.at ?? null} items={menu ? act.menu(menu.m, { open: () => setDlg({ mode: "edit", id: menu.m.id }), select: () => setSel(new Set([menu.m.id])) }) : []} onClose={() => setMenu(null)} />
      <ConnectDialog memo={connect} onClose={() => { if (connect?.isNew) snack("일반 메모로 저장했어요 · AI 연결은 나중에 켤 수 있어요"); setConnect(null); }}
        onDone={(items) => { if (connect && x.first) setX((v) => ({ ...v, firstStep: 2 })); if (connect) { const m = memos.find((x) => x.id === connect.id); if (m) upd(m.id, aiOn(m, items)); snack(`AI 연결을 켰어요 · ${items.length}개 항목`, { check: true }); } setConnect(null); }} />
      <MemoDialog open={!!open} memo={open} name={s.name} onClose={(seen) => { if (open && seen && open.badge) upd(open.id, { badge: 0 }); setDlg(null); }}
        onSave={(p) => { if (open) { const changed = (p.title !== undefined && p.title !== open.title) || (p.body !== undefined && p.body !== open.body); if (changed) p.timeline = [...(p.timeline ?? open.timeline ?? firstOnly(open)), { kind: "edit", date: "11월 16일", old: { when: `11월 16일 · 고치기 전`, title: open.title, body: open.body.replace(/\n/g, " ") } }]; upd(open.id, p); if (changed) snack("저장했어요 · 수정 이력에 1개 추가", { check: true }); } setDlg(null); }}
        onMenu={(at) => open && setMenu({ m: open, at })} onConnect={(t) => open && setConnect({ id: open.id, ...t })}
        onNudge={() => { if (open?.badge) upd(open.id, { badge: 0 }); setDlg(null); hideNudge("memo"); studioOpen.report([s.code]); }} />
      <NewDialog code={s.code} open={dlg?.mode === "new"} tab0={dlg?.mode === "new" ? dlg.tab : "memo"} init={dlg?.mode === "new" ? dlg.init : undefined} name={s.name} onClose={() => setDlg(null)}
        onSave={(m) => {
          const id = Date.now();
          const wantAi = m.ai; const base = wantAi ? { ...m, ai: false, tracks: undefined, timeline: undefined } : m;
          setMemos((a) => { const i = a.findIndex((x) => x.code === s.code && (x.col ?? 0) === 0 && !x.pinned); const n: Memo = { ...base, id, code: s.code, date: API_MODE ? mmdd(new Date().toISOString()) : "11.16", badge: 0, col: 0, pinned: false }; const b = a.slice(); b.splice(i < 0 ? a.length : i, 0, n); return b; });
          setFresh(id); window.setTimeout(() => setFresh(null), 1600); setDlg(null);
          if (x.first) setX((v) => ({ ...v, firstStep: Math.max(v.firstStep, 1) }));
          if (wantAi) window.setTimeout(() => setConnect({ id, title: m.title, body: m.body, isNew: true }), 380); else snack("메모를 저장했어요", { check: true });
        }} />
    </div>
  );
}
const firstOnly = (m: Memo): TL[] => { const [mm, dd] = m.date.split("."); return [{ kind: "first", date: m.date, old: { when: `${+mm}월 ${+dd}일 · 처음 작성한 메모`, title: m.title, body: m.body.replace(/\n/g, " ") } }]; };

/* ---------- 팝업 공통 부품 ---------- */
function Toggle45({ on, set }: { on: boolean; set: (v: boolean) => void }) {
  return (
    <button role="switch" aria-checked={on} aria-label="AI 연결" onClick={() => set(!on)} className="relative h-[25px] w-[45px] shrink-0 rounded-[12.5px] transition-colors"
      style={on ? { background: "#14171c" } : { background: "#e5e7eb", boxShadow: "inset 0 0 0 1.25px #14171c, inset 0 1.25px 2.5px rgba(0,0,0,0.12)" }}>
      <span className="absolute top-[2.5px] flex h-5 w-5 items-center justify-center rounded-full bg-white" style={{ left: on ? 22.5 : 2.5, boxShadow: on ? undefined : "0px 1.88px 4.38px -1.25px rgba(0,0,0,0.28)", transition: "left calc(.3s * var(--k)) var(--spring)" }}>
        {on ? <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2.29163 5.20801L4.16663 7.08301L7.70829 3.33301" stroke="#14171C" strokeWidth="1.66667" strokeLinecap="round" strokeLinejoin="round" /></svg>
          : <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M3.125 3.125L6.875 6.875M6.875 3.125L3.125 6.875" stroke="#9AA3B2" strokeWidth="1.66667" strokeLinecap="round" /></svg>}
      </span>
    </button>
  );
}
const AI_OFF = "켜 두면 하루 한 번 공시·뉴스를 대신 확인해 여기에 붙여 드려요.";
function AiFooter({ on, set, sub }: { on: boolean; set: (v: boolean) => void; sub: string }) {
  return (
    <div className="flex h-[108px] w-[680px] shrink-0 flex-col items-start px-6 py-3">
      <div data-coach="ai" className="flex h-[84px] w-[632px] flex-col items-start justify-center gap-2 rounded-[12px] bg-[#f2f3f4] px-4 py-2">
        <div className="flex h-10 w-[560px] items-center gap-3">
          <div className="flex min-w-0 flex-1 flex-col items-start">
            <p className="whitespace-nowrap text-[17px] font-medium leading-[26px] text-[#15171a]">AI 연결</p>
            <p className="w-full text-[14px] font-medium leading-[21px]" style={{ color: on ? "#57535f" : "#4e5968" }}>{sub}</p>
          </div>
          <Toggle45 on={on} set={set} />
        </div>
      </div>
    </div>
  );
}
function Actions({ note, ok, onCancel, onOk, pl = 40 }: { note: string; ok: string; onCancel: () => void; onOk: () => void; pl?: number }) {
  return (
    <div className="flex w-full shrink-0 items-center gap-2 pb-6 pr-6 pt-1" style={{ paddingLeft: pl }}>
      <p className="min-w-0 flex-1 text-[13px] font-medium leading-[20px] text-[#747d8d]">{note}</p>
      <button onClick={onCancel} className="flex h-11 items-center justify-center rounded-[12px] bg-[#f2f3f4] px-[18px] text-[15px] font-medium leading-[23px] text-[#15171a] hover:bg-[#e9eaec]">취소</button>
      <button onClick={onOk} className="flex h-11 items-center justify-center rounded-[12px] bg-[#14171c] px-6 text-[15px] font-medium leading-[23px] text-white">{ok}</button>
    </div>
  );
}
function Tabs2({ a, b, v, set }: { a: string; b: string; v: 0 | 1; set: (i: 0 | 1) => void }) {
  return (
    <div className="flex h-[60px] w-[680px] shrink-0 flex-col items-start px-6 pb-3">
      <div className="relative flex h-12 w-[632px] items-start gap-1 rounded-[14px] bg-[#f2f3f4] p-1">
        <span className="m-pill absolute left-1 top-1 h-10 w-[310px] rounded-[12px] bg-white" style={{ transform: `translateX(${v * 314}px)` }} />
        {[a, b].map((t, i) => <button key={t} onClick={() => set(i as 0 | 1)} className={cx("relative flex h-10 min-w-0 flex-1 items-center justify-center rounded-[12px] text-center text-[15px] font-medium leading-[23px] text-[#15171a]", TR)}>{t}</button>)}
      </div>
    </div>
  );
}
function Close({ onClick }: { onClick: () => void }) {
  return <button aria-label="닫기" onClick={onClick} className={cx("flex h-8 w-8 shrink-0 items-center justify-center rounded-[12px] text-[26px] font-medium leading-[35px] text-[#15171a] hover:bg-[#f2f3f4]", TR)}>×</button>;
}
function Swatches({ v, set }: { v: ColorKey; set: (c: ColorKey) => void }) {
  return (
    <div className="flex h-11 w-[632px] shrink-0 items-center gap-3">
      <p className="w-[76px] text-[13px] font-medium leading-[20px] text-[#4e5968]">메모 색상</p>
      <div className="flex h-9 w-[210px] items-center gap-2">
        {COLORS.map((c) => <button key={c} aria-label={PAPER[c].label} aria-pressed={v === c} onClick={() => set(c)} className={cx("flex h-[34px] w-[34px] items-center justify-center rounded-full", TR)} style={{ background: PAPER[c].bg, boxShadow: v === c ? "inset 0 0 0 1.5px #15171a" : undefined }}>{v === c && <span className="m-pop w-[22px] text-center text-[15px] font-medium leading-[23px] text-[#15171a]">✓</span>}</button>)}
      </div>
      <p className="w-[210px] text-[13px] font-medium leading-[20px] text-[#747d8d]">보기·수정 칸에 같은 색상</p>
    </div>
  );
}

/* 첫 줄 = 제목 (한 칸 편집) */
const esc = (t: string) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
function PaperEditor({ init, color, onEmpty, autoFocus, edRef }: { init: string; color: ColorKey; onEmpty?: (e: boolean) => void; autoFocus?: boolean; edRef: React.MutableRefObject<HTMLDivElement | null> }) {
  useLayoutEffect(() => {
    const el = edRef.current; if (!el) return;
    el.innerHTML = init ? init.split("\n").map((l) => `<div>${esc(l) || "<br>"}</div>`).join("") : "<div><br></div>";
    if (autoFocus) { el.focus(); const r = document.createRange(); r.selectNodeContents(el); r.collapse(!init); const s = getSelection(); s?.removeAllRanges(); s?.addRange(r); }
  }, []); // eslint-disable-line
  const fix = () => {
    const el = edRef.current; if (!el) return;
    const f = el.firstChild;
    if (f && f.nodeName !== "DIV") {
      const sel = getSelection(), an = sel?.anchorNode, ao = sel?.anchorOffset ?? 0;
      const d = document.createElement("div");
      while (el.firstChild && el.firstChild.nodeName !== "DIV") d.appendChild(el.firstChild);
      el.insertBefore(d, el.firstChild);
      if (an && sel) sel.collapse(an, ao);
    }
    if (!el.firstChild) el.innerHTML = "<div><br></div>";
    onEmpty?.(!el.innerText.trim());
  };
  return (
    <div ref={edRef} contentEditable suppressContentEditableWarning spellCheck={false} onInput={fix} aria-label="메모 (첫 줄은 제목)" role="textbox" aria-multiline
      onPaste={(e) => { e.preventDefault(); document.execCommand("insertText", false, e.clipboardData.getData("text/plain")); }}
      className="memo-ed relative min-h-full w-full whitespace-pre-wrap break-words outline-none caret-[#15171a]" data-color={color} />
  );
}
const readEditor = (el: HTMLDivElement | null) => {
  const lines = (el?.innerText ?? "").replace(/ /g, " ").replace(/\n{2,}/g, (m) => "\n".repeat(Math.ceil(m.length / 2))).split("\n");
  const title = (lines[0] ?? "").trim();
  const body = lines.slice(1).join("\n").replace(/^\n+|\n+$/g, "").trim();
  return { title, body };
};

/* ---------- AI 업데이트 타임라인 ---------- */
const KIND = {
  뉴스: { bg: "#e3edff", bar: "#3d73f0", icon: <><path d="M2.25 8.25L13.5 4.5V13.5L2.25 10.5V8.25Z" stroke="#3D73F0" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /><path d="M8.6998 12.6004C8.621 12.886 8.48672 13.1533 8.30462 13.3871C8.12253 13.6208 7.89617 13.8164 7.63849 13.9626C7.38081 14.1089 7.09684 14.2029 6.80281 14.2394C6.50877 14.2759 6.21042 14.2542 5.9248 14.1754C5.63917 14.0966 5.37186 13.9623 5.13813 13.7802C4.9044 13.5981 4.70883 13.3718 4.56257 13.1141C4.41632 12.8564 4.32226 12.5724 4.28575 12.2784C4.24924 11.9844 4.271 11.686 4.3498 11.4004" stroke="#3D73F0" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /><path d="M15.75 6.75V11.25" stroke="#3D73F0" strokeWidth="1.5" strokeLinecap="round" /></> },
  주가: { bg: "#fff1d6", bar: "#c98a0b", icon: <g stroke="#C98A0B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 11.5V14.625" /><path d="M11.5 10.6494V14.625" /><path d="M14 8.16016V14.6252" /><path d="M15.25 3.375L9.84625 8.77875C9.81722 8.80785 9.78274 8.83094 9.74477 8.8467C9.70681 8.86245 9.6661 8.87056 9.625 8.87056C9.5839 8.87056 9.54319 8.86245 9.50523 8.8467C9.46726 8.83094 9.43278 8.80785 9.40375 8.77875L7.34625 6.72125C7.28765 6.66267 7.20818 6.62975 7.12531 6.62975C7.04245 6.62975 6.96298 6.66267 6.90438 6.72125L2.75 10.875" /><path d="M4 13.0391V14.6247" /><path d="M6.5 10.6602V14.6252" /></g> },
  공시: { bg: "#eee8ff", bar: "#7046f5", icon: <g stroke="#7046F5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5.25 15.25C4.91848 15.25 4.60054 15.1183 4.36612 14.8839C4.1317 14.6495 4 14.3315 4 14V4C4 3.66848 4.1317 3.35054 4.36612 3.11612C4.60054 2.8817 4.91848 2.75 5.25 2.75H10.25C10.4478 2.74968 10.6438 2.7885 10.8266 2.86423C11.0094 2.93996 11.1754 3.0511 11.315 3.19125L13.5575 5.43375C13.698 5.57344 13.8095 5.73959 13.8854 5.9226C13.9614 6.10561 14.0003 6.30186 14 6.5V14C14 14.3315 13.8683 14.6495 13.6339 14.8839C13.3995 15.1183 13.0815 15.25 12.75 15.25H5.25Z" /><path d="M10.25 2.75V5.875C10.25 6.04076 10.3158 6.19973 10.4331 6.31694C10.5503 6.43415 10.7092 6.5 10.875 6.5H14" /><path d="M7.75 7.125H6.5" /><path d="M11.5 9.625H6.5" /><path d="M11.5 12.125H6.5" /></g> },
} as const;
const Chev = ({ up }: { up?: boolean }) => <svg className="shrink-0 transition-transform" style={{ transform: up ? "rotate(180deg)" : undefined, transitionDuration: "calc(.25s * var(--k))" }} width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M4.08398 5.54199L7.00065 8.45866L9.91732 5.54199" stroke="#575B63" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
const Grow = ({ on, children }: { on: boolean; children: ReactNode }) => <div className={cx("grid w-full transition-[grid-template-rows]", on ? "grid-rows-[1fr]" : "grid-rows-[0fr]")} style={{ transitionDuration: "calc(.3s * var(--k))" }}><div className="min-h-0 overflow-hidden">{children}</div></div>;
function Feed({ m, onNudge }: { m: Memo; onNudge?: () => void }) {
  const { nudgeOff, hideNudge, coach } = useApp();
  const [open, setOpen] = useState<Set<number>>(new Set());
  const firsts = m.timeline?.filter((x) => x.kind === "first") ?? [];
  const tl = m.ai ? (m.timeline ?? firstOnly(m)) : (firsts.length ? firsts : firstOnly(m));
  const n = m.ai ? tl.filter((x) => x.kind in KIND).length : 0;
  const tog = (i: number) => setOpen((s) => { const t = new Set(s); if (t.has(i)) t.delete(i); else t.add(i); return t; });
  return (
    <div className="flex w-full flex-col items-start gap-4">
      {/* v2: 처음 생각 → 그 뒤 나온 소식 (판단이 이어지는 흐름을 한 줄로) */}
      {m.ai && (
        <div data-thread className="flex w-[632px] items-center gap-3 rounded-[14px] bg-[#f7f8fa] px-4 py-3">
          <span className="dk-keep h-9 w-9 shrink-0 rounded-[9px_9px_0px_9px]" style={{ background: PAPER[m.color].bg }} />
          <div className="flex min-w-0 flex-1 flex-col items-start">
            <p className="whitespace-nowrap text-[13px] font-medium leading-[20px] text-[#747d8d]">처음 생각 · {firsts[0]?.date ?? m.date}</p>
            <p className="w-full truncate text-[15px] font-bold leading-[23px] text-[#15171a]">{firsts[0]?.old?.title ?? m.title}</p>
          </div>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" className="shrink-0"><path d="M4 10H16M11 5L16 10L11 15" stroke="#9AA3B2" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <div className="flex shrink-0 flex-col items-end">
            <p className="whitespace-nowrap text-[13px] font-medium leading-[20px] text-[#747d8d]">그 뒤 도착한 소식</p>
            <p className="whitespace-nowrap text-[15px] font-bold leading-[23px] text-[#15171a]">{n}건</p>
          </div>
        </div>
      )}
      <div className="flex w-[632px] items-center gap-2">
        <p className="w-20 text-[17px] font-bold leading-[26px] text-[#15171a]">도착한 소식</p>
        <p className="w-3 text-[17px] font-bold leading-[26px] text-[#15171a]">{n}</p>
        <p className="w-[484px] text-right text-[13px] font-medium leading-[20px] text-[#575b63]">최신순</p>
      </div>
      {m.ai && n === 0 && (
        <div data-feed-empty className="flex w-[632px] flex-col items-center gap-2 rounded-[16px] bg-[#f7f8fa] px-6 py-6 text-center">
          <p className="text-[17px] font-bold leading-[26px] text-[#15171a]">아직 도착한 소식이 없어요</p>
          <p className="break-keep text-[14px] leading-[21px] text-[#747d8d]">추적 중인 항목과 관련된 공시·뉴스·종가 변화가 생기면 여기에 모아 드려요.</p>
          {m.tracks && <div className="mt-1 flex flex-wrap justify-center gap-[6px]">{m.tracks.split(" · ").map((t) => <span key={t} className="rounded-full bg-white px-3 py-1 text-[13px] font-bold text-[#333d4b] shadow-[inset_0_0_0_1px_#e5e7eb]">{t}</span>)}</div>}
        </div>
      )}
      <div className="flex w-[632px] flex-col items-start gap-2">
        {tl.filter((x) => m.ai || x.kind === "first").map((x, i) => {
          if (x.kind === "start") return (
            <div key={i} className="flex w-[632px] items-center gap-8 pb-1 pl-6 pt-1"><span className="h-1 w-1 shrink-0 rounded-full bg-[#747d8d]" /><p className="w-[570px] text-[13px] font-medium leading-[20px] text-[#575b63]">{x.date} · AI 연결 시작</p></div>
          );
          if (x.kind === "edit" || x.kind === "first") { const o = open.has(i); return (
            <div key={i} className="flex w-full flex-col items-start">
              <button onClick={() => tog(i)} aria-expanded={o} className="flex w-[632px] items-center gap-3 rounded-[12px] px-4 py-3 text-left hover:bg-[#f9f9f9]">
                <span className="flex h-[22px] w-8 shrink-0 items-center justify-center rounded-[8px] bg-[#f2f3f4]">
                  {x.kind === "edit"
                    ? <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#575B63" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M8 3H4.11111C3.81643 3 3.53381 3.11706 3.32544 3.32544C3.11706 3.53381 3 3.81643 3 4.11111V11.8889C3 12.1836 3.11706 12.4662 3.32544 12.6746C3.53381 12.8829 3.81643 13 4.11111 13H11.8889C12.1836 13 12.4662 12.8829 12.6746 12.6746C12.8829 12.4662 13 12.1836 13 11.8889V8" /><path d="M11.5415 2.79147C11.7625 2.57045 12.0623 2.44629 12.3748 2.44629C12.6874 2.44629 12.9872 2.57045 13.2082 2.79147C13.4292 3.01248 13.5533 3.31224 13.5533 3.6248C13.5533 3.93736 13.4292 4.23712 13.2082 4.45813L8.20095 9.46591C8.06903 9.59772 7.90606 9.6942 7.72706 9.74647L6.13095 10.2131C6.08314 10.2271 6.03247 10.2279 5.98423 10.2156C5.93599 10.2032 5.89196 10.1781 5.85675 10.1429C5.82154 10.1077 5.79644 10.0636 5.78408 10.0154C5.77172 9.96717 5.77256 9.91649 5.7865 9.86869L6.25317 8.27258C6.30568 8.09372 6.40235 7.93094 6.53428 7.79925L11.5415 2.79147Z" /></svg>
                    : <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#575B63" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 6.33334C13.0004 6.15729 12.966 5.98289 12.8987 5.82022C12.8314 5.65755 12.7325 5.50982 12.6078 5.38556L10.6144 3.39223C10.4902 3.26752 10.3425 3.16865 10.1798 3.10133C10.0171 3.03401 9.84272 2.99957 9.66667 3H4.11111C3.81643 3 3.53381 3.11707 3.32544 3.32544C3.11706 3.53381 3 3.81643 3 4.11112V11.8889C3 12.1836 3.11706 12.4662 3.32544 12.6746C3.53381 12.8829 3.81643 13 4.11111 13H11.8889C12.1836 13 12.4662 12.8829 12.6746 12.6746C12.8829 12.4662 13 12.1836 13 11.8889V6.33334Z" /><path d="M9.66602 3V5.77778C9.66602 5.92512 9.72455 6.06643 9.82873 6.17061C9.93292 6.2748 10.0742 6.33333 10.2216 6.33333H12.9993" /></svg>}
                </span>
                <p className="w-[490px] text-[14px] leading-[21px] text-[#575b63]">{x.date} · {x.kind === "edit" ? "메모를 수정했어요" : "첫 메모를 남겼어요"}</p>
                <Chev up={o} />
              </button>
              {x.old && <Grow on={o}>
                <div className="flex w-[632px] flex-col items-start pb-3 pl-[60px] pr-4">
                  <div className="flex w-[516px] flex-col items-start gap-1 rounded-[12px] px-4 py-3" style={{ background: PAPER[m.color].bg }}>
                    <p className="w-[484px] text-[13px] font-medium leading-[20px] text-[#575b63]">{x.old.when}</p>
                    <p className="w-[484px] text-[14px] leading-[21px] text-[#15171a]">{x.old.title}</p>
                    <p className="w-[484px] text-[14px] leading-[21px] text-[#575b63]">{x.old.body}</p>
                  </div>
                </div>
              </Grow>}
            </div>
          ); }
          const K = KIND[x.kind as keyof typeof KIND], o = open.has(i);
          return (
            <div key={i} className="relative flex w-full flex-col items-start overflow-hidden rounded-[16px]" style={{ background: K.bg }}>
              <button onClick={() => tog(i)} aria-expanded={o} className="flex w-[632px] items-center gap-3 p-4 text-left">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-white"><svg width="18" height="18" viewBox="0 0 18 18" fill="none">{K.icon}</svg></span>
                <span className="flex w-[440px] flex-col items-start gap-1">
                  <span className="w-[440px] text-[13px] font-medium leading-[20px] text-[#575b63]">{x.kind} · {x.date}</span>
                  <span className="w-[440px] text-[17px] font-bold leading-[26px] text-[#15171a]">{x.title}</span>
                </span>
                <span className="flex w-16 shrink-0 items-center justify-end gap-1"><span className="w-10 text-[13px] font-medium leading-[20px] text-[#575b63]">{o ? "접기" : "자세히"}</span><Chev up={o} /></span>
              </button>
              <Grow on={o}>
                <div className="flex w-[632px] flex-col items-start gap-3 pb-5 pl-[60px] pr-5">
                  <p className="w-[512px] text-[14px] leading-[21px] text-[#575b63]">{x.body}</p>
                  <div className="flex w-[512px] items-start gap-2 rounded-[12px] px-3 py-[10px]" style={{ background: PAPER[m.color].bg }}><span className="shrink-0 text-[13px] font-bold leading-[20px] text-[#575b63]">연결된 내 메모</span><span className="min-w-0 flex-1 truncate text-[13px] font-medium leading-[20px] text-[#15171a]">{m.title}</span></div>
                  <div className="flex w-[512px] items-end justify-between gap-3 border-t border-[#e8ecf3] pt-3"><p className="min-w-0 flex-1 whitespace-pre-line text-[13px] font-medium leading-[20px] text-[#575b63]">{x.src}</p>{x.kind === "뉴스" || x.kind === "공시" ? <a href={x.kind === "공시" ? "https://dart.fss.or.kr" : "https://www.hankyung.com"} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="shrink-0 text-[13px] font-bold leading-[20px] text-[#15171a] underline underline-offset-2">원문 열기 ↗</a> : null}</div>
                </div>
              </Grow>
              <span className="absolute left-0 top-[18px] h-10 w-[3px] rounded-[1.5px]" style={{ background: K.bar }} />
            </div>
          );
        })}
      </div>
      {/* v2 넛지: 소식이 2개 이상 붙은 메모에서 주간보고서로 */}
      {m.ai && n >= 2 && onNudge && !nudgeOff.memo && !coach && (
        <div data-nudge="memo" className="u252-pl relative flex h-12 w-[632px] shrink-0 items-center rounded-[14px] bg-[#15171a]">
          <button onClick={onNudge} className="u252-go flex h-12 min-w-0 flex-1 items-center gap-2 rounded-l-[14px] pl-4 pr-3 text-left">
            <Spark />
            <span className="min-w-0 flex-1 truncate text-[15px] font-bold leading-[23px] text-white">이 메모에 붙은 소식, 한 번에 정리해 드릴까요?</span>
            <Arrow />
          </button>
          <span className="h-5 w-px shrink-0 bg-white/20" />
          <button aria-label="제안 닫기" title="닫기" onClick={() => hideNudge("memo")} className="grid h-12 w-11 shrink-0 place-items-center rounded-r-[14px] hover:bg-white/10"><Cross /></button>
        </div>
      )}
      {m.ai && (
        <div className="flex w-[632px] items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#747D8D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0"><path d="M6.52212 2.53455C6.54295 2.42304 6.60212 2.32233 6.68939 2.24985C6.77666 2.17737 6.88653 2.1377 6.99997 2.1377C7.11341 2.1377 7.22328 2.17737 7.31055 2.24985C7.39782 2.32233 7.45699 2.42304 7.47782 2.53455L7.98872 5.23636C8.02501 5.42845 8.11835 5.60513 8.25658 5.74336C8.39481 5.88159 8.5715 5.97493 8.76358 6.01122L11.4654 6.52212C11.5769 6.54295 11.6776 6.60212 11.7501 6.68939C11.8226 6.77666 11.8622 6.88653 11.8622 6.99997C11.8622 7.11341 11.8226 7.22328 11.7501 7.31055C11.6776 7.39782 11.5769 7.45699 11.4654 7.47782L8.76358 7.98872C8.5715 8.02501 8.39481 8.11835 8.25658 8.25658C8.11835 8.39481 8.02501 8.5715 7.98872 8.76358L7.47782 11.4654C7.45699 11.5769 7.39782 11.6776 7.31055 11.7501C7.22328 11.8226 7.11341 11.8622 6.99997 11.8622C6.88653 11.8622 6.77666 11.8226 6.68939 11.7501C6.60212 11.6776 6.54295 11.5769 6.52212 11.4654L6.01122 8.76358C5.97493 8.5715 5.88159 8.39481 5.74336 8.25658C5.60513 8.11835 5.42845 8.02501 5.23636 7.98872L2.53455 7.47782C2.42304 7.45699 2.32233 7.39782 2.24985 7.31055C2.17737 7.22328 2.1377 7.11341 2.1377 6.99997C2.1377 6.88653 2.17737 6.77666 2.24985 6.68939C2.32233 6.60212 2.42304 6.54295 2.53455 6.52212L5.23636 6.01122C5.42845 5.97493 5.60513 5.88159 5.74336 5.74336C5.88159 5.60513 5.97493 5.42845 6.01122 5.23636L6.52212 2.53455Z" /><path d="M10.8896 2.13965V4.08409" /><path d="M11.8614 3.11133H9.91699" /><path d="M3.11187 11.8614C3.64881 11.8614 4.08409 11.4262 4.08409 10.8892C4.08409 10.3523 3.64881 9.91699 3.11187 9.91699C2.57493 9.91699 2.13965 10.3523 2.13965 10.8892C2.13965 11.4262 2.57493 11.8614 3.11187 11.8614Z" /></svg>
          <p className="w-[570px] text-[13px] font-medium leading-[20px] text-[#575b63]">뉴스·공시는 AI가 요약했어요. 자세히에서 출처를 볼 수 있어요.</p>
        </div>
      )}
      {m.ai && <Disclaimer className="!text-left" />}
    </div>
  );
}

const PANEL = "flex max-h-[calc(100vh-32px)] w-[680px] flex-col items-start overflow-hidden rounded-[30px] bg-white shadow-[inset_0_0_0_1px_#e8ecf3,0px_24px_60px_-16px_rgba(110,99,150,0.16)]";
const trackCount = (t?: string) => (t ?? "").split("·").map((x) => parseInt(x.replace(/\D/g, "")) || 0).reduce((a, b) => a + b, 0) || 1;

/* ---------- 메모 팝업 (내 메모 · 메모 / AI 업데이트) ---------- */
function MemoDialog({ open, memo, name, onClose, onSave, onNudge, onMenu, onConnect }: { open: boolean; memo?: Memo; name: string; onClose: (seenAi: boolean) => void; onSave: (p: Partial<Memo>) => void; onNudge?: () => void; onMenu?: (at: { x: number; y: number }) => void; onConnect?: (t: { title: string; body: string }) => void }) {
  const { coach, x, setX, studio } = useApp();
  const last = useRef<Memo | undefined>(memo); if (memo) last.current = memo;
  const m = memo ?? last.current;
  const [tab, setTab] = useState<0 | 1>(0), [color, setColor] = useState<ColorKey>(m?.color ?? "yellow"), [ai, setAi] = useState(!!m?.ai);
  const seen = useRef(false);
  const ed = useRef<HTMLDivElement | null>(null);
  useEffect(() => { if (memo) { setTab(0); setColor(memo.color); setAi(memo.ai); seen.current = false; } }, [memo?.id]); // eslint-disable-line
  useEffect(() => { if (coach?.step === 2 && memo) setTab(1); }, [coach?.step, memo?.id]); // eslint-disable-line -- v2 코치마크 ③: AI 업데이트 탭을 보여 줌
  useEffect(() => { if (memo && x.memoTab === 1) { setTab(1); seen.current = true; setX((v) => ({ ...v, memoTab: 0 })); } }, [memo?.id, x.memoTab]); // eslint-disable-line -- 알림함에서 열면 AI 업데이트 탭
  useEffect(() => { if (memo) setAi(memo.ai); }, [memo?.ai]); // eslint-disable-line -- AI 연결 창에서 켜면 같이 바뀜
  if (!m) return null;
  const [mm, dd] = m.date.split(".");
  const close = () => onClose(seen.current);
  const save = () => {
    const r = readEditor(ed.current);
    const p: Partial<Memo> = { color, ai, title: r.title || m.title, body: r.title ? r.body : m.body };
    if (ai && !m.ai) { p.tracks = m.tracks ?? "공시·뉴스 1개"; p.timeline = m.timeline?.some((x) => x.kind === "start") ? m.timeline : [...(m.timeline ?? firstOnly(m)), { kind: "start", date: "11월 12일" }]; }
    if (seen.current) p.badge = 0;
    onSave(p);
  };
  const view = { ...m, ai, color };
  return (
    <Modal open={open} onClose={close} width={680} scrim="rgba(14,15,20,0.32)" label="내 메모">
      <div className={PANEL}>
        <div className="flex h-24 w-[680px] shrink-0 items-start gap-3 pb-[13px] pl-6 pr-6 pt-5">
          <div className="flex min-w-0 flex-1 flex-col items-start gap-[13px]">
            <p className="w-[588px] text-[13px] font-medium leading-[20px] text-[#747d8d]">{name} · 2026. {mm}. {dd} 작성</p>
            <p className="w-[588px] text-[26px] font-bold leading-[35px] text-[#15171a]">내 메모</p>
          </div>
          {onMenu && <button aria-label="메모 메뉴" data-dlg-menu onClick={(e) => { const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); onMenu({ x: r.right - 220, y: r.bottom + 6 }); }} className="mr-[-4px] grid h-8 w-8 shrink-0 place-items-center rounded-[12px] text-[#15171a] hover:bg-[#f2f3f4]"><Dots /></button>}
          <Close onClick={close} />
        </div>
        <Tabs2 a="메모" b="AI 업데이트" v={tab} set={(i) => { setTab(i); if (i === 1) seen.current = true; }} />
        <div data-coach={tab === 1 ? "feed" : undefined} className={cx("w-[680px] min-h-0 shrink overflow-y-auto pb-4 pl-6 pr-6 pt-2", tab === 0 ? "h-[348px] shrink-0" : "flex-1")}>
          <div className={cx("flex w-[632px] flex-col items-start gap-[13px]", tab !== 0 && "hidden")}>
            <div className="h-[277px] w-[632px] shrink-0 overflow-y-auto rounded-[16px] p-5 transition-colors" style={{ background: PAPER[color].bg, transitionDuration: "calc(.3s * var(--k))" }}>
              <PaperEditor key={m.id} init={m.title + (m.body ? "\n" + m.body : "")} color={color} edRef={ed} />
            </div>
            <Swatches v={color} set={setColor} />
          </div>
          {tab === 1 && <div className="m-in flex flex-col gap-4">{studio.creditOut && m.ai && <SpentBox title="AI 연결이 잠시 멈췄어요" sub={"이번 달 AI 사용량을 다 썼어요. 12월 1일에 다시 찾아요.\n메모는 계속 쓸 수 있어요."} />}<Feed m={view} onNudge={onNudge} /></div>}
        </div>
        <AiFooter on={ai} set={(v) => { if (v && !m.ai && onConnect) { const r = readEditor(ed.current); onConnect({ title: r.title || m.title, body: r.title ? r.body : m.body }); return; } setAi(v); }} sub={ai ? (tab === 1 ? `이 메모를 AI가 지켜보고 있어요 · ${m.tracks ?? "공시·뉴스 1개"}` : `이 메모에서 ${trackCount(m.tracks)}개 항목을 지켜봐요.`) : AI_OFF} />
        <Actions note="연결하지 않아도 메모는 그대로 남아요" ok="메모 저장" onCancel={close} onOk={save} />
      </div>
    </Modal>
  );
}

/* ---------- 6.1 새 메모 · 6.2 체크리스트 ---------- */
function NewDialog({ code, open, tab0, init, name, onClose, onSave }: { code: string; open: boolean; tab0: "memo" | "check"; init?: string; name: string; onClose: () => void; onSave: (m: Omit<Memo, "id" | "code" | "date" | "badge" | "col" | "pinned">) => void }) {
  const { checklist, setChecklist, clTitle, setClTitle } = useChecklist(code);
  const snack = useSnack();
  const [tab, setTab] = useState<0 | 1>(0), [color, setColor] = useState<ColorKey>("yellow"), [ai, setAi] = useState(false), [empty, setEmpty] = useState(true);
  const [items, setItems] = useState(checklist), [title, setTitle] = useState(clTitle), [add, setAdd] = useState("");
  const [nonce, setNonce] = useState(0);
  const ed = useRef<HTMLDivElement | null>(null);
  useEffect(() => { if (open) { setTab(tab0 === "check" ? 1 : 0); setColor("yellow"); setAi(false); setEmpty(!init); setItems(checklist); setTitle(clTitle); setAdd(""); setNonce((n) => n + 1); } }, [open]); // eslint-disable-line
  const save = () => {
    if (tab === 1) { setChecklist(items); setClTitle(title.trim() || "체크리스트"); onClose(); return; }
    const r = readEditor(ed.current); if (!r.title) { snack("빈 메모는 저장하지 않았어요"); ed.current?.focus(); return; }
    onSave({ title: r.title, body: r.body, color, ai, pinnedAt: undefined, tracks: ai ? "공시·뉴스 1개" : undefined, timeline: ai ? [{ kind: "first", date: "11.12", old: { when: "11월 12일 · 처음 작성한 메모", title: r.title, body: r.body.replace(/\n/g, " ") } }, { kind: "start", date: "11월 12일" }] : undefined });
  };
  const done = items.filter((c) => c.d).length;
  return (
    <Modal open={open} onClose={onClose} width={680} label={tab ? "새 체크리스트" : "새 메모"}>
      <div className={PANEL}>
        <div className="flex h-24 w-[680px] shrink-0 items-center gap-3 pb-6 pl-6 pr-6 pt-5">
          <div className="flex min-w-0 flex-1 flex-col items-start gap-1">
            <p className="w-[588px] text-[13px] font-medium leading-[20px] text-[#747d8d]">{name} · 나의 보드</p>
            <p className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#15171a]">{tab ? "새 체크리스트" : "새 메모"}</p>
          </div>
          <Close onClick={onClose} />
        </div>
        <Tabs2 a="메모" b="체크리스트" v={tab} set={setTab} />
        {tab === 0 ? (<>
          <div className="h-[348px] w-[680px] shrink-0 pb-4 pl-6 pr-6 pt-2">
            <div className="flex w-[632px] flex-col items-start gap-[13px]">
              <div className="relative h-[277px] w-[632px] shrink-0 overflow-y-auto rounded-[16px] p-5 transition-colors" style={{ background: PAPER[color].bg, transitionDuration: "calc(.3s * var(--k))" }}>
                {empty && (
                  <div aria-hidden className="pointer-events-none absolute left-5 right-5 top-5 flex flex-col items-start gap-2">
                    <p className="w-full text-[22px] font-bold leading-[31px] text-[#16161c] opacity-30">실적 발표 후 다시 보기</p>
                    <p className="w-full text-[17px] leading-[1.6] text-[#16161c] opacity-[0.32]">다음 분기 보고서에서 순이익이 작년보다 늘었는지 확인하기<br />종가 ○○원 아래로 내려오면 다시 보기</p>
                    <div className="flex w-full flex-col items-start border-t border-dashed border-[rgba(22,22,28,0.18)] pt-[10px]"><p className="w-full break-keep text-[13px] leading-[1.5] text-[#16161c] opacity-[0.38]">투자가 막연하세요? 떠오른 생각 한 줄이면 충분해요.<br />첫 줄은 제목이 돼요. 확인할 것·다시 볼 조건을 적어 두면 AI가 관련 소식을 더 잘 찾아요.</p></div>
                  </div>
                )}
                <PaperEditor key={nonce} init={init ?? ""} color={color} autoFocus onEmpty={setEmpty} edRef={ed} />
              </div>
              <Swatches v={color} set={setColor} />
            </div>
          </div>
          <AiFooter on={ai} set={setAi} sub={ai ? "이 메모에서 1개 항목을 지켜봐요." : AI_OFF} />
          <Actions note="연결하지 않아도 메모는 그대로 남아요" ok="메모 저장" onCancel={onClose} onOk={save} />
        </>) : (<>
          <div className="min-h-0 w-[680px] shrink overflow-y-auto pb-4 pl-6 pr-6 pt-2">
            <div className="m-in flex w-[632px] flex-col items-start gap-3">
              <div className="flex w-full items-center justify-between"><p className="text-[17px] font-bold leading-[26px] text-[#15171a]">체크리스트 제목</p><p className="text-[13px] font-medium leading-[20px] text-[#747d8d]">보드 카드 제목으로 보여요</p></div>
              <input value={title} onChange={(e) => setTitle(e.target.value)} aria-label="체크리스트 제목" className="h-12 w-full rounded-[12px] border border-[#e8ecf3] bg-[#fafbfc] px-4 text-[15px] font-bold leading-[23px] text-[#15171a] outline-none focus:border-[#15171a]" />
              <div className="flex w-full items-center justify-between"><p className="text-[17px] font-bold leading-[26px] text-[#15171a]">확인할 항목</p>
                <div className="flex items-center gap-2"><p className="text-[13px] font-medium leading-[20px] text-[#747d8d]">{done} / {items.length} 완료</p><Ring done={done} n={items.length} track="#E8ECF3" arc="#14171C" text="#747d8d" /></div>
              </div>
              <div className="flex w-full flex-col items-start rounded-[16px] border border-[#e8ecf3] bg-white px-4 py-1">
                {items.map((c, i) => (
                  <div key={i} className="m-in flex h-11 w-full items-center gap-3">
                    <CheckDot on={c.d} onClick={() => setItems((l) => l.map((x, j) => (j === i ? { ...x, d: !x.d } : x)))} off="#d1d6de" fill="#14171c" />
                    <p className={cx("min-w-0 flex-1 truncate text-[15px] leading-[23px] transition-colors", c.d ? "text-[#9aa3b2] line-through" : "text-[#333d4b]")}>{c.t}</p>
                    <button aria-label={`${c.t} 지우기`} onClick={() => setItems((l) => l.filter((_, j) => j !== i))} className="whitespace-nowrap text-[20px] font-medium leading-[29px] text-[#9aa3b2] hover:text-[#15171a]">×</button>
                  </div>
                ))}
                <div className="h-px w-full bg-[#e8ecf3]" />
                <label className="flex h-11 w-full items-center gap-3">
                  <span className="flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[5px] border border-dashed border-[#d1d6de]"><span className="text-[13px] font-medium leading-[20px] text-[#9aa3b2]">+</span></span>
                  <input value={add} onChange={(e) => setAdd(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing && add.trim()) { setItems((l) => [...l, { t: add.trim(), d: false }]); setAdd(""); } }} placeholder="항목 추가 · Enter로 바로 추가" className="min-w-0 flex-1 bg-transparent text-[15px] leading-[23px] text-[#333d4b] outline-none placeholder:text-[#9aa3b2]" />
                </label>
              </div>
            </div>
          </div>
          <div className="flex w-full shrink-0 flex-col items-start px-6 py-3">
            <div className="flex w-full items-center gap-3 rounded-[12px] bg-[#f2f3f4] px-4 py-3">
              <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-[#9aa3b2]"><p className="text-[13px] font-bold leading-[20px] text-[#747d8d]">i</p></div>
              <div className="flex min-w-0 flex-1 flex-col items-start"><p className="whitespace-nowrap text-[17px] font-medium leading-[26px] text-[#15171a]">AI 연결 없음</p><p className="whitespace-nowrap text-[14px] font-medium leading-[21px] text-[#4e5968]">체크리스트는 보드에만 저장되고, 뉴스·공시와 연결되지 않아요.</p></div>
            </div>
          </div>
          <Actions note="저장 후에도 언제든 고칠 수 있어요" ok="체크리스트 저장" onCancel={onClose} onOk={save} pl={24} />
        </>)}
      </div>
    </Modal>
  );
}
