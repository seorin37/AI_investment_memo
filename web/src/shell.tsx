import { useEffect, useRef, useState, type ReactNode } from "react";
import { DarkRail, DarkRow } from "./theme";
import { cx } from "./kit";
import { useApp } from "./store";
import { Icon, SLogo, type IconName } from "./fig";
import { WORDMARK, AVATAR } from "./assets_wm";
import { BellBtn, CtxMenu, matchKo } from "./x";
import { useStockActions } from "./screens/mine";
import type { Stock } from "./data";

/* Figma: Main Sidebar (Expanded 250 / Collapsed 72) — 위치·크기 그대로 */
const LABEL = "text-[17px] leading-[26px] text-[#1c1c1c]";

function Row({ icon, label, on, onClick, w = 218, children }: { icon?: IconName; label: string; on?: boolean; onClick?: () => void; w?: number; children?: ReactNode }) {
  return (
    <button onClick={onClick} className={cx("flex h-10 shrink-0 items-center gap-2 rounded-[8px] px-3 text-left", on ? "bg-[#f3f1ef]" : "bg-white hover:bg-[#f9f9f9]")} style={{ width: w }}>
      {icon && <Icon n={icon} c={on ? "#5E5668" : "#333333"} />}
      <span className={cx(LABEL, on && "font-bold !text-[#5e5668]")}>{label}</span>
      {children}
    </button>
  );
}

