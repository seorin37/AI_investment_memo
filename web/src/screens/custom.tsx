/* 2.2 홈 직접 사용자화 + 2.4.1~2.4.4 위젯 — Figma 그대로 (이 화면이 곧 내 홈) */
import { useRef, useState, type ReactNode } from "react";
import { cx, Modal } from "../kit";
import { useApp, hm, ago, mmdd, type WItem } from "../store";
import { api, useQ } from "../api";
import type { MarketEvent } from "../api/types";
import { MarketCardBase } from "./home";

const G = 24, BW = 626; // 격자, 보드 안쪽 폭
const DEF: Record<string, { t: string; w: number; h: number; resize: boolean }> = {
  market: { t: "시장 지수·환율", w: BW, h: 277, resize: false },
  updates: { t: "종목별 업데이트", w: 248, h: 512, resize: true },
  schedule: { t: "주요 증시 일정", w: 512, h: 512, resize: true },
  news: { t: "뉴스", w: 254, h: 572, resize: true },
};
const hit = (a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
function findSlot(items: { x: number; y: number; w: number; h: number }[], w: number, h: number) {
  const ok = (r: { x: number; y: number; w: number; h: number }) => !items.some((i) => hit(r, { x: i.x - G + 1, y: i.y - G + 1, w: i.w + G * 2 - 2, h: i.h + G * 2 - 2 }));
  for (let y = 0; y < 4000; y += G) for (let x = 0; x + w <= BW; x += G) { const r = { x, y, w, h }; if (ok(r)) return r; }
  return { x: 0, y: 0, w, h };
}
/* 위젯 추가 칸 자리: Figma처럼 240 (공간이 모자라면 168까지) */
function addSlot(items: WItem[]) {
  if (!items.length) return { x: 0, y: 0, w: 280, h: 280 };
  for (const w of [240, 216, 192, 168]) { const r = findSlot(items, w, 240); if (r.y + 240 <= 572) return r; }
  return findSlot(items, 240, 240);
}

export function CustomPage() {
  const { ud, act, go } = useApp();
  const board = ud.home.board;
  const boardRef = useRef(board); boardRef.current = board;
  const setBoard = (f: (b: WItem[]) => WItem[]) => act.home({ board: f(boardRef.current) });
  const setHomeMode = (mode: "template" | "custom") => act.home({ mode });
  const [sel, setSel] = useState<string | null>(board[board.length - 1]?.id ?? null);
  const [pick, setPick] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const add = addSlot(board);
  const bottom = Math.max(572, add.y + add.h, ...board.map((b) => b.y + b.h));
  const addWidget = (id: string) => {
    const d = DEF[id];
    const s = findSlot(board, d.w, d.h);
    setBoard((b) => [...b, { id, ...s }]); setSel(id); setHomeMode("custom"); setPick(false);
  };
  const drag = (e: React.PointerEvent, it: WItem, mode: "move" | "nw" | "ne" | "sw" | "se") => {
    e.preventDefault(); e.stopPropagation(); setSel(it.id);
    const sx = e.clientX, sy = e.clientY, o = { ...it };
    const snap = (v: number) => Math.round(v / G) * G;
    const mv = (ev: PointerEvent) => {
      const dx = ev.clientX - sx, dy = ev.clientY - sy;
      let n = { ...o };
      if (mode === "move") n = { ...o, x: Math.max(0, Math.min(BW - o.w, o.x + dx)), y: Math.max(0, o.y + dy) };
      else {
        const minW = 168, minH = 168;
        if (mode.includes("e")) n.w = Math.max(minW, Math.min(BW - o.x, o.w + dx));
        if (mode.includes("s")) n.h = Math.max(minH, o.h + dy);
        if (mode.includes("w")) { const nx = Math.max(0, Math.min(o.x + o.w - minW, o.x + dx)); n.w = o.w + (o.x - nx); n.x = nx; }
        if (mode.includes("n")) { const ny = Math.max(0, Math.min(o.y + o.h - minH, o.y + dy)); n.h = o.h + (o.y - ny); n.y = ny; }
      }
      setBoard((b) => b.map((x) => (x.id === it.id ? n : x)));
    };
    const up = () => {
      window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up);
      setBoard((b) => {
        const me = b.find((x) => x.id === it.id)!;
        let n = { ...me, x: Math.min(BW - me.w, snap(me.x)), y: snap(me.y), w: me.w === BW ? BW : Math.min(BW, snap(me.w) || me.w), h: snap(me.h) || me.h };
        if (DEF[it.id].w === 254 && mode === "move") n = { ...n, w: me.w, h: me.h };
        const others = b.filter((x) => x.id !== it.id);
        if (others.some((x) => hit(n, x))) n = mode === "move" ? { ...n, ...findSlot(others, n.w, n.h) } : o; // 겹치면 빈 자리로
        return b.map((x) => (x.id === it.id ? n : x));
      });
    };
    window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
  };
  return (
    <div className="flex min-h-full w-full flex-col items-start gap-8 p-10">
      <div className="flex h-20 w-full items-center justify-between bg-white">
        <div className="flex h-20 w-[530px] flex-col items-start gap-[6px] bg-white">
          <p className="whitespace-nowrap text-[30px] font-bold leading-[40px] text-[#15171a]">홈 직접 사용자화</p>
          <p className="whitespace-nowrap text-[15px] leading-[23px] text-[#747d8d]">필요한 위젯을 추가해 나만의 투자 홈을 만들어 보세요.</p>
        </div>
        <button onClick={() => go({ name: "start" })} className="flex h-11 w-[144px] items-center justify-center rounded-[12px] border border-[#e8ecf3] bg-white text-[14px] font-medium leading-[21px] text-[#15171a] hover:bg-[#f9f9f9]">시작 화면으로</button>
      </div>
      <div ref={ref} onPointerDown={(e) => { if (e.target === e.currentTarget) setSel(null); }} className="relative w-full overflow-hidden rounded-[24px] bg-[#f5f6f8]" style={{ height: bottom + 48, maxWidth: 674 }}>
        {board.length > 0 && <div className="pointer-events-none absolute inset-0" style={{ backgroundImage: "linear-gradient(#e6eaf0 1px, transparent 1px), linear-gradient(90deg, #e6eaf0 1px, transparent 1px)", backgroundSize: "24px 24px" }} />}
        <button onClick={() => setPick(true)} className="m-new absolute flex flex-col items-center justify-center gap-3 rounded-[20px] border-2 border-dashed border-[#e8ecf3] bg-white hover:border-[#d7dce6]" style={{ left: 24 + add.x, top: 24 + add.y, width: add.w, height: add.h }}>
          <span className="text-[36px] leading-[54px] text-[#477bff]">＋</span>
          <span className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#15171a]">위젯 추가</span>
          <span className="whitespace-nowrap text-[13px] leading-[20px] text-[#747d8d]">클릭해서 위젯을 골라보세요</span>
        </button>
        {board.map((it) => (
          <Frame key={it.id} it={it} on={sel === it.id} onSel={() => setSel(it.id)} drag={drag} resize={DEF[it.id].resize} onDel={() => { setBoard((b) => b.filter((x) => x.id !== it.id)); setSel(null); }}>
            <WidgetBody id={it.id} w={it.w} />
          </Frame>
        ))}
      </div>
      <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#747d8d]">{board.length ? "상단 손잡이로 이동 · 모서리로 크기 조절 · 24px 격자에 맞춰 배치" : "추가한 위젯은 언제든 바꾸거나 삭제할 수 있어요."}</p>
      <WidgetPicker open={pick} onClose={() => setPick(false)} have={board.map((b) => b.id)} onAdd={addWidget} />
    </div>
  );
}

