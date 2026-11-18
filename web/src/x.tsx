/* 11.16 앱 통일 — 앱(예빈 모바일 체험판)에 있던 공통 기능을 웹에. 모양은 웹(검정·A안 글자), 움직임은 Lucian 값 그대로(x.css). */
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cx, mainCenter, Modal } from "./kit";
import { useApp, type Notif } from "./store";

/* ---------- 사용량 % (앱과 같이 화면에 %로) ---------- */
export function useUsage() {
  const { ud } = useApp();
  return Math.min(100, Math.round(ud.usage.pct));
}
/* 사용량이 다시 채워지는 날 (예: "12월 1일") */
export function useResetDay() { const { ud } = useApp(); const d = new Date(ud.usage.reset_at); return `${d.getMonth() + 1}월 ${d.getDate()}일`; }

/* ---------- 사용량을 다 썼을 때 안내 상자 (메모 보드 · 메모 상세 · 업데이트 · 스튜디오 공통) ---------- */
export function SpentBox({ title, sub, className }: { title: string; sub: string; className?: string }) {
  const { setStudio, setOverlay, setPlanOpen, openSettings } = useApp();
  return (
    <div data-spent className={cx("m-pop flex w-full flex-col items-start gap-1 rounded-[16px] bg-[#fff4e5] px-5 py-4", className)}>
      <p className="w-full text-[15px] font-bold leading-[23px] text-[#7a4a00]">{title}</p>
      <p className="w-full whitespace-pre-line break-keep text-[14px] leading-[21px] text-[#8a5a00]">{sub}</p>
      <div className="mt-2 flex gap-2">
        <button onClick={() => { setStudio((s) => ({ ...s, open: true })); setOverlay("charge"); }} className="flex h-9 items-center rounded-[10px] bg-[#15171a] px-[14px] text-[14px] font-bold text-white hover:bg-[#2a2a2a]">크레딧 구매</button>
        <button onClick={() => { setPlanOpen(true); openSettings("사용량"); }} className="flex h-9 items-center rounded-[10px] bg-white px-[14px] text-[14px] font-bold text-[#7a4a00] shadow-[inset_0_0_0_1px_#f1d9b3] hover:bg-[#fffaf2]">플랜 변경</button>
      </div>
    </div>
  );
}

/* ---------- 투자 권유가 아니라는 한 줄 ---------- */
export const Disclaimer = ({ className }: { className?: string }) => (
  <p data-disclaimer className={cx("w-full break-keep text-center text-[13px] leading-[20px] text-[#9a9ea7]", className)}>투자 권유가 아닌 참고 정보예요 · AI는 틀릴 수 있어 원문을 꼭 확인해 주세요</p>
);

/* ---------- 인터넷 끊김 띠 (Lucian #091) — 가운데 화면 위쪽 가운데 ---------- */
export function OfflineBand() {
  const { x, nav, sideOpen, studio } = useApp();
  const [left, setLeft] = useState<number | null>(null);
  const [retry, setRetry] = useState(false);
  useEffect(() => {
    let raf = 0; const t0 = performance.now();
    const f = () => { const c = mainCenter(); setLeft((l) => (c === null ? l : l !== null && Math.abs(l - c) < 0.25 ? l : c)); if (performance.now() - t0 < 1400) raf = requestAnimationFrame(f); };
    f(); window.addEventListener("resize", f); return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", f); };
  }, [nav, sideOpen, studio.open, x.offline]);
  useEffect(() => { document.documentElement.dataset.offline = x.offline ? "1" : "0"; }, [x.offline]);
  return (
    <div role="status" aria-live="polite" data-offline={x.offline ? "1" : "0"} className={cx("off-band fixed bottom-7 z-[70] flex items-center gap-3 rounded-[14px] bg-[#2b2d33] py-[10px] pl-[10px] pr-3 text-white shadow-[0_10px_24px_-10px_rgba(0,0,0,.45)]", x.offline && "on")} style={{ left: left ?? "50%" }}>
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-[11px] bg-white/10">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round"><path className="a a3" d="M2 8.5a15 15 0 0 1 20 0" /><path className="a a2" d="M5 12a10 10 0 0 1 14 0" /><path className="a" d="M8.5 15.5a5 5 0 0 1 7 0" /><path d="M3 3l18 18" /></svg>
      </span>
      <span className="flex flex-col"><span className="whitespace-nowrap text-[15px] font-bold leading-[23px]">인터넷 연결이 끊겼어요</span><span className="whitespace-nowrap text-[13px] leading-[20px] text-white/70">받아 둔 내용은 그대로 볼 수 있어요</span></span>
      <button tabIndex={x.offline ? 0 : -1} onClick={() => { setRetry(true); window.setTimeout(() => setRetry(false), 600); }} className={cx("ml-2 h-9 rounded-[10px] px-3 text-[14px] font-bold text-white hover:bg-white/10", retry && "opacity-60")}>다시 시도</button>
    </div>
  );
}

