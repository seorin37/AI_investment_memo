/* 3.1 최신 업데이트 · 3.2 종목 업데이트 — Figma 그대로 (양옆 접힘이면 2열) */
import { FixedFrame } from "./stock";
import { useLayoutEffect, useRef, useState } from "react";
import { cx, PageTitle } from "../kit";
import { SkelPage, SpentBox, Disclaimer, matchKo } from "../x";
import { api, useQ } from "../api";
import type { UpdateItem } from "../api/types";
import { SLogo } from "../fig";
import { useApp, ago, mmdd } from "../store";

type K = "공시" | "뉴스" | "주가";
const CHIP: Record<K, string> = { 공시: "bg-[#fbeded] text-[#e5484d]", 뉴스: "bg-[#e8edf5] text-black", 주가: "bg-[#e6f0e2] text-[#1e8e4e]" };
const Chip = ({ k }: { k: K }) => <span className={cx("flex shrink-0 items-center rounded-[6px] px-2 py-[3px] text-[13px] font-medium leading-[20px]", CHIP[k])}>{k}</span>;

/* 줄을 누르면 펼쳐지는 AI 요약 + 원문 근거 + 연결된 내 메모 */
const josa = (w: string) => { const c = w.charCodeAt(w.length - 1); return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? "을" : "를"; };
function Spark({ code, at, up }: { code: string; at: string; up: boolean }) {
  const all = api.market.closes(code, 40) as { t: string; c: number }[];
  const end = Math.max(1, all.findIndex((x) => x.t >= at.slice(0, 10)) + 1 || all.length), cl = all.slice(Math.max(0, end - 10), end).map((x) => x.c);
  const mn = Math.min(...cl), mx = Math.max(...cl), pts = cl.map((v) => 6 + ((mx - v) / (mx - mn || 1)) * 44);
  return (
    <svg width="100%" height="64" viewBox="0 0 220 64" preserveAspectRatio="none" fill="none" className="shrink-0">
      <line x1="0" y1="44" x2="220" y2="44" stroke="#9aa0aa" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
      <path d={pts.map((y, i) => `${i ? "L" : "M"}${(i * 216) / Math.max(1, pts.length - 1) + 2} ${y.toFixed(1)}`).join("")} stroke={up ? "#e5484d" : "#2f6bdb"} strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" className="m-line" pathLength={400} />
    </svg>
  );
}
function Row({ u, extra, logo, i }: { u: UpdateItem; extra?: string; logo?: boolean; i: number }) {
  const { x, setX, go, memos, setMemoOpen } = useApp();
  const [open, setOpen] = useState(false);
  const code = u.stock_code, k = u.kind, t = u.title, id = u.id;
  const unread = !x.read[id] && isNew(u);
  const memo = memos.find((m) => m.stock_code === code && m.ai && (m.timeline ?? []).some((e) => e.at === u.at && (e.title === u.title || e.title?.startsWith(u.title))));
  const name = api.market.info(code)?.name ?? "";
  const d = { sum: u.summary, quote: k === "공시" ? ["회사는 ", u.title.replace(/ 공시가 나왔어요$/, ""), "에 관한 사항을 공시합니다."] as [string, string, string] : undefined, src: `${u.src} · ${mmdd(u.at)}`, price: k === "주가" ? { up: !/하락|-/.test(u.title) } : undefined };
  return (
    <div data-upd-row={id} className="m-reveal w-full" style={{ ["--i" as string]: i }}>
      <button onClick={() => { setOpen(!open); if (unread) setX((v) => ({ ...v, read: { ...v.read, [id]: true } })); }} aria-expanded={open} className="flex w-full items-center gap-[10px] rounded-[10px] py-[2px] text-left hover:bg-[#f7f8fa]">
        {logo && <SLogo code={code} size={24} r={7} />}
        {extra && <span className="flex shrink-0 items-center rounded-[6px] bg-[#f7f8fa] px-2 py-[3px] text-[13px] font-medium leading-[20px] text-[#191f28]">{extra}</span>}
        <Chip k={k} />
        <p className={cx("min-w-0 flex-1 truncate text-[14px] leading-[21px] text-[#191f28]", unread ? "font-bold" : "font-medium")}>{t}</p>
        <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">{ago(u.at)}</p>
        <span className={cx("h-[6px] w-[6px] shrink-0 rounded-full transition-opacity", unread ? "bg-[#e5484d]" : "opacity-0")} aria-label={unread ? "안 읽음" : undefined} />
      </button>
      <div className={cx("x-fold", open && "on")}><div>
        <div className="mt-2 flex flex-col gap-3 rounded-[12px] bg-[#f7f8fa] p-4">
          <p className="break-keep text-[14px] leading-[21px] text-[#333d4b]">{d.sum}</p>
          {d.quote && <div className="rounded-[10px] bg-white px-3 py-[10px] text-[14px] leading-[21px] text-[#575b63] shadow-[inset_3px_0_0_#15171a]"><span className="text-[13px] font-bold text-[#8b95a1]">요약 · 원문 근거 </span>{d.quote[0]}<span className="font-bold text-[#15171a] underline decoration-[#ffd34d] decoration-[3px] underline-offset-[3px]">{d.quote[1]}</span>{d.quote[2]}</div>}
          {d.price && <div className="flex flex-col gap-1 rounded-[10px] bg-white px-3 py-2"><Spark code={code} at={u.at} up={d.price.up} /><p className="break-keep text-[13px] leading-[20px] text-[#575b63]">{name} 최근 10거래일 종가 · 전일 확정 종가로 코드가 계산했어요</p></div>}
          <div className="flex items-center justify-between gap-3">
            <p className="text-[13px] leading-[20px] text-[#8b95a1]">{d.src}{k !== "주가" ? " · AI가 원문에 있는 내용만 골라 적었어요" : ""}</p>
            {k !== "주가" && u.url && <a href={u.url} target="_blank" rel="noreferrer" className="shrink-0 text-[13px] font-bold text-[#15171a] underline underline-offset-2">{k === "공시" ? "원문 보기 ↗" : "원문 기사 열기 ↗"}</a>}
          </div>
          {memo ? <div className="flex items-center gap-3 border-t border-[#e8ecf3] pt-3">
            <span className="flex min-w-0 flex-1 flex-col"><span className="text-[13px] leading-[20px] text-[#8b95a1]">연결된 내 메모 · 작성 당시 {memo.date}</span><span className="truncate text-[14px] font-bold leading-[21px] text-[#15171a]">{memo.title}</span></span>
            <button onClick={() => { go({ name: "stock", code, tab: "board" }); setX((v) => ({ ...v, memoTab: 1 })); setMemoOpen(memo.id); }} className="h-9 shrink-0 rounded-[10px] bg-white px-3 text-[13px] font-bold text-[#15171a] shadow-[inset_0_0_0_1px_#e5e7eb] hover:bg-[#f9f9f9]">메모 보드에서 보기</button>
          </div> : <div className="flex items-center gap-3 border-t border-[#e8ecf3] pt-3"><span className="min-w-0 flex-1 break-keep text-[13px] leading-[20px] text-[#8b95a1]">이 소식과 연결된 메모가 없어요 · {name}{josa(name)} 지켜보는 메모에 AI 연결을 켜면 비슷한 소식을 모아 드려요</span><button onClick={() => { go({ name: "stock", code, tab: "board" }); setMemoOpen(-1); }} className="h-9 shrink-0 rounded-[10px] bg-white px-3 text-[13px] font-bold text-[#15171a] shadow-[inset_0_0_0_1px_#e5e7eb] hover:bg-[#f9f9f9]">메모 쓰기</button></div>}
        </div>
      </div></div>
    </div>
  );
}