function Frame({ it, on, onSel, drag, resize, onDel, children }: { it: WItem; on: boolean; onSel: () => void; drag: (e: React.PointerEvent, it: WItem, m: "move" | "nw" | "ne" | "sw" | "se") => void; resize: boolean; onDel: () => void; children: ReactNode }) {
  return (
    <div onPointerDown={onSel} className={cx("m-pop absolute flex flex-col items-start rounded-[16px] border-[1.5px] bg-white", on ? "z-10 border-[#477bff]" : "border-transparent")} style={{ left: 24 + it.x, top: 24 + it.y, width: it.w, height: it.h }}>
      <div onPointerDown={(e) => drag(e, it, "move")} className="flex h-8 w-full shrink-0 cursor-grab touch-none items-center justify-between px-3 active:cursor-grabbing">
        <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#747d8d]">⠿  끌어서 이동</p>
        <div className="flex items-center gap-3">
          {resize && <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#747d8d]">↗ 크기 조절</p>}
          {on && <button onPointerDown={(e) => e.stopPropagation()} onClick={onDel} className="whitespace-nowrap text-[13px] leading-[20px] text-[#747d8d] hover:text-[#15171a]">삭제</button>}
        </div>
      </div>
      <div className="min-h-0 w-full flex-1 overflow-hidden">{children}</div>
      {on && (["nw", "ne", "sw", "se"] as const).map((c) => (
        <span key={c} onPointerDown={(e) => resize && drag(e, it, c)} className={cx("absolute h-[10px] w-[10px] touch-none rounded-[2px] border-[1.5px] border-[#477bff] bg-white", resize && (c === "nw" || c === "se" ? "cursor-nwse-resize" : "cursor-nesw-resize"))}
          style={{ left: c.includes("w") ? -5 : undefined, right: c.includes("e") ? -5 : undefined, top: c.includes("n") ? -5 : undefined, bottom: c.includes("s") ? -5 : undefined }} />
      ))}
    </div>
  );
}

function WidgetBody({ id, w }: { id: string; w: number }) {
  if (id === "market") return <div className="flex h-[245px] w-full items-start gap-4 px-0">{(["kospi", "kosdaq", "usd"] as const).map((k) => <MarketCardBase key={k} k={k} h={245} usdLabel="미국 USD" />)}</div>;
  if (id === "updates") return <UpdatesW />;
  if (id === "schedule") return <CalendarW w={w} />;
  return <NewsW />;
}
const CARD = "flex h-full w-full flex-col items-start overflow-hidden rounded-[20px] bg-white shadow-[0px_5px_22px_0px_rgba(20,26,46,0.04)]";
function UpdatesW() {
  const { go, stocks, newN } = useApp();
  const [hov, setHov] = useState(stocks[0]?.stock_code ?? "");
  return (
    <div className={cx(CARD, "gap-3 p-6")}>
      <p className="w-full text-[20px] font-medium leading-[29px] tracking-[-0.01em] text-[#15171a]">업데이트</p>
      <p className="w-full text-[13px] leading-[20px] text-[#747d8d]">내 종목의 새로운 소식</p>
      <div className="flex min-h-0 w-full flex-1 flex-col gap-3 overflow-y-auto">
      {!stocks.length && <p className="py-4 text-[13px] text-[#747d8d]">종목을 추가하면 여기에 모여요</p>}
      {stocks.map((st) => { const c = st.stock_code, b = newN[c] ?? 0; return (
        <button key={c} onMouseEnter={() => setHov(c)} onClick={() => go({ name: "updates", code: c })} className={cx("flex h-[78px] w-full shrink-0 flex-col items-start gap-2 rounded-[12px] border p-3 text-left", hov === c ? "border-[#111] bg-[#f7f7f7]" : "border-[#e8ecf3] bg-white")}>
          <div className="flex h-[26px] w-full items-start justify-between">
            <p className="text-[14px] font-medium leading-[21px] tracking-[-0.01em] text-[#15171a]">{st.name}</p>
            {b ? <span className="flex h-[26px] min-w-[26px] items-center justify-center rounded-full bg-[#e45d6a] px-1 text-[14px] font-medium leading-[21px] text-white">{b}</span> : null}
          </div>
          <p className="w-full text-[13px] leading-[20px] text-[#747d8d]">{st.hold} · {b ? `새 업데이트 ${b}건` : "모두 확인했어요"}</p>
        </button>
      ); })}
      </div>
      <button onClick={() => go({ name: "updates" })} className="w-full text-left text-[13px] font-medium leading-[20px] tracking-[-0.01em] text-[#111]">전체 업데이트 보기  →</button>
    </div>
  );
}
function CalendarW({ w }: { w: number }) {
  const { stocks } = useApp();
  void w;
  const now = new Date(); const [ym, setYm] = useState<[number, number]>([now.getFullYear(), now.getMonth()]);
  const first = new Date(ym[0], ym[1], 1), n = new Date(ym[0], ym[1] + 1, 0).getDate();
  const days: (number | null)[] = [...Array.from({ length: first.getDay() }, () => null), ...Array.from({ length: n }, (_, i) => i + 1)];
  const weeks = Array.from({ length: Math.ceil(days.length / 7) }, (_, i) => days.slice(i * 7, i * 7 + 7));
  const evs = (api.market.schedule(stocks.map((s) => s.stock_code)) as MarketEvent[]).filter((e) => +e.date.slice(0, 4) === ym[0] && +e.date.slice(5, 7) === ym[1] + 1);
  const ev: Record<number, boolean> = Object.fromEntries(evs.map((e) => [+e.date.slice(8, 10), true]));
  const today = now.getFullYear() === ym[0] && now.getMonth() === ym[1] ? now.getDate() : -1;
  const mv = (d: number) => setYm(([y, m]) => { const t = new Date(y, m + d, 1); return [t.getFullYear(), t.getMonth()]; });
  return (
    <div className={cx(CARD, "gap-3 p-6")}>
      <p className="w-full text-[20px] font-medium leading-[29px] tracking-[-0.01em] text-[#15171a]">주요 증시 일정</p>
      <div className="flex h-6 w-full items-center justify-between">
        <p className="text-[17px] font-medium leading-[26px] tracking-[-0.01em] text-[#15171a]">{ym[0]}년 {ym[1] + 1}월</p>
        <p className="flex w-24 items-center justify-center gap-2 text-[13px] leading-[20px] text-[#747d8d]"><button aria-label="이전 달" onClick={() => mv(-1)} className="px-1 hover:text-[#15171a]">‹</button><button onClick={() => setYm([now.getFullYear(), now.getMonth()])} className="hover:text-[#15171a]">오늘</button><button aria-label="다음 달" onClick={() => mv(1)} className="px-1 hover:text-[#15171a]">›</button></p>
      </div>
      <div className="flex h-5 w-full items-start gap-1">{["일", "월", "화", "수", "목", "금", "토"].map((d) => <p key={d} className="min-w-0 flex-1 text-center text-[13px] leading-[20px] text-[#747d8d]">{d}</p>)}</div>
      <div className="flex w-full flex-col items-start gap-2">
        {weeks.map((wk, i) => (
          <div key={i} className="flex h-9 w-full items-start justify-between px-[13.43px]">
            {Array.from({ length: 7 }, (_, j) => wk[j] ?? null).map((d, j) => (
              <div key={j} className={cx("relative flex h-9 w-9 flex-col items-center rounded-[12px] py-1", d === today ? "bg-[#111]" : d && ev[d] ? "bg-[#f3f4f6]" : "")}>
                {d && <p className={cx("w-[26px] text-center text-[13px] leading-[20px]", d === today ? "text-white" : "text-[#15171a]")}>{d}</p>}
                {d && ev[d] && <p className={cx("absolute left-[13px] top-[18px] w-[10px] text-center text-[26px] leading-[35px]", d === today ? "text-white" : "text-[#e5484d]")}>•</p>}
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="flex min-h-0 w-full flex-1 flex-col items-start gap-2 overflow-y-auto">
        {evs.length === 0 && <p className="text-[13px] leading-[20px] text-[#747d8d]">이 달에 정리된 일정이 없어요</p>}
        {evs.map((e) => <div key={e.date + e.title} className="flex h-8 w-full shrink-0 items-center gap-2 rounded-[12px] bg-[#f3f4f6] px-3"><p className="truncate text-[13px] font-medium leading-[20px] tracking-[-0.01em] text-[#15171a]">●  {e.date.slice(5, 7)}.{e.date.slice(8, 10)}   {e.title}</p></div>)}
      </div>
    </div>
  );
}
function NewsW() {
  const { stocks } = useApp();
  const codes = stocks.map((s) => s.stock_code);
  const all = useQ("news:" + codes.join(",") + api.market.lastClose(), () => api.market.news(codes)) ?? [];
  const head = all[0], list = all.slice(1, 8), day = api.market.lastClose();
  return (
    <div className="flex h-full w-full flex-col items-start gap-[9.31px] overflow-hidden rounded-[15.52px] bg-white p-[18.62px]">
      <div className="flex w-full items-center justify-between"><p className="text-[14px] font-medium leading-[21px] text-[#15171a]">뉴스</p><p className="text-[11px] leading-[16px] text-[#747d8d]">{mmdd(day)} · {all.filter((n) => n.at.slice(0, 10) === day).length}건</p></div>
      {head && <a href={head.url} target="_blank" rel="noreferrer" className="flex w-full flex-col items-start gap-[6.21px] rounded-[9.31px] bg-[#f3f4f6] p-[10.86px]">
        <div className="flex w-full items-center justify-between"><span className="rounded-[7.76px] bg-white px-[6.21px] py-[1.55px] text-[13px] font-medium leading-[20px] text-[#575b63]">{head.src}</span><p className="text-[13px] font-medium leading-[20px] text-[#575b63]">{hm(head.at)} · {ago(head.at)}</p></div>
        <p className="w-full text-[14px] font-bold leading-[21px] text-[#15171a]">{head.title}</p>
        <p className="text-[13px] font-medium leading-[20px] text-[#15171a] underline">원문 읽기 ↗</p>
      </a>}
      <div className="flex min-h-0 w-full flex-1 flex-col items-start overflow-y-auto">
        {list.map((n) => (
          <a key={n.id} href={n.url} target="_blank" rel="noreferrer" className="flex w-full items-start gap-[7.76px] border-t-[0.78px] border-[#eef0f3] px-[1.55px] py-[7.76px]">
            <p className="w-[34px] shrink-0 text-[13px] font-medium leading-[20px] text-[#747d8d]">{n.at.slice(0, 10) === day ? hm(n.at) : mmdd(n.at)}</p>
            <div className="flex min-w-0 flex-1 flex-col items-start gap-[1.55px]"><p className="w-full text-[13px] font-medium leading-[20px] text-[#15171a]">{n.title}</p><p className="text-[11px] leading-[16px] text-[#747d8d]">{n.src}</p></div>
            <p className="text-[13px] font-medium leading-[20px] text-[#9aa3b2]">↗</p>
          </a>
        ))}
      </div>
    </div>
  );
}

/* 위젯 고르기: 4. 종목 추가 팝업 스타일 (사용자 결정) */
function WidgetPicker({ open, onClose, have, onAdd }: { open: boolean; onClose: () => void; have: string[]; onAdd: (id: string) => void }) {
  const [p, setP] = useState<string | null>(null);
  const list = Object.entries(DEF);
  return (
    <Modal open={open} onClose={onClose} label="위젯 추가">
      <div className="flex w-[680px] max-w-[calc(100vw-32px)] flex-col gap-4 rounded-[20px] bg-white p-7">
        <div className="flex items-center justify-between"><p className="text-[20px] font-bold leading-[29px] text-[#191f28]">위젯 추가</p><button onClick={onClose} className="text-[13px] font-medium text-[#6b7684]">닫기</button></div>
        <div className="flex flex-col">
          {list.map(([id, d]) => {
            const done = have.includes(id);
            return (
              <button key={id} disabled={done} onClick={() => setP(id)} className={cx("flex h-[41px] items-center justify-between rounded-[10px] px-[14px] text-left", p === id && !done ? "bg-[#efefef]" : !done && "hover:bg-[#f9f9f9]")}>
                <span className={cx("text-[14px] text-[#191f28]", p === id && !done ? "font-bold" : "font-medium", done && "text-[#8f8f8f]")}>{d.t}</span>
                <span className="text-[13px] text-[#8f8f8f]">{done ? "추가됨" : `${d.w === BW ? "가로 전체" : `${d.w}×${d.h}`}`}</span>
              </button>
            );
          })}
        </div>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="h-[41px] w-[82px] rounded-[10px] bg-[#f7f8fa] text-[14px] font-bold text-[#8f8f8f]">취소</button>
          <button disabled={!p || have.includes(p)} onClick={() => p && (onAdd(p), setP(null))} className="h-[41px] w-[82px] rounded-[10px] bg-black text-[14px] font-bold text-white disabled:bg-[#e8ecf3] disabled:text-[#8f8f8f]">추가</button>
        </div>
      </div>
    </Modal>
  );
}