/* ---------- 첫 방문 뼈대 (Lucian #079) — 안의 [data-sk] 카드 자리에 뼈대를 그렸다가 차례로 보여줌. 크기·위치는 그대로 ---------- */
export function SkelPage({ id, children, className }: { id: string; children: ReactNode; className?: string }) {
  const { x, setX } = useApp();
  const [phase, setPhase] = useState<"wait" | "done" | "idle">(() => (x.seen[id] ? "idle" : "wait"));
  const ref = useRef<HTMLDivElement>(null);
  const [boxes, setBoxes] = useState<{ l: number; t: number; w: number; h: number; r: string; d: number }[]>([]);
  useLayoutEffect(() => {
    if (phase !== "wait" || !ref.current) return;
    const host = ref.current, hr = host.getBoundingClientRect(), k = hr.width / (host.offsetWidth || 1);
    const els = [...host.querySelectorAll<HTMLElement>("[data-sk]")];
    els.forEach((e, i) => e.style.setProperty("--d", `calc(${i * 0.07}s * var(--k, 1))`));
    setBoxes(els.map((e, i) => { const r = e.getBoundingClientRect(); return { l: (r.left - hr.left) / k, t: (r.top - hr.top) / k, w: r.width / k, h: r.height / k, r: getComputedStyle(e).borderRadius || "16px", d: i * 0.07 }; }));
    setX((v) => ({ ...v, seen: { ...v.seen, [id]: true } }));
    const kk = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--k")) || 1;
    const t1 = window.setTimeout(() => setPhase("done"), 520 * kk);
    const t2 = window.setTimeout(() => { setPhase("idle"); els.forEach((e) => e.style.removeProperty("--d")); }, (520 + 700 + els.length * 70) * kk);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div ref={ref} data-skel={phase} className={cx("sk-host", phase === "wait" && "sk-wait", phase === "done" && "sk-done", className)}>
      {children}
      {phase !== "idle" && <div aria-hidden className="sk-layer">{boxes.map((b, i) => <span key={i} className="sk-box" style={{ left: b.l, top: b.t, width: b.w, height: b.h, borderRadius: b.r, ["--d" as string]: `calc(${b.d}s * var(--k, 1))` }} />)}</div>}
    </div>
  );
}

/* ---------- 위젯 하나만 실패 (앱: 위젯 안에서만 오류 + 5초 뒤 자동 다시 시도) ---------- */
export function WidgetFail({ what, h }: { what: string; h?: number }) {
  const { setX } = useApp();
  const [n, setN] = useState(5);
  useEffect(() => { const id = window.setInterval(() => setN((v) => { if (v <= 1) { setX((x) => ({ ...x, widgetFail: false })); return 0; } return v - 1; }), 1000); return () => clearInterval(id); }, [setX]);
  return (
    <div data-widget-fail className="m-in flex w-full flex-col items-center justify-center gap-2 rounded-[16px] bg-[#f7f8fa] px-4 text-center" style={{ height: h }}>
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#9aa0aa" strokeWidth="1.8" strokeLinecap="round"><circle cx="12" cy="12" r="9" /><path d="M12 7.5v5.5M12 16.2v.3" /></svg>
      <p className="text-[15px] font-bold leading-[23px] text-[#333d4b]">{what}를 불러오지 못했어요</p>
      <button onClick={() => setX((x) => ({ ...x, widgetFail: false }))} className="h-9 rounded-[10px] bg-white px-3 text-[14px] font-bold text-[#15171a] shadow-[inset_0_0_0_1px_#e5e7eb] hover:bg-[#f9f9f9]">다시 시도 · {n}초 뒤 자동</button>
    </div>
  );
}

/* ---------- ⋯ / 우클릭 메뉴 (Lucian #038) ---------- */
export type MenuItem = { label: string; icon?: ReactNode; danger?: boolean; run: () => void } | "-";
export function CtxMenu({ at, items, onClose }: { at: { x: number; y: number } | null; items: MenuItem[]; onClose: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ x: number; y: number; ox: string } | null>(null);
  useLayoutEffect(() => {
    if (!at) { setOpen(false); return; }
    const w = 220, h = ref.current?.offsetHeight ?? 200;
    const flipX = at.x + w > window.innerWidth - 12, flipY = at.y + h > window.innerHeight - 12;
    setPos({ x: flipX ? at.x - w : at.x, y: flipY ? Math.max(12, at.y - h) : at.y, ox: `${flipX ? "right" : "left"} ${flipY ? "bottom" : "top"}` });
    const r = requestAnimationFrame(() => setOpen(true)); return () => cancelAnimationFrame(r);
  }, [at]);
  useEffect(() => {
    if (!at) return;
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    const d = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) onClose(); };
    window.addEventListener("keydown", k); window.addEventListener("mousedown", d, true); window.addEventListener("resize", onClose);
    return () => { window.removeEventListener("keydown", k); window.removeEventListener("mousedown", d, true); window.removeEventListener("resize", onClose); };
  }, [at, onClose]);
  return createPortal(
    <div ref={ref} role="menu" data-ctx className={cx("u038-menu fixed z-[95] w-[220px] rounded-[14px] border border-[#e5e8eb] bg-white p-1.5 shadow-[0_16px_36px_-12px_rgba(17,17,17,.25)]", open && at && "is-open")} style={{ left: pos?.x ?? -999, top: pos?.y ?? -999, transformOrigin: pos?.ox }}>
      {items.map((it, i) => it === "-" ? <div key={i} className="mx-2 my-1 h-px bg-[#efeff2]" /> : (
        <button key={it.label} role="menuitem" tabIndex={at ? 0 : -1} onClick={() => { onClose(); it.run(); }} className={cx("flex h-10 w-full items-center gap-[10px] rounded-[10px] px-3 text-left text-[15px] font-medium leading-[23px] hover:bg-[#f5f6f8]", it.danger ? "text-[#e5484d]" : "text-[#15171a]")}>
          {it.icon && <span className="grid w-5 shrink-0 place-items-center">{it.icon}</span>}{it.label}
        </button>
      ))}
    </div>, document.body
  );
}
export const MI = {
  pin: <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12.5 2.5l5 5-3 1-3.5 3.5-.5 4-8-8 4-.5L10 4l1-3z" transform="translate(-0.5 0.5)" /><path d="M3 17l4-4" /></svg>,
  trash: <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3.5 5.5h13M8 5.5V3.5h4v2M5 5.5l.8 11h8.4l.8-11" /></svg>,
  copy: <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"><rect x="6.5" y="6.5" width="10" height="10" rx="2" /><path d="M13.5 6.5V4.5a1 1 0 0 0-1-1h-8a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h2" /></svg>,
  share: <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M10 12.5V3M6.5 6.5L10 3l3.5 3.5M4 10.5v5a1.5 1.5 0 0 0 1.5 1.5h9a1.5 1.5 0 0 0 1.5-1.5v-5" /></svg>,
  find: <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><circle cx="9" cy="9" r="5.5" /><path d="M13 13l4 4" /></svg>,
  move: <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M4 7h12M12 3.5L15.5 7 12 10.5M16 13H4M8 16.5L4.5 13 8 9.5" /></svg>,
  info: <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><rect x="3" y="3.5" width="14" height="13" rx="2.5" /><path d="M6.5 13V10M10 13V7.5M13.5 13v-4" /></svg>,
  select: <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="10" cy="10" r="7" /><path d="M7 10.2l2 2 4-4.4" /></svg>,
};