/* 최근 2거래일 안의 소식만 '안 읽음'으로 셈 */
const isNew = (u: UpdateItem) => u.at.slice(0, 10) >= api.market.tradingDays(2)[0];

export function UpdatesPage({ code }: { code?: string }) {
  const { stocks, go, x, setX, creditOut, newN: NEW_N } = useApp();
  const ref = useRef<HTMLDivElement>(null);
  const order = stocks.map((s) => s.stock_code);
  const cur = code ? stocks.find((s) => s.stock_code === code) : undefined;
  const all = useQ("upd:" + order.join(",") + api.market.lastClose(), () => api.market.updates(order, 30)) ?? [];
  const byCode = (c: string) => all.filter((u) => u.stock_code === c);
  const CARD = (c: string) => byCode(c).slice(0, 3);
  const LIST = (c: string) => byCode(c);
  const ids = (cur ? LIST(cur.stock_code) : order.flatMap((c) => CARD(c))).filter(isNew).map((u) => u.id);
  const unread = ids.filter((id) => !x.read[id]).length;
  const markAll = () => setX((v) => ({ ...v, read: { ...v.read, ...Object.fromEntries(ids.map((id) => [id, true])) } }));
  /* 칩: 검은 알약이 스프링 곡선으로 미끄러짐 */
  const chipRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [pill, setPill] = useState<{ l: number; t: number; w: number; h: number } | null>(null);
  const chipBox = useRef<HTMLDivElement | null>(null);
  /* 11.18: 종목 칩은 글자를 세로로 꺾지 않고, 자리가 모자라면 다음 줄로 넘겨요. 줄이 바뀌어도 검은 알약이 따라가요 */
  useLayoutEffect(() => {
    const place = () => { const b = chipRefs.current[code ?? ""]; if (b) setPill({ l: b.offsetLeft, t: b.offsetTop, w: b.offsetWidth, h: b.offsetHeight }); };
    place();
    const ro = typeof ResizeObserver !== "undefined" && chipBox.current ? new ResizeObserver(place) : null;
    if (ro && chipBox.current) ro.observe(chipBox.current);
    return () => ro?.disconnect();
  }, [code, stocks.length]);
  const [q, setQ] = useState(""), [qOpen, setQOpen] = useState(false);
  /* 11.16 앱 통일: 종류(공시·뉴스·주가)만 모아 보기 — 알약이 미끄러짐 */
  const [topic, setTopic] = useState<"전체" | K>("전체");
  const pool = cur ? LIST(cur.stock_code) : order.flatMap((c) => CARD(c));
  const cnt = (k: K) => pool.filter((r) => r.kind === k).length;
  const tRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [tPill, setTPill] = useState<{ l: number; w: number } | null>(null);
  useLayoutEffect(() => { const b = tRefs.current[topic]; if (b) setTPill({ l: b.offsetLeft, w: b.offsetWidth }); }, [topic, code]);
  const pass = (k: K) => topic === "전체" || topic === k;
  const lastCode = useRef(code); if (lastCode.current !== code) { lastCode.current = code; if (topic !== "전체") setTopic("전체"); }
  const found = q.trim() ? stocks.filter((s) => matchKo(s.name, q) || s.stock_code.includes(q.trim())) : stocks;
  return (
    <FixedFrame>
    <div ref={ref} className="flex w-[860px] flex-col items-start gap-8 pb-8 pt-8">
      <PageTitle title={cur ? `${cur.name} 업데이트` : "최신 업데이트"} sub={cur ? `${cur.name}의 공시·뉴스·주가 변동을 시간순으로 모았어요` : "내 종목의 공시·뉴스·주가 변동을 모아봤어요"}
        right={<>
          {unread > 0 && <span data-unread className="flex items-center gap-[6px] rounded-full bg-white px-3 py-[6px] text-[13px] font-bold leading-[20px] text-[#15171a] shadow-[inset_0_0_0_1px_#e5e7eb]"><span className="h-[6px] w-[6px] rounded-full bg-[#e5484d]" />읽지 않은 소식 {unread}건</span>}
          <button data-readall disabled={!unread} onClick={markAll} className="flex items-center gap-1 rounded-full bg-[#e7e7e7] px-3 py-[6px] text-[13px] font-bold leading-[20px] text-[#111] enabled:hover:bg-[#dcdcdc] disabled:opacity-40"><svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2.5 7.2L5.4 10L11.5 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>모두 읽음</button>
        </>} />
      <div className="flex w-full flex-col items-start gap-6">
        {creditOut && <SpentBox title="AI 업데이트가 잠시 멈췄어요" sub={"이번 달 AI 사용량을 다 썼어요.\n다음 달 1일부터 새 소식을 다시 찾아요."} />}
        <div className="flex w-full items-start gap-3">
          <div ref={chipBox} data-upd-chips className="relative flex min-w-0 flex-1 flex-wrap items-start gap-2">
            {pill && <span className="x-pill" style={{ left: pill.l, top: pill.t, bottom: "auto", width: pill.w, height: pill.h }} />}
            {[["", "업데이트"], ...order.map((c) => [c, stocks.find((s) => s.stock_code === c)!.name])].map(([c, l]) => {
              const on = (code ?? "") === c;
              return <button key={l} ref={(el) => { chipRefs.current[c] = el; }} onClick={() => go({ name: "updates", code: c || undefined })} data-upd-chip={c || "all"} className={cx("relative flex shrink-0 items-start whitespace-nowrap rounded-[20px] px-4 py-2 text-[13px] font-medium leading-[20px] transition-colors", on ? "text-white" : "bg-white text-[#8f8f8f] hover:text-[#191f28]")}>{l}</button>;
            })}
          </div>
          <div className="relative shrink-0">
            <label className="flex h-9 w-[200px] items-center gap-[6px] rounded-full bg-white px-3 shadow-[inset_0_0_0_1px_#e5e7eb] focus-within:shadow-[inset_0_0_0_1.5px_#111]">
              <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="#6b7078" strokeWidth="1.6" strokeLinecap="round"><circle cx="9" cy="9" r="5.5" /><path d="M13 13l4 4" /></svg>
              <input data-upd-search value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => setQOpen(true)} onBlur={() => window.setTimeout(() => setQOpen(false), 150)} placeholder="내 종목에서 찾기 (초성도 돼요)" className="min-w-0 flex-1 bg-transparent text-[13px] leading-[20px] text-[#16171a] outline-none placeholder:text-[#8b95a1]" />
            </label>
            {qOpen && (
              <div className="m-pop absolute right-0 top-11 z-30 w-[260px] rounded-[14px] border border-[#e5e8eb] bg-white p-1.5 shadow-[0_12px_28px_-10px_rgba(31,46,84,.18)]">
                {found.length === 0 ? <p className="px-3 py-3 text-[13px] leading-[20px] text-[#8b95a1]">내 종목에 ‘{q}’이 없어요 · 종목은 사이드바 + 에서 추가해요</p> : found.map((s) => (
                  <button key={s.stock_code} onMouseDown={(e) => e.preventDefault()} onClick={() => { setQ(""); setQOpen(false); go({ name: "updates", code: s.stock_code }); }} className="flex h-10 w-full items-center justify-between rounded-[10px] px-3 text-left hover:bg-[#f5f6f8]">
                    <span className="truncate text-[14px] font-medium text-[#191f28]">{s.name}</span><span className="shrink-0 text-[13px] text-[#8b95a1]">{NEW_N[s.stock_code] ? `새 소식 ${NEW_N[s.stock_code]}` : "새 소식 없음"}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <div data-topics className="relative -mt-2 flex items-center gap-1 rounded-full bg-white p-1 shadow-[inset_0_0_0_1px_#e5e7eb]">
          {tPill && <span className="absolute top-1 bottom-1 rounded-full bg-[#f2f3f4] transition-[left,width]" style={{ left: tPill.l, width: tPill.w, transitionDuration: "calc(.45s * var(--k))", transitionTimingFunction: "cubic-bezier(.34,1.45,.64,1)" }} />}
          {(["전체", "공시", "뉴스", "주가"] as const).map((t) => <button key={t} ref={(el) => { tRefs.current[t] = el; }} data-topic={t} aria-pressed={topic === t} onClick={() => setTopic(t)} className={cx("relative flex h-8 items-center gap-1 rounded-full px-[14px] text-[13px] font-bold transition-colors", topic === t ? "text-[#15171a]" : "text-[#8b95a1] hover:text-[#15171a]")}>{t}{t !== "전체" && <span className="font-medium">{cnt(t)}</span>}</button>)}
        </div>
        <SkelPage id="updates" className="w-full">
        {!cur ? (
          <div className="grid w-full grid-cols-2 gap-4">
            {order.map((c) => {
              const s = stocks.find((x) => x.stock_code === c)!;
              const rows = CARD(c);
              const more = LIST(c).length - rows.length;
              return (
                <div key={c} data-sk className="m-reveal flex w-full flex-col items-start gap-[14px] overflow-hidden rounded-[16px] border border-[#e5e8eb] bg-white p-5">
                  <button data-upd-name={c} onClick={() => go({ name: "stock", code: c, tab: "board" })} aria-label={`${s.name} 화면으로`} className="group -mx-1 -my-[2px] flex items-center gap-2 rounded-[8px] px-1 py-[2px] hover:bg-[#f3f4f6]"><SLogo code={c} size={28} r={8} /><p className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#191f28]">{s.name}</p><span className="flex items-center rounded-[6px] bg-[#e8edf5] px-2 py-[3px] text-[13px] font-medium leading-[20px] text-black">{s.hold}</span><svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 transition-transform group-hover:translate-x-[2px]"><path d="M6 3.5L10.5 8L6 12.5" stroke="#8b95a1" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
                  <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">{s.stock_code} · {s.market}</p>
                  <div className="h-px w-full bg-[#e5e8eb]" />
                  {rows.length ? (rows.some((r) => pass(r.kind)) ? rows.map((r, i) => pass(r.kind) && <Row key={r.id} u={r} i={i} />) : <p className="text-[14px] font-medium leading-[21px] text-[#8b95a1]">{topic} 소식이 없어요</p>)
                    : <p className="text-[14px] font-medium leading-[21px] text-[#6b7684]">최근 30일 동안 새 소식이 없어요</p>}
                  {more > 0 && <button onClick={() => go({ name: "updates", code: c })} className="text-[13px] font-bold leading-[20px] text-[#575b63] hover:text-[#15171a]">+{more}건 더 보기</button>}
                </div>
              );
            })}
          </div>
        ) : (
          <div data-sk className="flex w-full flex-col items-start overflow-hidden rounded-[16px] border border-[#e5e8eb] bg-white">
            {LIST(cur.stock_code).filter((r) => pass(r.kind)).map((r, j) => (
              <div key={r.id} className="contents">
                {j > 0 && <div className="h-px w-full bg-[#e5e8eb]" />}
                <div className="w-full px-5 py-[14px]"><Row u={r} logo i={j} /></div>
              </div>
            ))}
            {LIST(cur.stock_code).length > 0 && !LIST(cur.stock_code).some((r) => pass(r.kind)) && <p className="px-5 py-4 text-[14px] font-medium leading-[21px] text-[#8b95a1]">{topic} 소식이 없어요</p>}
            {!LIST(cur.stock_code).length && <p className="px-5 py-4 text-[14px] font-medium leading-[21px] text-[#6b7684]">최근 30일 동안 새 소식이 없어요. AI가 매일 확인하고 있어요.</p>}
          </div>
        )}
        </SkelPage>
        <div data-upd-end className="flex w-full flex-col items-center gap-1 pt-2">
          <p className="text-[14px] font-medium leading-[21px] text-[#8b95a1]">최근 30일 업데이트를 모두 확인했어요</p>
          <Disclaimer />
        </div>
      </div>
    </div>
    </FixedFrame>
  );
}