export function Sidebar() {
  const { route, go, stocks, memos, setOverlay, openSettings, sideOpen, setSideOpen } = useApp();
  const [open, setOpen] = useState({ mine: true, 보유: true, 관심: true });
  const [fly, setFly] = useState(false);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const qRef = useRef<HTMLInputElement>(null);
  const sact = useStockActions();
  const [smenu, setSmenu] = useState<{ s: Stock; at: { x: number; y: number } } | null>(null);
  useEffect(() => { const k = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setSideOpen(true); setTimeout(() => qRef.current?.focus(), 60); } }; window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, [setSideOpen]);
  const isStock = (c: string) => route.name === "stock" && route.code === c;
  const homeOn = route.name === "home" || route.name === "custom" || route.name === "start";
  const { journal, x, setX } = useApp();
  const res = q.trim()
    ? [...stocks.filter((s) => matchKo(s.name, q) || s.code.includes(q)).map((s) => ({ k: "s" + s.code, t: s.name, sub: s.code, go: () => { setX((v) => ({ ...v, recent: [s.name, ...v.recent.filter((r) => r !== s.name)].slice(0, 5) })); go({ name: "stock", code: s.code, tab: "board" }); } })),
       ...memos.filter((m) => (m.title + m.body).includes(q)).slice(0, 4).map((m) => ({ k: "m" + m.id, t: m.title, sub: `${stocks.find((s) => s.code === m.code)?.name ?? ""} 메모`, go: () => go({ name: "stock", code: m.code, tab: "board" }) })),
       ...journal.filter((j) => (j.title + j.body.join(" ")).includes(q)).slice(0, 3).map((j) => ({ k: "j" + j.id, t: j.title || "제목 없음", sub: "투자 기록", go: () => go({ name: "journal" }) }))]
    : [];
  const [focus, setFocus] = useState(false);
  const pick = (i: number) => { res[i]?.go(); setQ(""); qRef.current?.blur(); };

  const Support = (
    <div className="relative">
      {sideOpen ? <Row icon="settings" label="설정 및 지원" on={fly} onClick={() => setFly(!fly)} /> : <RailBtn icon="settings" label="설정 및 지원" on={fly} onClick={() => setFly(!fly)} />}
      {fly && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setFly(false)} />
          <div className="m-pop absolute bottom-0 z-40 flex w-[192px] flex-col gap-1 rounded-[8px] bg-white px-2 py-3 shadow-[0_4px_16px_rgba(0,0,0,.12)]" style={{ left: sideOpen ? 234 : 56 }}>
            {([["settings", "설정", () => openSettings("내 프로필")], ["feedback", "피드백", () => setOverlay("feedback")], ["help", "도움말", () => go({ name: "help" })]] as const).map(([i, l, f]) => (
              <Row key={l} icon={i} label={l} w={176} onClick={() => { setFly(false); f(); }} />
            ))}
          </div>
        </>
      )}
    </div>
  );

  if (!sideOpen)
    return (
      <nav aria-label="메뉴 (접힘)" className="flex h-full w-[72px] shrink-0 flex-col justify-between bg-white px-4 py-6">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-2"><RailBtn icon="panelOpen" label="사이드바 펼치기" onClick={() => setSideOpen(true)} plain /><BellBtn rail /></div>
          <button aria-label="검색" onClick={() => { setSideOpen(true); setTimeout(() => qRef.current?.focus(), 60); }} className="grid h-10 w-10 place-items-center rounded-[8px] bg-[#f9f9f9]"><Icon n="search" /></button>
          <div className="flex flex-col gap-2">
            <RailBtn icon="home" label="홈" on={homeOn} onClick={() => go({ name: "home" })} />
            <RailBtn icon="updates" label="최신 업데이트" on={route.name === "updates"} onClick={() => go({ name: "updates" })} />
            <RailBtn icon="journal" label="투자 기록" on={route.name === "journal"} onClick={() => go({ name: "journal" })} />
          </div>
        </div>
        <div className="min-h-0 flex-1 pt-2"><RailBtn icon="stocks" label="내 종목" on={route.name === "stock" || route.name === "mine"} onClick={() => go({ name: "mine" })} /></div>
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <DarkRail />
            <RailBtn icon="trash" label="휴지통" onClick={() => setOverlay("trash")} />
            {Support}
          </div>
          <span className="h-px w-10 bg-[#f9f9f9]" />
          <button aria-label="내 프로필" onClick={() => openSettings("내 프로필")} className="h-10 w-10 overflow-hidden rounded-full"><img src={AVATAR} alt="" className="dk-keep h-full w-full object-cover" /></button>
        </div>
      </nav>
    );

  const groups = (["보유", "관심"] as const).map((g) => [g, stocks.filter((s) => s.hold === g)] as const);
  return (
    <nav aria-label="메모스 메뉴" className="relative flex h-full w-[250px] shrink-0 flex-col gap-2 bg-white px-4 py-6">
      {/* top · fixed */}
      <div className="flex shrink-0 flex-col gap-6">
        <div className="relative h-10">
          <button aria-label="홈으로" onClick={() => go({ name: "home" })} className="absolute left-0 top-[-16px] h-[72px] w-[117px]"><img src={WORDMARK} alt="MEMO'S" className="h-full w-full" draggable={false} /></button>
          <span className="absolute left-[154px] top-1"><BellBtn /></span>
          <button aria-label="사이드바 접기" onClick={() => setSideOpen(false)} className="absolute left-[194px] top-2 grid h-6 w-6 place-items-center rounded-[6px] bg-white hover:bg-[#f9f9f9]"><Icon n="panel" size={24} c="#666666" /></button>
        </div>
        <div className="relative">
          <label className="flex h-10 w-[218px] items-center gap-1 rounded-[8px] bg-[#f9f9f9] px-3 py-[10px]">
            <Icon n="search" />
            <input ref={qRef} value={q} onChange={(e) => { setQ(e.target.value); setSel(0); }}
              onKeyDown={(e) => { if (e.key === "Escape") setQ(""); if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, res.length - 1)); } if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); } if (e.key === "Enter") pick(sel); }}
              onFocus={() => setFocus(true)} onBlur={() => window.setTimeout(() => setFocus(false), 150)}
              placeholder="검색" className="w-full bg-transparent text-[17px] leading-[26px] text-[#1c1c1c] outline-none placeholder:text-[#6b7078]" />
          </label>
          {!q.trim() && focus && (
            <div data-search-hint className="m-pop absolute left-0 top-12 z-40 w-[218px] rounded-[12px] border border-[#e5e8eb] bg-white p-1.5 shadow-[0_8px_24px_rgba(31,46,84,.10)]">
              <p className="px-[10px] pb-1 pt-2 text-[13px] font-bold text-[#8b95a1]">최근 찾은 종목</p>
              <div className="flex flex-wrap gap-1 px-2 pb-2">{x.recent.map((r) => <button key={r} onMouseDown={(e) => e.preventDefault()} onClick={() => { const s = stocks.find((y) => y.name === r); if (s) go({ name: "stock", code: s.code, tab: "board" }); else setQ(r); }} className="rounded-full bg-[#f2f3f4] px-[10px] py-1 text-[13px] font-medium text-[#333d4b] hover:bg-[#e9eaec]">{r}</button>)}</div>
              <p className="px-[10px] pb-1 pt-1 text-[13px] font-bold text-[#8b95a1]">많이 찾는 종목</p>
              {[["005930", "삼성전자"], ["000660", "SK하이닉스"], ["373220", "LG에너지솔루션"], ["005380", "현대차"]].map(([c, n]) => <button key={c} onMouseDown={(e) => e.preventDefault()} onClick={() => { if (stocks.some((s) => s.code === c)) go({ name: "stock", code: c, tab: "board" }); else setOverlay("addStock"); qRef.current?.blur(); }} className="flex h-9 w-full items-center justify-between rounded-[10px] px-[10px] text-left hover:bg-[#f5f6f8]"><span className="text-[14px] font-medium text-[#191f28]">{n}</span><span className="text-[13px] text-[#8f8f8f]">{stocks.some((s) => s.code === c) ? "내 종목" : "추가"}</span></button>)}
              <p className="px-[10px] pb-1 pt-2 text-[13px] leading-[20px] text-[#8b95a1]">종목·메모·기록을 한 번에 찾아요</p>
            </div>
          )}
          {q.trim() && (
            <div className="m-pop absolute left-0 top-12 z-40 w-[218px] rounded-[12px] border border-[#e5e8eb] bg-white p-1.5 shadow-[0_8px_24px_rgba(31,46,84,.10)]">
              {res.length === 0 && <div className="px-[14px] py-3"><p className="text-[13px] font-bold text-[#575b63]">찾지 못했어요</p><p className="text-[13px] leading-[20px] text-[#8f8f8f]">종목명·6자리 코드, 메모·기록 글자로 다시 찾아보세요</p></div>}
              {res.map((r, i) => (
                <button key={r.k} onMouseEnter={() => setSel(i)} onClick={() => pick(i)} className={cx("flex h-[41px] w-full items-center justify-between gap-2 rounded-[10px] px-[14px] text-left", sel === i && "bg-[#efefef]")}>
                  <span className={cx("truncate text-[14px] text-[#191f28]", sel === i ? "font-bold" : "font-medium")}>{r.t}</span>
                  <span className="shrink-0 text-[13px] text-[#8f8f8f]">{r.sub}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <Row icon="home" label="홈" on={homeOn} onClick={() => go({ name: "home" })} />
          <Row icon="updates" label="최신 업데이트" on={route.name === "updates"} onClick={() => go({ name: "updates" })} />
          <Row icon="journal" label="투자 기록" on={route.name === "journal"} onClick={() => go({ name: "journal" })} />
        </div>
      </div>

      {/* center · 내 종목 */}
      <div className="flex min-h-0 flex-1 flex-col gap-3">
        <div className="flex h-10 shrink-0 items-center">
          <Row icon="stocks" label="내 종목" w={154} on={route.name === "mine"} onClick={() => go({ name: "mine" })} />
          <button aria-label="종목 추가" onClick={() => setOverlay("addStock")} className="h-8 w-7 rounded-[6px] hover:bg-[#f9f9f9]"><Icon n="plus" size={28} c="#1C1C1C" style={{ width: 28, height: 32 }} /></button>
          <button aria-label="내 종목 접기" onClick={() => setOpen((o) => ({ ...o, mine: !o.mine }))} className="ml-1 grid h-8 w-7 place-items-center"><Icon n="chevUp" size={16} c="#666666" style={{ transform: open.mine ? "" : "rotate(180deg)", transition: "transform .25s" }} /></button>
        </div>
        <div className={cx("grid min-h-0 transition-[grid-template-rows] duration-300", open.mine ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
          <div className="min-h-0 overflow-y-auto overflow-x-hidden">
            <div className="flex flex-col gap-3">
              {groups.map(([g, list]) => (
                <div key={g} className="flex flex-col gap-1">
                  <button onClick={() => setOpen((o) => ({ ...o, [g]: !o[g] }))} className="relative flex h-10 w-[218px] items-center rounded-[8px] bg-white pl-10 hover:bg-[#f9f9f9]">
                    <span className="text-[13px] font-medium leading-[20px] text-[#6b7078]">{g}</span>
                    <span className="absolute left-[186px] top-1 grid h-8 w-7 place-items-center"><Icon n="chevUp" size={16} c="#666666" style={{ transform: open[g] ? "" : "rotate(180deg)", transition: "transform .25s" }} /></span>
                  </button>
                  <div className={cx("grid transition-[grid-template-rows] duration-300", open[g] ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
                    <div className="overflow-hidden">
                      <div className="flex gap-[3px] pl-11">
                        <span className="w-px shrink-0 bg-[#e5e7eb]" />
                        <SortList list={list} isStock={isStock} onMenu={(st, at) => setSmenu({ s: st, at })} />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <CtxMenu at={smenu?.at ?? null} items={smenu ? sact.menu(smenu.s) : []} onClose={() => setSmenu(null)} />
      {sact.confirm}
      {/* bottom · fixed */}
      <div className="flex shrink-0 flex-col gap-5">
        <div className="flex flex-col gap-2">
          <DarkRow />
          <Row icon="trash" label="휴지통" onClick={() => setOverlay("trash")} />
          {Support}
        </div>
        <span className="h-px w-[218px] bg-[#f9f9f9]" />
        <div className="flex h-12 w-[218px] items-center justify-between pr-1">
          <button onClick={() => openSettings("내 프로필")} className="flex items-center gap-3 text-left">
            <img src={AVATAR} alt="" className="dk-keep h-12 w-12 rounded-full object-cover" />
            <span className="flex flex-col gap-1"><span className={LABEL}>김나라</span><span className="text-[13px] leading-[20px] text-[#9f9f9f]">대학생</span></span>
          </button>
          <button aria-label="로그아웃" title="로그아웃" onClick={() => setOverlay("logout")} className="grid h-[18px] w-[18px] place-items-center"><Icon n="logout" size={18} /></button>
        </div>
      </div>
    </nav>
  );
}

/* 사이드바 종목 순서 바꾸기 — Lucian UX/UI Prompt #317 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#317 (날아가는 정렬 목록)
   줄은 절대 위치(translateY) + transform .6s cubic-bezier(.3,1.1,.4,1). 올라가는 줄은 앞으로(그림자), 내려가는 줄은 뒤로(.9). 잡은 줄은 손을 따라옴.
   끌기는 4px 넘게 움직였을 때만 (그냥 누르면 그 종목으로 이동). 키보드: Alt + ↑/↓ */
const ROW = 52;
function SortList({ list, isStock, onMenu }: { list: Stock[]; isStock: (c: string) => boolean; onMenu: (s: Stock, at: { x: number; y: number }) => void }) {
  const { go, setStocks } = useApp();
  const [drag, setDrag] = useState<{ code: string; from: number; dy: number } | null>(null);
  const [moved, setMoved] = useState<Record<string, "up" | "dn">>({});
  const ids = list.map((s) => s.code);
  const target = drag ? Math.max(0, Math.min(ids.length - 1, Math.round((drag.from * ROW + drag.dy) / ROW))) : -1;
  const order = drag ? (() => { const o = ids.filter((c) => c !== drag.code); o.splice(target, 0, drag.code); return o; })() : ids;
  const commit = (code: string, to: number) => {
    const from = ids.indexOf(code); if (from === to || to < 0) return;
    const next = ids.filter((c) => c !== code); next.splice(to, 0, code);
    const mv: Record<string, "up" | "dn"> = {}; next.forEach((c, i) => { const was = ids.indexOf(c); if (was > i) mv[c] = "up"; else if (was < i) mv[c] = "dn"; });
    setMoved(mv); window.setTimeout(() => setMoved({}), 1300);
    setStocks((all) => { const inG = new Set(ids), byCode = new Map(all.map((x) => [x.code, x])); let k = 0; return all.map((x) => (inG.has(x.code) ? byCode.get(next[k++])! : x)); });
  };
  const down = (s: Stock, i: number) => (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    const y0 = e.clientY; let started = false;
    const mv = (ev: PointerEvent) => { const dy = ev.clientY - y0; if (!started && Math.abs(dy) < 4) return; started = true; setDrag({ code: s.code, from: i, dy }); };
    const up = (ev: PointerEvent) => {
      window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up);
      if (!started) return;
      const dy = ev.clientY - y0, to = Math.max(0, Math.min(ids.length - 1, Math.round((i * ROW + dy) / ROW)));
      setDrag(null); commit(s.code, to);
      const stop = (ce: MouseEvent) => { ce.stopPropagation(); ce.preventDefault(); window.removeEventListener("click", stop, true); }; window.addEventListener("click", stop, true); window.setTimeout(() => window.removeEventListener("click", stop, true), 50);
    };
    window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
  };
  if (!list.length) return <span className="h-10" />;
  return (
    <div data-sort-list className="relative w-[170px]" style={{ height: list.length * ROW - 12 }}>
      {list.map((s, i) => {
        const pos = order.indexOf(s.code), me = drag?.code === s.code;
        const y = me ? drag!.from * ROW + drag!.dy : pos * ROW;
        const st = me ? "lift" : moved[s.code] ?? "";
        return (
          <div key={s.code} data-sort-row={s.code} className={cx("group absolute left-0 top-0 w-[170px] rounded-[8px]", me ? "z-20 shadow-[0_10px_22px_-12px_rgba(17,17,17,.45)]" : st === "up" ? "z-10 shadow-[0_10px_22px_-12px_rgba(17,17,17,.35)]" : st === "dn" ? "z-0 opacity-90" : "")}
            style={{ transform: `translateY(${y}px)${me ? " scale(1.03)" : ""}`, transition: me ? "box-shadow .3s" : "transform calc(.6s * var(--k)) cubic-bezier(.3,1.1,.4,1), box-shadow .3s, opacity .3s", background: me ? "#fff" : undefined }}
            onContextMenu={(e) => { e.preventDefault(); onMenu(s, { x: e.clientX, y: e.clientY }); }}>
            <button data-stock={s.code} onPointerDown={down(s, i)} onClick={() => go({ name: "stock", code: s.code, tab: "board" })}
              onKeyDown={(e) => { if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) { e.preventDefault(); commit(s.code, i + (e.key === "ArrowUp" ? -1 : 1)); } }}
              title="끌어서 순서 바꾸기 · Alt + ↑↓" className={cx("m-new flex h-10 w-[170px] touch-none select-none items-center gap-2 rounded-[8px] pl-2 pr-3", me ? "cursor-grabbing bg-white" : isStock(s.code) ? "bg-[#f3f1ef]" : "hover:bg-[#f9f9f9]")}>
              <SLogo code={s.code} size={24} r={7.2} />
              <span className={cx("truncate", LABEL, isStock(s.code) && "font-bold !text-[#5e5668]")}>{s.name}</span>
            </button>
            {!drag && <button aria-label={`${s.name} 메뉴`} data-stock-menu={s.code} onClick={(e) => { const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); onMenu(s, { x: r.left, y: r.bottom + 4 }); }} className="absolute right-1 top-2 grid h-6 w-6 place-items-center rounded-[6px] text-[#8b95a1] opacity-0 transition-opacity hover:bg-[#ececec] focus-visible:opacity-100 group-hover:opacity-100"><svg width="14" height="14" viewBox="0 0 18 18" fill="currentColor"><circle cx="4" cy="9" r="1.5" /><circle cx="9" cy="9" r="1.5" /><circle cx="14" cy="9" r="1.5" /></svg></button>}
          </div>
        );
      })}
    </div>
  );
}

function RailBtn({ icon, label, on, onClick, plain }: { icon: IconName; label: string; on?: boolean; onClick?: () => void; plain?: boolean }) {
  return (
    <button aria-label={label} title={label} onClick={onClick} className={cx("grid h-10 w-10 place-items-center rounded-[8px]", on ? "bg-[#f3f1ef]" : plain ? "hover:bg-[#f9f9f9]" : "bg-white hover:bg-[#f9f9f9]")}>
      <Icon n={icon} c={on ? "#5E5668" : "#333333"} />
    </button>
  );
}

/* 가운데 영역 (배경 #f3f4f6) */
export function Main({ children, navKey }: { children: ReactNode; navKey: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.scrollTo({ top: 0 }); }, [navKey]);
  return (
    <main ref={ref} className="relative min-w-0 flex-1 overflow-y-auto bg-[#f3f4f6] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <div key={navKey} className="m-in min-h-full">{children}</div>
    </main>
  );
}

export function PageHead({ title, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <header className="mb-5 flex items-end justify-between gap-4">
      <div className="min-w-0"><h1 className="text-[26px] font-bold leading-[35px] text-[#191f28]">{title}</h1>{sub && <p className="mt-1 text-[14px] text-[#575b63]">{sub}</p>}</div>
      {right}
    </header>
  );
}