/* ---------- 알림함 (Lucian #074) — 사이드바 종 버튼 + 창 ---------- */
export const BellIcon = ({ size = 20 }: { size?: number }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9.5a6 6 0 0 1 12 0c0 5 2 6.5 2 6.5H4s2-1.5 2-6.5" /><path d="M10 19.5a2 2 0 0 0 4 0" /></svg>;
export function useNotifs() {
  const { notifs, ud } = useApp();
  return { list: notifs, unread: notifs.filter((n) => !n.read).length, allOff: !ud.settings.noti_upd && !ud.settings.noti_studio };
}
export function BellBtn({ rail }: { rail?: boolean }) {
  const { x, setX } = useApp();
  const { unread } = useNotifs();
  const [ring, setRing] = useState(false);
  const prev = useRef(unread);
  useEffect(() => { if (unread > prev.current) { setRing(true); const t = window.setTimeout(() => setRing(false), 950); prev.current = unread; return () => clearTimeout(t); } prev.current = unread; }, [unread]);
  return (
    <button data-bell aria-label={`알림${unread ? ` ${unread}개` : ""}`} title="알림" aria-expanded={x.inbox} onClick={(e) => { e.stopPropagation(); setX((v) => ({ ...v, inbox: !v.inbox })); }}
      className={cx("u074-bell relative grid place-items-center rounded-[8px] text-[#333333]", rail ? "h-10 w-10" : "h-8 w-8", x.inbox ? "bg-[#f3f1ef]" : "hover:bg-[#f9f9f9]", ring && "ring")}>
      <BellIcon />
      <span className={cx("u074-badge absolute -right-1 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full border-2 border-white bg-[#e5484d] px-1 text-[11px] font-bold leading-none text-white", !unread && "zero")}>{unread || ""}</span>
    </button>
  );
}
const NIcon = ({ n }: { n: Notif }) => (
  <span className={cx("grid h-9 w-9 shrink-0 place-items-center rounded-[11px]", n.kind === "upd" ? "bg-[#f1f2f4]" : "bg-[#15171a]")}>
    {n.kind === "upd"
      ? <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="#15171a" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M7.5 3.5v3M12.5 3.5v3M5.5 6.5h9v3a4.5 4.5 0 0 1-9 0z" /><path d="M10 14v3" /></svg>
      : <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M7.33317 2C7.73317 4.86667 9.13317 6.26667 11.9998 6.66667C9.13317 7.06667 7.73317 8.46667 7.33317 11.3333C6.93317 8.46667 5.53317 7.06667 2.6665 6.66667C5.53317 6.26667 6.93317 4.86667 7.33317 2Z" fill="white" /></svg>}
  </span>
);
export function InboxPanel() {
  const { x, setX, sideOpen, go, setMemoOpen, setStudio, sgo, openSettings, act, made } = useApp();
  const { list, unread, allOff } = useNotifs();
  const [tab, setTab] = useState<"all" | "upd" | "studio">("all");
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!x.inbox) return;
    const d = (e: MouseEvent) => { const t = e.target as HTMLElement; if (!ref.current?.contains(t) && !t.closest("[data-bell]")) setX((v) => ({ ...v, inbox: false })); };
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") setX((v) => ({ ...v, inbox: false })); };
    window.addEventListener("mousedown", d); window.addEventListener("keydown", k);
    return () => { window.removeEventListener("mousedown", d); window.removeEventListener("keydown", k); };
  }, [x.inbox, setX]);
  const shown = list.filter((n) => tab === "all" || n.kind === tab);
  const open = (n: Notif) => {
    setX((v) => ({ ...v, inbox: false, memoTab: n.kind === "upd" ? 1 : v.memoTab }));
    if (n.kind === "studio") act.readNotif(Number(n.id.slice(1)));
    if (n.kind === "upd" && n.stock_code) { go({ name: "stock", code: n.stock_code, tab: "board" }); if (n.memo != null) window.setTimeout(() => setMemoOpen(n.memo!), 120); }
    else if (n.view && n.made != null && made.some((m) => m.id === n.made)) { setStudio((s) => ({ ...s, open: true, badge: null, cur: n.made!, ...(n.view === "player" ? { mini: false, playing: true, t: 0 } : {}) })); sgo(n.view); }
  };
  return (
    <div ref={ref} role="dialog" aria-label="알림함" data-inbox className={cx("u074-pan fixed top-4 z-[60] flex max-h-[calc(100vh-32px)] w-[380px] flex-col rounded-[22px] border border-[#e5e8eb] bg-white shadow-[0_30px_60px_-30px_rgba(17,17,17,.35)]", x.inbox && "on")} style={{ left: (sideOpen ? 250 : 72) + 8 }}>
      <div className="flex items-center gap-2 px-5 pb-2 pt-[18px]">
        <p className="flex-1 text-[20px] font-bold leading-[29px] text-[#15171a]">알림</p>
        <button tabIndex={x.inbox ? 0 : -1} disabled={!unread} onClick={() => act.readAll()} className="h-8 rounded-[8px] px-2 text-[14px] font-bold text-[#575b63] enabled:hover:bg-[#f5f6f8] disabled:opacity-40">모두 읽음</button>
      </div>
      <div className="flex gap-1 px-4 pb-2">
        {([["all", "전체"], ["upd", "업데이트"], ["studio", "스튜디오"]] as const).map(([k, l]) => <button key={k} tabIndex={x.inbox ? 0 : -1} onClick={() => setTab(k)} className={cx("h-8 rounded-full px-3 text-[13px] font-bold transition-colors", tab === k ? "bg-[#15171a] text-white" : "text-[#8b95a1] hover:bg-[#f5f6f8]")}>{l}</button>)}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {allOff ? <Empty t="알림을 모두 꺼 두었어요" s="알림에서 켠 알림만 여기에 와요" /> : shown.length === 0 ? <Empty t="새 알림이 없어요" s="연결한 메모에 소식이 오면 여기에 모아 드려요" /> : shown.map((n) => (
          <button key={n.id} tabIndex={x.inbox ? 0 : -1} data-notif={n.id} onClick={() => open(n)} className={cx("u074-row relative flex w-full items-start gap-3 rounded-[14px] py-[11px] pl-3 pr-7 text-left hover:bg-[#f5f6f8]", n.read && "opacity-60")}>
            <NIcon n={n} />
            <span className="flex min-w-0 flex-1 flex-col"><span className="truncate text-[15px] font-bold leading-[23px] text-[#15171a]">{n.t}</span><span className="break-keep text-[14px] leading-[21px] text-[#575b63]">{n.s}</span><span className="text-[13px] leading-[20px] text-[#9a9ea7]">{n.when}</span></span>
            {!n.read && <span className="absolute right-3 top-[18px] h-2 w-2 rounded-full bg-[#e5484d]" />}
          </button>
        ))}
      </div>
      <button tabIndex={x.inbox ? 0 : -1} onClick={() => { setX((v) => ({ ...v, inbox: false })); openSettings("알림"); }} className="flex h-12 shrink-0 items-center justify-center border-t border-[#efeff2] text-[14px] font-bold text-[#575b63] hover:bg-[#f9f9f9]">알림 설정</button>
    </div>
  );
}
const Empty = ({ t, s }: { t: string; s: string }) => (
  <div className="flex flex-col items-center gap-1 px-6 py-12 text-center"><p className="text-[15px] font-bold leading-[23px] text-[#333d4b]">{t}</p><p className="break-keep text-[14px] leading-[21px] text-[#8b95a1]">{s}</p></div>
);

