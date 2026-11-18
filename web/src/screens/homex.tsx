/* 11.16 앱 통일 — 홈 편집(끌어서 순서 · 빼기+되돌리기 · 위젯 추가 · 기본 구성 · 빈 상태), 시장 상세(훑어 보는 선 · 기간), 체크리스트 위젯.
   움직임: 들기·자리 비키기는 보드와 같은 FLIP(.46s), 시트·창은 기존 Modal. */
import { useRef, useState, type ReactNode } from "react";
import { Modal, cx, useSnack } from "../kit";
import { useApp } from "../store";
import { api } from "../api";
import { mkData, rangeLabels, type MkKey, type Range } from "../marketData";
import { useFlip } from "./board";

export const HALF = new Set(["updates", "news", "check"]);
export const CATALOG: [string, string, string][] = [["market", "시장 한눈에 보기", "코스피 · 코스닥 · 원/달러"], ["updates", "종목별 업데이트", "내 종목의 새 소식 수"], ["news", "오늘의 시장 뉴스", "4개 언론사 헤드라인"], ["check", "체크리스트", "자유롭게 적는 할 일 목록"]];
export const DEFAULT_W = ["market", "updates", "news"];

/* 줄 나누기: 넓은 위젯은 한 줄, 반쪽 위젯은 둘씩 */
export function rows(list: string[]) {
  const out: string[][] = []; let half: string[] = [];
  for (const id of list) { if (HALF.has(id)) { half.push(id); if (half.length === 2) { out.push(half); half = []; } } else { if (half.length) { out.push(half); half = []; } out.push([id]); } }
  if (half.length) out.push(half);
  return out;
}