/* ---------- AI 사용량 창 (스튜디오 칩을 누르면) ---------- */
export function UsageSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { setOverlay, setPlanOpen, openSettings, setStudio } = useApp();
  const pct = useUsage(), day = useResetDay();
  return (
    <Modal open={open} onClose={onClose} width={400} label="AI 사용량">
      <div data-usage-sheet className="flex w-[400px] flex-col gap-4 rounded-[28px] bg-white px-7 py-[27px]">
        <div className="flex flex-col gap-1">
          <p className="text-[22px] font-bold leading-[31px] text-[#15171a]">AI 사용량</p>
          <p className="break-keep text-[15px] leading-[23px] text-[#747d8d]">{pct >= 100 ? `이번 달 AI 사용량을 다 썼어요 · ${day}에 새로 채워져요` : `이번 달 ${pct}% 사용 · ${day}에 새로 채워져요`}</p>
        </div>
        <div className="h-2 w-full rounded-full bg-[#eceef1]"><div className="h-2 rounded-full transition-[width]" style={{ width: `${pct}%`, background: pct >= 100 ? "#e5484d" : "#15171a", transitionDuration: "calc(.6s * var(--k))" }} /></div>
        <div className="flex flex-col gap-2">
          <button onClick={() => { onClose(); setStudio((s) => ({ ...s, open: true })); setOverlay("charge"); }} className="flex h-[68px] w-full items-center gap-3 rounded-[16px] bg-[#f5f6f8] px-4 text-left hover:bg-[#eef0f3]">
            <span className="flex min-w-0 flex-1 flex-col"><span className="text-[17px] font-bold leading-[26px] text-[#15171a]">크레딧 구매</span><span className="text-[14px] leading-[21px] text-[#747d8d]">이번 달에 필요한 만큼만 더 써요</span></span>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M6.75 4.5L11.25 9L6.75 13.5" stroke="#9AA0AA" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
          <button onClick={() => { onClose(); setPlanOpen(true); openSettings("사용량"); }} className="flex h-[68px] w-full items-center gap-3 rounded-[16px] bg-[#f5f6f8] px-4 text-left hover:bg-[#eef0f3]">
            <span className="flex min-w-0 flex-1 flex-col"><span className="text-[17px] font-bold leading-[26px] text-[#15171a]">플랜 변경</span><span className="text-[14px] leading-[21px] text-[#747d8d]">매달 받는 사용량을 늘려요</span></span>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M6.75 4.5L11.25 9L6.75 13.5" stroke="#9AA0AA" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
        </div>
      </div>
    </Modal>
  );
}

/* ---------- 검색 강조 ---------- */
export function Hl({ text, q }: { text: string; q: string }) {
  const t = q.trim(); if (!t) return <>{text}</>;
  const parts = text.split(t);
  return <>{parts.map((p, i) => <span key={i}>{p}{i < parts.length - 1 && <mark className="x-hl">{t}</mark>}</span>)}</>;
}

/* ---------- 초성 검색 ---------- */
const CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
export const cho = (s: string) => [...s].map((c) => { const n = c.charCodeAt(0) - 0xac00; return n >= 0 && n < 11172 ? CHO[Math.floor(n / 588)] : c; }).join("");
export const matchKo = (name: string, q: string) => { const t = q.trim(); if (!t) return true; return name.toLowerCase().includes(t.toLowerCase()) || ([...t].every((c) => CHO.includes(c)) && cho(name).includes(t)); };