export function HomeGrid({ render, onAdd }: { render: (id: string, w: number | string | undefined) => ReactNode; onAdd: () => void }) {
  const { x, ud, act } = useApp();
  const snack = useSnack();
  const list = ud.home.widgets, edit = x.homeEdit;
  const box = useRef<HTMLDivElement>(null);
  useFlip(box);
  const [drag, setDrag] = useState<string | null>(null), [gone, setGone] = useState<string | null>(null);
  const cur = useRef(list); cur.current = list;
  const setList = (f: (l: string[]) => string[]) => act.home({ widgets: f(cur.current) });
  const remove = (id: string) => {
    setGone(id);
    const kk = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--k")) || 1;
    window.setTimeout(() => { const before = list; setList((l) => l.filter((y) => y !== id)); setGone(null); snack("위젯을 뺐어요", { undo: () => setList(() => before) }); }, 320 * kk);
  };
  const down = (id: string) => (e: React.PointerEvent) => {
    e.preventDefault(); setDrag(id);
    const mv = (ev: PointerEvent) => {
      const els = [...(box.current?.querySelectorAll<HTMLElement>("[data-hw]") ?? [])];
      const hit = els.find((el) => { const r = el.getBoundingClientRect(); return ev.clientX >= r.left && ev.clientX <= r.right && ev.clientY >= r.top && ev.clientY <= r.bottom; });
      const to = hit?.dataset.hw; if (!to || to === id) return;
      setList((l) => { const a = l.filter((y) => y !== id); const i = a.indexOf(to); const j = l.indexOf(to) > l.indexOf(id) ? i + 1 : i; a.splice(j, 0, id); return a; });
    };
    const up = () => { setDrag(null); window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
  };
  const W = (id: string, w: number | string | undefined) => (
    <div key={id} data-hw={id} data-flip={"w-" + id} data-sk className={cx("relative min-w-0", w === undefined ? "flex-1" : "shrink-0", drag === id && "he-lift", gone === id && "he-gone")} style={typeof w === "number" ? { width: w } : w ? { width: w } : undefined}>
      {render(id, w)}
      {edit && (
        <div className="m-pop absolute right-3 top-3 z-20 flex items-center gap-1 rounded-[12px] bg-[#15171a] p-1 shadow-[0_8px_20px_-8px_rgba(0,0,0,.5)]">
          <button aria-label="끌어서 순서 바꾸기" onPointerDown={down(id)} className="grid h-8 w-8 cursor-grab touch-none place-items-center rounded-[8px] text-white hover:bg-white/10 active:cursor-grabbing"><svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><circle cx="5.5" cy="4" r="1.3" /><circle cx="10.5" cy="4" r="1.3" /><circle cx="5.5" cy="8" r="1.3" /><circle cx="10.5" cy="8" r="1.3" /><circle cx="5.5" cy="12" r="1.3" /><circle cx="10.5" cy="12" r="1.3" /></svg></button>
          <button aria-label="위젯 빼기" data-hw-remove={id} onClick={() => remove(id)} className="grid h-8 w-8 place-items-center rounded-[8px] text-white hover:bg-white/10"><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3.5 8h9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg></button>
        </div>
      )}
      {edit && <div className="pointer-events-none absolute inset-0 z-10 rounded-[20px] shadow-[0_0_0_2px_#111]" />}
    </div>
  );
  return (
    <div ref={box} data-home-grid className={cx("flex w-full flex-col gap-6", edit && "select-none")}>
      {list.length === 0 && (
        <button data-home-empty onClick={onAdd} className="m-in flex h-[220px] w-full flex-col items-center justify-center gap-2 rounded-[20px] border-2 border-dashed border-[#d5d8dd] bg-white hover:border-[#b9bec6]">
          <span className="text-[32px] leading-none text-[#15171a]">＋</span><span className="text-[17px] font-bold text-[#15171a]">위젯 추가</span><span className="text-[14px] text-[#8b95a1]">눌러서 위젯을 골라 보세요</span>
        </button>
      )}
      {rows(list).map((r) => (
        <div key={r.join("+")} className="flex w-full items-start gap-6">
          {r.length === 1 ? W(r[0], HALF.has(r[0]) ? "100%" : "100%") : r.map((id) => W(id, id === "updates" ? 320 : undefined))}
        </div>
      ))}
    </div>
  );
}

/* 편집 머리: 홈 제목 줄 오른쪽 버튼 대신 나오는 띠 */
export function EditBar({ onAdd, onReset }: { onAdd: () => void; onReset: () => void }) {
  const { setX } = useApp();
  return (
    <div data-edit-bar className="m-pop flex h-[76px] w-full items-center gap-3 rounded-[20px] bg-[#15171a] pl-6 pr-4 text-white">
      <div className="flex min-w-0 flex-1 flex-col"><p className="text-[17px] font-bold leading-[26px]">홈 편집</p><p className="text-[14px] leading-[21px] text-white/70">⋮⋮를 끌어 순서를 바꾸고, 필요 없는 건 − 로 빼 보세요.</p></div>
      <button onClick={onReset} className="h-10 rounded-[12px] px-3 text-[14px] font-bold text-white/80 hover:bg-white/10">기본 구성으로 되돌리기</button>
      <button onClick={onAdd} className="flex h-10 items-center gap-1 rounded-[12px] bg-white/10 px-4 text-[14px] font-bold hover:bg-white/20">＋ 위젯 추가</button>
      <button data-edit-done onClick={() => setX((v) => ({ ...v, homeEdit: false }))} className="h-10 rounded-[12px] bg-white px-5 text-[15px] font-bold text-[#15171a] hover:bg-[#f2f3f4]">완료</button>
    </div>
  );
}

export function AddWidget({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { ud, act } = useApp();
  const snack = useSnack();
  return (
    <Modal open={open} onClose={onClose} width={680} label="위젯 추가">
      <div data-add-widget className="flex w-[680px] flex-col gap-4 rounded-[20px] bg-white p-7">
        <div className="flex items-center justify-between"><p className="text-[22px] font-bold leading-[31px] text-[#15171a]">위젯 추가</p><button onClick={onClose} className="text-[14px] font-medium text-[#6b7684] hover:text-[#191f28]">닫기</button></div>
        <div className="flex flex-col gap-2">
          {CATALOG.map(([id, t, d]) => { const have = ud.home.widgets.includes(id); return (
            <button key={id} disabled={have} onClick={() => { act.home({ widgets: [id, ...ud.home.widgets] }); onClose(); snack("위젯을 맨 위에 넣었어요 · 끌어서 옮길 수 있어요", { check: true }); }} className={cx("flex h-[68px] w-full items-center gap-3 rounded-[16px] px-4 text-left", have ? "cursor-default bg-[#f7f8fa] opacity-60" : "bg-[#f5f6f8] hover:bg-[#eef0f3]")}>
              <span className="flex min-w-0 flex-1 flex-col"><span className="text-[17px] font-bold leading-[26px] text-[#15171a]">{t}</span><span className="text-[14px] leading-[21px] text-[#747d8d]">{d}</span></span>
              <span className="shrink-0 text-[14px] font-bold text-[#575b63]">{have ? "홈에 있어요" : "추가"}</span>
            </button>
          ); })}
        </div>
      </div>
    </Modal>
  );
}

export function ResetConfirm({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { act } = useApp();
  const snack = useSnack();
  return (
    <Modal open={open} onClose={onClose} width={400} label="기본 구성으로 되돌릴까요?">
      <div className="flex w-[400px] flex-col gap-6 rounded-[28px] bg-white px-7 py-[27px]">
        <div className="flex flex-col gap-2"><p className="text-[22px] font-bold leading-[31px] text-[#15171a]">기본 구성으로 되돌릴까요?</p><p className="break-keep text-[15px] leading-[23px] text-[#747d8d]">지금 순서와 고른 위젯이 처음 구성(시장 · 업데이트 · 뉴스)으로 바뀌어요.</p></div>
        <div className="flex gap-2">
          <button onClick={onClose} className="flex h-12 flex-1 items-center justify-center rounded-[12px] bg-[#f2f3f4] text-[15px] font-medium text-[#15171a]">취소</button>
          <button onClick={() => { act.home({ widgets: DEFAULT_W }); onClose(); snack("기본 구성으로 되돌렸어요", { check: true }); }} className="flex h-12 flex-1 items-center justify-center rounded-[12px] bg-[#14171c] text-[15px] font-medium text-white">되돌리기</button>
        </div>
      </div>
    </Modal>
  );
}

/* ---------- 체크리스트 위젯 (다 끝내면 축하) ---------- */
export function CheckWidget({ h = 472 }: { h?: number }) {
  const { checklists, stocks, act, go, setMemoOpen } = useApp();
  const [add, setAdd] = useState("");
  const withCl = stocks.filter((s) => checklists[s.stock_code]);
  const [pick, setPick] = useState<string | null>(null);
  const code = pick && stocks.some((s) => s.stock_code === pick) ? pick : (withCl[0] ?? stocks[0])?.stock_code;
  const cl = code ? checklists[code] : undefined, checklist = cl?.items ?? [];
  const done = checklist.length > 0 && checklist.every((c) => c.d);
  return (
    <div data-check-widget className="flex w-full flex-col gap-2 overflow-hidden rounded-[20px] border border-[#e5e7eb] bg-white px-6 pb-4 pt-[18px]" style={{ height: h }}>
      <div className="flex items-center justify-between"><p className="text-[17px] font-bold leading-[26px] text-[#15171a]">{cl?.title ?? "체크리스트"}</p><p className="text-[13px] text-[#6b7078]">{checklist.filter((c) => c.d).length}/{checklist.length}</p></div>
      {stocks.length > 0 && <div className="-mx-1 flex shrink-0 gap-1 overflow-x-auto px-1 pb-1">{stocks.map((s) => <button key={s.stock_code} onClick={() => setPick(s.stock_code)} className={cx("h-8 shrink-0 rounded-full px-3 text-[13px] font-bold transition-colors", s.stock_code === code ? "bg-[#15171a] text-white" : "bg-[#f3f4f6] text-[#575b63] hover:bg-[#e9eaec]")}>{s.name}{checklists[s.stock_code] ? ` ${checklists[s.stock_code].items.filter((c) => !c.d).length}` : ""}</button>)}</div>}
      {done && <div className="m-pop flex items-center gap-2 rounded-[12px] bg-[#f2f9f4] px-3 py-2 text-[14px] font-bold text-[#1e8e4e]"><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" fill="#1e8e4e" /><path d="M4.8 8.2L7 10.3L11.2 5.9" stroke="white" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>모두 확인했어요!</div>}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {!stocks.length && <p className="py-6 text-center text-[14px] text-[#8b95a1]">종목을 추가하면 종목별 체크리스트를 쓸 수 있어요</p>}
        {code && !checklist.length && <p className="py-6 text-center text-[14px] leading-[21px] text-[#8b95a1]">아직 체크리스트가 없어요<br />아래에 확인할 일을 적고 Enter</p>}
        {code && checklist.map((c) => (
          <button key={c.id} onClick={() => act.toggleCheck(code, c.id)} className="flex h-11 w-full shrink-0 items-center gap-3 border-t border-[#f0f1f3] text-left first:border-t-0">
            <span className={cx("grid h-5 w-5 shrink-0 place-items-center rounded-full transition-colors", c.d ? "bg-[#15171a]" : "shadow-[inset_0_0_0_1.6px_#c9ccd2]")}>{c.d && <svg className="m-pop" width="11" height="11" viewBox="0 0 12 12" fill="none"><path d="M2.5 6L4.8 8.3L9.5 3.5" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>}</span>
            <span className={cx("truncate text-[15px] leading-[23px] transition-colors", c.d ? "text-[#a0a5ad] line-through" : "text-[#15171a]")}>{c.t}</span>
          </button>
        ))}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <input disabled={!code} value={add} onChange={(e) => setAdd(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing && add.trim() && code) { act.addCheck(code, add.trim()); setAdd(""); } }} placeholder="할 일을 적고 Enter" className="h-11 min-w-0 flex-1 rounded-[12px] bg-[#f3f4f6] px-4 text-[15px] text-[#15171a] outline-none placeholder:text-[#8b95a1] disabled:opacity-50" />
        {code && <button onClick={() => { go({ name: "stock", code, tab: "board" }); setMemoOpen(-2); }} className="h-11 shrink-0 rounded-[12px] px-3 text-[13px] font-bold text-[#575b63] hover:bg-[#f3f4f6]">편집</button>}
      </div>
    </div>
  );
}

/* ---------- 시장 상세: 선을 훑으면 그날 값 · 기간 바꾸기 ---------- */
export function MarketDetail({ m, onClose }: { m: MkKey | null; onClose: () => void }) {
  const last = useRef(m); if (m) last.current = m;
  const key = m ?? last.current;
  const [r, setR] = useState<Range>("1달");
  const [hx, setHx] = useState<number | null>(null);
  if (!key) return <Modal open={false} onClose={onClose} label="시장 상세"><div /></Modal>;
  const md = mkData(key, r), sr = md.sr;
  const W = 616, H = 220, mn = Math.min(...sr), mx = Math.max(...sr);
  const X = (i: number) => (i / (sr.length - 1)) * W, Y = (v: number) => 10 + ((mx - v) / (mx - mn || 1)) * (H - 40);
  const col = md.up ? "#E5484D" : "#2F6BDB";
  const labels = rangeLabels(r);
  const days = r === "1일" ? [] : api.market.tradingDays(sr.length);
  const idx = hx === null ? null : Math.max(0, Math.min(sr.length - 1, Math.round((hx / W) * (sr.length - 1))));
  const fmt = (n: number) => n.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const when = (i: number) => r === "1일" ? `${String(9 + Math.floor((i * 390) / (sr.length - 1) / 60)).padStart(2, "0")}:${String(Math.floor(((i * 390) / (sr.length - 1)) % 60)).padStart(2, "0")}` : days[i] ? `${days[i].slice(5, 7)}.${days[i].slice(8, 10)} 종가` : "";
  const line = sr.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join("");
  return (
    <Modal open={!!m} onClose={onClose} width={680} label={`${md.name} 상세`}>
      <div data-market-detail className="flex w-[680px] flex-col gap-4 rounded-[28px] bg-white px-8 pb-7 pt-7">
        <div className="flex items-start justify-between">
          <div className="flex flex-col">
            <p className="text-[15px] font-medium leading-[23px] text-[#575b63]">{md.name}</p>
            <p className="text-[30px] font-bold leading-[40px] text-[#15171a]">{idx === null ? md.v : fmt(sr[idx])}</p>
            <p className="text-[14px] font-bold leading-[21px]" style={{ color: md.up ? "#e5484d" : "#2f6bdb" }}>{idx === null ? `${md.label} · ${md.when}` : when(idx)}</p>
          </div>
          <button aria-label="닫기" onClick={onClose} className="grid h-9 w-9 place-items-center rounded-[10px] hover:bg-[#f2f3f4]"><svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M5 5L15 15M15 5L5 15" stroke="#333" strokeWidth="1.8" strokeLinecap="round" /></svg></button>
        </div>
        <div className="relative" style={{ width: W, height: H }} onMouseMove={(e) => { const b = (e.currentTarget as HTMLElement).getBoundingClientRect(); setHx(((e.clientX - b.left) / b.width) * W); }} onMouseLeave={() => setHx(null)}>
          <svg key={r} width={W} height={H} viewBox={`0 0 ${W} ${H}`} fill="none" className="absolute inset-0">
            {[0, 1, 2, 3].map((i) => <line key={i} x1="0" x2={W} y1={10 + i * ((H - 40) / 3)} y2={10 + i * ((H - 40) / 3)} stroke="#eef0f3" />)}
            {idx !== null && <clipPath id="mdc"><rect x="0" y="0" width={X(idx)} height={H} /></clipPath>}
            <path d={line} stroke={idx === null ? col : "#c9ccd2"} strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" className={idx === null ? "m-line" : undefined} pathLength={idx === null ? 400 : undefined} />
            {idx !== null && <path clipPath="url(#mdc)" d={line} stroke={col} strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />}
            {idx !== null && <><line x1={X(idx)} x2={X(idx)} y1="0" y2={H - 24} stroke="#15171a" strokeDasharray="3 3" /><circle cx={X(idx)} cy={Y(sr[idx])} r="5" fill="#fff" stroke={col} strokeWidth="2.4" /></>}
          </svg>
          <div className="absolute bottom-0 left-0 right-0 flex justify-between">{labels.map((l, i) => <span key={l + i} className="text-[11px] leading-[16px] text-[#8b95a1]">{l}</span>)}</div>
        </div>
        <div className="flex h-12 w-full items-start rounded-[14px] bg-[#f3f4f6] p-1">
          {(["1일", "1주", "1달", "1년"] as Range[]).map((x) => <button key={x} onClick={() => setR(x)} className={cx("flex h-10 min-w-0 flex-1 items-center justify-center rounded-[12px] text-[15px] leading-[23px] transition-colors", r === x ? "bg-white font-bold text-[#16171a]" : "font-medium text-[#8b95a1] hover:text-[#16171a]")}>{x}</button>)}
        </div>
        <p className="text-[13px] leading-[20px] text-[#8b95a1]">선을 마우스로 훑으면 그때의 값이 보여요 · {r === "1일" ? "전 거래일 하루 흐름 · " : ""}{`${md.q.as_of.slice(5, 7)}.${md.q.as_of.slice(8, 10)} 종가 기준`}</p>
      </div>
    </Modal>
  );
}

/* ---------- 첫 홈 → 첫 메모 (앱 '첫 홈'): 종목 고르기 ✓ → 첫 메모 → AI 연결, 끝나면 '지켜보고 있어요' ---------- */
export function FirstMemo() {
  const { x, setX, stocks, go, setMemoOpen, ud } = useApp();
  const [pick, setPick] = useState(false), [code, setCode] = useState<string | null>(null);
  const st = x.firstStep;
  const steps: [string, boolean][] = [["종목 고르기", true], ["첫 메모", st >= 1], ["AI 연결", st >= 2]];
  return (
    <div data-first-memo className="m-in flex w-full flex-col gap-4 rounded-[20px] border border-[#e5e7eb] bg-white px-6 py-5">
      <div className="flex items-start gap-4">
        <div className="flex min-w-0 flex-1 flex-col">
          <p className="text-[20px] font-bold leading-[29px] text-[#15171a]">{st >= 2 ? "AI가 이 메모를 지켜보고 있어요" : st >= 1 ? "첫 메모를 남겼어요" : `반가워요, ${ud.profile?.name ?? ""}님 · 첫 메모를 남겨 보세요`}</p>
          <p className="break-keep text-[15px] leading-[23px] text-[#575b63]">{st >= 2 ? "관련 소식이 생기면 업데이트 탭과 알림함에 알려 드려요. 보통 공시·뉴스가 쌓이는 데 하루 이틀 걸려요." : st >= 1 ? "AI 연결은 메모를 열어 언제든 켤 수 있어요. 켜면 관련 공시·뉴스·종가 변화를 찾아 드려요." : "왜 이 종목을 골랐는지, 무엇을 확인하고 싶은지 한두 줄이면 충분해요."}</p>
        </div>
        {st >= 2 ? <button onClick={() => setX((v) => ({ ...v, first: false }))} className="h-10 shrink-0 rounded-[12px] bg-[#f2f3f4] px-4 text-[15px] font-bold text-[#15171a] hover:bg-[#e9eaec]">확인</button>
          : <button data-first-write onClick={() => { setCode(stocks[0]?.stock_code ?? null); setPick(true); }} className="h-11 shrink-0 rounded-[12px] bg-[#15171a] px-5 text-[15px] font-bold text-white hover:bg-[#2a2a2a]">{st >= 1 ? "메모 하나 더 쓰기" : "첫 메모 쓰기"}</button>}
      </div>
      <div className="flex items-center gap-2">
        {steps.map(([t, on], i) => (
          <span key={t} className="flex items-center gap-2">
            {i > 0 && <span className={cx("h-px w-6 transition-colors", on ? "bg-[#15171a]" : "bg-[#e5e7eb]")} />}
            <span className={cx("flex h-8 items-center gap-1 rounded-full px-3 text-[13px] font-bold transition-colors", on ? "bg-[#15171a] text-white" : "bg-[#f2f3f4] text-[#8b95a1]")}>{on && <svg className="m-pop" width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2.5 6L4.8 8.3L9.5 3.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>}{t}</span>
          </span>
        ))}
      </div>
      <Modal open={pick} onClose={() => setPick(false)} width={400} label="어느 종목에 남길까요?">
        <div data-first-pick className="flex w-[400px] flex-col gap-4 rounded-[28px] bg-white px-7 py-[27px]">
          <div className="flex flex-col gap-1"><p className="text-[22px] font-bold leading-[31px] text-[#15171a]">어느 종목에 남길까요?</p><p className="text-[15px] leading-[23px] text-[#747d8d]">메모는 종목별 메모 보드에 저장돼요</p></div>
          <div className="flex max-h-[300px] flex-col gap-1 overflow-y-auto">
            {stocks.length === 0 && <p className="py-6 text-center text-[14px] text-[#8b95a1]">고른 종목이 없어요 · 사이드바 + 에서 추가해 보세요</p>}
            {stocks.map((s) => { const on = code === s.stock_code; return (
              <button key={s.stock_code} onClick={() => setCode(s.stock_code)} className={cx("flex h-14 w-full items-center gap-3 rounded-[14px] px-3 text-left transition-colors", on ? "bg-[#f7f7f7] shadow-[inset_0_0_0_1.5px_#111]" : "hover:bg-[#f9f9f9]")}>
                <span className="flex min-w-0 flex-1 flex-col"><span className="text-[16px] font-bold text-[#15171a]">{s.name}</span><span className="text-[13px] text-[#8b95a1]">{s.hold}</span></span>
                <span className={cx("grid h-[22px] w-[22px] place-items-center rounded-full", on ? "bg-[#111]" : "shadow-[inset_0_0_0_1.6px_#c9ccd2]")}>{on && <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2.5 6L4.8 8.3L9.5 3.5" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>}</span>
              </button>
            ); })}
          </div>
          <button disabled={!code} onClick={() => { setPick(false); if (code) { go({ name: "stock", code, tab: "board" }); setMemoOpen(-1); } }} className="h-12 rounded-[12px] bg-[#14171c] text-[15px] font-medium text-white disabled:bg-[#c9ccd2]">이 종목에 메모 쓰기</button>
        </div>
      </Modal>
    </div>
  );
}
