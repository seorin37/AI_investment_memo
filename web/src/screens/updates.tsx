/* 3.1 최신 업데이트 · 3.2 종목 업데이트 — Figma 그대로 (양옆 접힘이면 2열) */
import { FixedFrame } from "./stock";
import { useLayoutEffect, useRef, useState } from "react";
import { cx, PageTitle } from "../kit";
import { SkelPage, SpentBox, Disclaimer, matchKo } from "../x";
import { NEW_N } from "../data";
import { SLogo } from "../fig";
import { useApp } from "../store";

type K = "공시" | "뉴스" | "주가";
const CHIP: Record<K, string> = { 공시: "bg-[#fbeded] text-[#e5484d]", 뉴스: "bg-[#e8edf5] text-black", 주가: "bg-[#e6f0e2] text-[#1e8e4e]" };
const CARD: Record<string, [K, string, string][]> = {
  "005930": [["공시", "자기주식 취득 결정 관련 공시", "2시간 전"], ["뉴스", "HBM4 공급 확대 기대감", "1일 전"], ["주가", "주가 +2.1% 상승", "3시간 전"]],
  "000660": [["공시", "신규 시설투자 관련 공시", "2시간 전"], ["뉴스", "HBM4 공급 확대 기대감", "1일 전"], ["주가", "주가 +7.1% 상승", "2일 전"]],
  "035420": [["공시", "사업보고서 제출 관련 공시", "1시간 전"], ["뉴스", "AI 검색 서비스 개편 기대감", "5시간 전"], ["주가", "주가 +1.3% 상승", "1일 전"]],
};
const LIST: Record<string, [K, string, string][]> = {
  "005930": [["공시", "자기주식 취득 결정 관련 주요사항 보고", "DART · 10분 전"], ["뉴스", "차세대 HBM 패키징 투자 확대 발표", "뉴스 · 45분 전"], ["주가", "장중 2.1% 상승, 거래량 증가", "시세 · 2시간 전"], ["공시", "분기보고서 제출 및 실적 전망 공시", "DART · 4시간 전"], ["뉴스", "파운드리 신규 수주 기대감 확대", "뉴스 · 1일 전"], ["주가", "외국인 순매수 전환, 종가 1.4% 상승", "시세 · 2일 전"], ["뉴스", "반도체 업황 회복 전망 리포트 발간", "뉴스 · 3일 전"], ["공시", "사업보고서 정정 공시", "DART · 4일 전"], ["뉴스", "AI 반도체 생태계 협력 확대", "뉴스 · 5일 전"], ["주가", "기관 순매수 유입, 주가 0.8% 상승", "시세 · 6일 전"], ["공시", "현금배당 결정 공시", "DART · 1주 전"]],
  "000660": [["공시", "신규 시설투자 관련 공시", "DART · 2시간 전"], ["뉴스", "HBM4 공급 확대 기대감", "뉴스 · 1일 전"], ["주가", "주가 +7.1% 상승", "시세 · 2일 전"]],
  "035420": [["공시", "사업보고서 제출 관련 공시", "DART · 1시간 전"], ["뉴스", "AI 검색 서비스 개편 기대감", "뉴스 · 5시간 전"], ["주가", "주가 +1.3% 상승", "시세 · 1일 전"]],
};
const Chip = ({ k }: { k: K }) => <span className={cx("flex shrink-0 items-center rounded-[6px] px-2 py-[3px] text-[13px] font-medium leading-[20px]", CHIP[k])}>{k}</span>;
const AI_OK = ["005930", "000660", "035420", "105560"];

/* 11.16 앱 통일: 줄을 누르면 펼쳐지는 AI 요약 + 원문 근거 + 연결된 내 메모 (화면 예시) */
type Det = { sum: string; quote?: [string, string, string]; src: string; memo: string; when: string; price?: { cond: string; up: boolean } };
const DET: Record<string, Det> = {
  "000660|신규 시설투자 관련 공시": { sum: "신규 시설투자를 결정했다는 공시예요. 투자 대상과 기간, 금액은 원문에서 확인해 주세요.", quote: ["회사는 이사회 결의에 따라 ", "신규 시설투자를 결정", "하였으며, 세부 투자 금액과 기간은 아래와 같습니다."], src: "DART · 원문 1쪽", memo: "실적 나오면 다시 보기", when: "10.01" },
  "000660|HBM4 공급 확대 기대감": { sum: "메모에서 확인하려던 공급 관련 뉴스예요. HBM4 공급 물량이 늘어날 수 있다는 업계 관측을 전한 기사예요.", src: "한국경제 · 11.04", memo: "요즘 반도체 분위기 좋아 보여", when: "10.03" },
  "000660|주가 +7.1% 상승": { sum: "전날 종가보다 7.1% 올랐어요. 전일 확정 종가로 코드가 계산했어요 · 장중 가격 신호가 아니에요.", src: "KIS · 11.04 종가", memo: "15만원 밑으로 오면 다시 생각", when: "09.25", price: { cond: "15만 원 이하", up: true } },
  "005930|자기주식 취득 결정 관련 공시": { sum: "자기주식을 취득하기로 결정했다는 공시예요. 취득 예정 수량과 기간은 원문에서 확인해 주세요.", quote: ["회사는 ", "자기주식 취득을 결정", "하였으며 취득 예정 기간은 아래와 같습니다."], src: "DART · 원문 1쪽", memo: "자사주 매입 나오면 다시 보기", when: "10.12" },
  "005930|HBM4 공급 확대 기대감": { sum: "메모에서 확인하려던 경쟁 상황 관련 뉴스예요. HBM 공급과 관련된 업계 관측을 전한 기사예요.", src: "서울경제 · 11.05", memo: "파운드리 수주 소식 지켜보기", when: "10.20" },
  "005930|주가 +2.1% 상승": { sum: "전날 종가보다 2.1% 올랐어요. 전일 확정 종가 기준이에요.", src: "KIS · 11.05 종가", memo: "자사주 매입 나오면 다시 보기", when: "10.12", price: { cond: "변동 보기", up: true } },
  "035420|사업보고서 제출 관련 공시": { sum: "사업보고서가 제출됐어요. 사업 부문별 숫자는 원문에서 확인해 주세요.", quote: ["회사는 ", "제 27기 사업보고서", "를 제출합니다."], src: "DART · 원문 표지", memo: "AI 검색 반응 보기", when: "10.18" },
  "035420|AI 검색 서비스 개편 기대감": { sum: "메모에서 확인하려던 AI 검색 관련 뉴스예요. 검색 서비스 개편에 대한 기대를 전한 기사예요.", src: "매일경제 · 11.05", memo: "AI 검색 반응 보기", when: "10.18" },
  "035420|주가 +1.3% 상승": { sum: "전날 종가보다 1.3% 올랐어요. 전일 확정 종가 기준이에요.", src: "KIS · 11.05 종가", memo: "AI 검색 반응 보기", when: "10.18", price: { cond: "변동 보기", up: true } },
};
const det = (code: string, k: K, t: string): Det => DET[`${code}|${t}`] ?? { sum: k === "공시" ? `${t}가 올라왔어요. 자세한 내용은 원문에서 확인해 주세요.` : k === "뉴스" ? "내 메모와 관련된 기사예요. 기사 내용은 원문 링크에서 볼 수 있어요." : "전일 확정 종가 기준 변동이에요.", src: k === "공시" ? "DART" : k === "뉴스" ? "뉴스" : "KIS 종가", memo: "", when: "" };

function Spark({ up }: { up: boolean }) {
  const pts = [38, 40, 35, 37, 30, 33, 26, 22, 25, 14];
  return (
    <svg width="100%" height="64" viewBox="0 0 220 64" preserveAspectRatio="none" fill="none" className="shrink-0">
      <line x1="0" y1="44" x2="220" y2="44" stroke="#9aa0aa" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
      <path d={pts.map((y, i) => `${i ? "L" : "M"}${i * 24 + 2} ${y}`).join("")} stroke={up ? "#e5484d" : "#2f6bdb"} strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" className="m-line" pathLength={400} />
    </svg>
  );
}
function Row({ code, k, t, w, id, extra, logo, i }: { code: string; k: K; t: string; w: string; id: string; extra?: string; logo?: boolean; i: number }) {
  const { x, setX, go, memos, setMemoOpen } = useApp();
  const [open, setOpen] = useState(false);
  const unread = !x.read[id];
  const d = det(code, k, t);
  const memo = memos.find((m) => m.code === code && m.title === d.memo);
  return (
    <div data-upd-row={id} className="m-reveal w-full" style={{ ["--i" as string]: i }}>
      <button onClick={() => { setOpen(!open); if (unread) setX((v) => ({ ...v, read: { ...v.read, [id]: true } })); }} aria-expanded={open} className="flex w-full items-center gap-[10px] rounded-[10px] py-[2px] text-left hover:bg-[#f7f8fa]">
        {logo && <SLogo code={code} size={24} r={7} />}
        {extra && <span className="flex shrink-0 items-center rounded-[6px] bg-[#f7f8fa] px-2 py-[3px] text-[13px] font-medium leading-[20px] text-[#191f28]">{extra}</span>}
        <Chip k={k} />
        <p className={cx("min-w-0 flex-1 truncate text-[14px] leading-[21px] text-[#191f28]", unread ? "font-bold" : "font-medium")}>{t}</p>
        <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">{w}</p>
        <span className={cx("h-[6px] w-[6px] shrink-0 rounded-full transition-opacity", unread ? "bg-[#e5484d]" : "opacity-0")} aria-label={unread ? "안 읽음" : undefined} />
      </button>
      <div className={cx("x-fold", open && "on")}><div>
        <div className="mt-2 flex flex-col gap-3 rounded-[12px] bg-[#f7f8fa] p-4">
          <p className="break-keep text-[14px] leading-[21px] text-[#333d4b]">{d.sum}</p>
          {d.quote && <div className="rounded-[10px] bg-white px-3 py-[10px] text-[14px] leading-[21px] text-[#575b63] shadow-[inset_3px_0_0_#15171a]"><span className="text-[13px] font-bold text-[#8b95a1]">요약 · 원문 근거 </span>{d.quote[0]}<span className="font-bold text-[#15171a] underline decoration-[#ffd34d] decoration-[3px] underline-offset-[3px]">{d.quote[1]}</span>{d.quote[2]}</div>}
          {d.price && <div className="flex flex-col gap-1 rounded-[10px] bg-white px-3 py-2"><Spark up={d.price.up} /><p className="break-keep text-[13px] leading-[20px] text-[#575b63]">메모의 조건 · <b className="text-[#15171a]">{d.price.cond}</b> · 전일 확정 종가로 코드가 계산했어요</p></div>}
          <div className="flex items-center justify-between gap-3">
            <p className="text-[13px] leading-[20px] text-[#8b95a1]">{d.src}{k !== "주가" ? " · AI가 원문에 있는 내용만 골라 적었어요" : ""}</p>
            {k !== "주가" && <a href={k === "공시" ? "https://dart.fss.or.kr" : "https://www.hankyung.com"} target="_blank" rel="noreferrer" className="shrink-0 text-[13px] font-bold text-[#15171a] underline underline-offset-2">{k === "공시" ? "원문 보기 ↗" : "원문 기사 열기 ↗"}</a>}
          </div>
          {d.memo && <div className="flex items-center gap-3 border-t border-[#e8ecf3] pt-3">
            <span className="flex min-w-0 flex-1 flex-col"><span className="text-[13px] leading-[20px] text-[#8b95a1]">연결된 내 메모 · 작성 당시 {d.when}</span><span className="truncate text-[14px] font-bold leading-[21px] text-[#15171a]">{d.memo}</span></span>
            <button onClick={() => { go({ name: "stock", code, tab: "board" }); if (memo) { setX((v) => ({ ...v, memoTab: 1 })); setMemoOpen(memo.id); } }} className="h-9 shrink-0 rounded-[10px] bg-white px-3 text-[13px] font-bold text-[#15171a] shadow-[inset_0_0_0_1px_#e5e7eb] hover:bg-[#f9f9f9]">메모 보드에서 보기</button>
          </div>}
        </div>
      </div></div>
    </div>
  );
}

export function UpdatesPage({ code }: { code?: string }) {
  const { stocks, go, x, setX, studio } = useApp();
  const ref = useRef<HTMLDivElement>(null);
  const order = ["005930", "000660", "035420"].filter((c) => stocks.some((s) => s.code === c)).concat(stocks.map((s) => s.code).filter((c) => !["005930", "000660", "035420"].includes(c)));
  const cur = code ? stocks.find((s) => s.code === code) : undefined;
  const ids = (cur ? (LIST[cur.code] ?? []).map((_, i) => `${cur.code}-L${i}`) : order.flatMap((c) => (CARD[c] ?? []).map((_, i) => `${c}-C${i}`)));
  const unread = ids.filter((id) => !x.read[id]).length;
  const markAll = () => setX((v) => ({ ...v, read: { ...v.read, ...Object.fromEntries(ids.map((id) => [id, true])) } }));
  /* 칩: 검은 알약이 스프링 곡선으로 미끄러짐 */
  const chipRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [pill, setPill] = useState<{ l: number; w: number } | null>(null);
  useLayoutEffect(() => { const b = chipRefs.current[code ?? ""]; if (b) setPill({ l: b.offsetLeft, w: b.offsetWidth }); }, [code, stocks.length]);
  const [q, setQ] = useState(""), [qOpen, setQOpen] = useState(false);
  /* 11.16 앱 통일: 종류(공시·뉴스·주가)만 모아 보기 — 알약이 미끄러짐 */
  const [topic, setTopic] = useState<"전체" | K>("전체");
  const pool = cur ? (LIST[cur.code] ?? []) : order.flatMap((c) => CARD[c] ?? []);
  const cnt = (k: K) => pool.filter((r) => r[0] === k).length;
  const tRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [tPill, setTPill] = useState<{ l: number; w: number } | null>(null);
  useLayoutEffect(() => { const b = tRefs.current[topic]; if (b) setTPill({ l: b.offsetLeft, w: b.offsetWidth }); }, [topic, code]);
  const pass = (k: K) => topic === "전체" || topic === k;
  const lastCode = useRef(code); if (lastCode.current !== code) { lastCode.current = code; if (topic !== "전체") setTopic("전체"); }
  const found = q.trim() ? stocks.filter((s) => matchKo(s.name, q) || s.code.includes(q.trim())) : stocks;
  return (
    <FixedFrame>
    <div ref={ref} className="flex w-[860px] flex-col items-start gap-8 pb-8 pt-8">
      <PageTitle title={cur ? `${cur.name} 업데이트` : "최신 업데이트"} sub={cur ? `${cur.name}의 공시·뉴스·주가 변동을 시간순으로 모았어요` : "내 종목의 공시·뉴스·주가 변동을 모아봤어요"}
        right={<>
          {unread > 0 && <span data-unread className="flex items-center gap-[6px] rounded-full bg-white px-3 py-[6px] text-[13px] font-bold leading-[20px] text-[#15171a] shadow-[inset_0_0_0_1px_#e5e7eb]"><span className="h-[6px] w-[6px] rounded-full bg-[#e5484d]" />읽지 않은 소식 {unread}건</span>}
          <button data-readall disabled={!unread} onClick={markAll} className="flex items-center gap-1 rounded-full bg-[#e7e7e7] px-3 py-[6px] text-[13px] font-bold leading-[20px] text-[#111] enabled:hover:bg-[#dcdcdc] disabled:opacity-40"><svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2.5 7.2L5.4 10L11.5 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>모두 읽음</button>
        </>} />
      <div className="flex w-full flex-col items-start gap-6">
        {studio.creditOut && <SpentBox title="AI 업데이트가 잠시 멈췄어요" sub={"이번 달 AI 사용량을 다 썼어요.\n12월 1일부터 새 소식을 다시 찾아요."} />}
        <div className="flex w-full items-center gap-3">
          <div className="relative flex min-w-0 flex-1 items-start gap-2">
            {pill && <span className="x-pill" style={{ left: pill.l, width: pill.w }} />}
            {[["", "업데이트"], ...order.map((c) => [c, stocks.find((s) => s.code === c)!.name])].map(([c, l]) => {
              const on = (code ?? "") === c;
              return <button key={l} ref={(el) => { chipRefs.current[c] = el; }} onClick={() => go({ name: "updates", code: c || undefined })} className={cx("relative flex items-start rounded-[20px] px-4 py-2 text-[13px] font-medium leading-[20px] transition-colors", on ? "text-white" : "bg-white text-[#8f8f8f] hover:text-[#191f28]")}>{l}</button>;
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
                  <button key={s.code} onMouseDown={(e) => e.preventDefault()} onClick={() => { setQ(""); setQOpen(false); go({ name: "updates", code: s.code }); }} className="flex h-10 w-full items-center justify-between rounded-[10px] px-3 text-left hover:bg-[#f5f6f8]">
                    <span className="truncate text-[14px] font-medium text-[#191f28]">{s.name}</span><span className="shrink-0 text-[13px] text-[#8b95a1]">{NEW_N[s.code] ? `새 소식 ${NEW_N[s.code]}` : "새 소식 없음"}</span>
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
              const s = stocks.find((x) => x.code === c)!;
              const rows = CARD[c] ?? [];
              const more = (LIST[c]?.length ?? 0) - rows.length;
              return (
                <div key={c} data-sk className="m-reveal flex w-full flex-col items-start gap-[14px] overflow-hidden rounded-[16px] border border-[#e5e8eb] bg-white p-5">
                  <button data-upd-name={c} onClick={() => go({ name: "stock", code: c, tab: "board" })} aria-label={`${s.name} 화면으로`} className="group -mx-1 -my-[2px] flex items-center gap-2 rounded-[8px] px-1 py-[2px] hover:bg-[#f3f4f6]"><SLogo code={c} size={28} r={8} /><p className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#191f28]">{s.name}</p><span className="flex items-center rounded-[6px] bg-[#e8edf5] px-2 py-[3px] text-[13px] font-medium leading-[20px] text-black">{s.hold}</span><svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 transition-transform group-hover:translate-x-[2px]"><path d="M6 3.5L10.5 8L6 12.5" stroke="#8b95a1" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
                  <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">{s.code} · {s.market}</p>
                  <div className="h-px w-full bg-[#e5e8eb]" />
                  {rows.length ? (rows.some(([k]) => pass(k)) ? rows.map(([k, t, w], i) => pass(k) && <Row key={t + k} code={c} k={k} t={t} w={w} id={`${c}-C${i}`} i={i} />) : <p className="text-[14px] font-medium leading-[21px] text-[#8b95a1]">{topic} 소식이 없어요</p>)
                    : <p className="text-[14px] font-medium leading-[21px] text-[#6b7684]">{AI_OK.includes(c) ? "아직 업데이트가 없어요 · 메모를 AI와 연결해 보세요" : "AI 연결 준비 중인 종목이에요 · 메모는 바로 쓸 수 있어요"}</p>}
                  {more > 0 && <button onClick={() => go({ name: "updates", code: c })} className="text-[13px] font-bold leading-[20px] text-[#575b63] hover:text-[#15171a]">+{more}건 더 보기</button>}
                </div>
              );
            })}
          </div>
        ) : (
          <div data-sk className="flex w-full flex-col items-start overflow-hidden rounded-[16px] border border-[#e5e8eb] bg-white">
            {(LIST[cur.code] ?? []).map(([k, t, w], i) => [k, t, w, i] as const).filter(([k]) => pass(k)).map(([k, t, w, i], j) => (
              <div key={t} className="contents">
                {j > 0 && <div className="h-px w-full bg-[#e5e8eb]" />}
                <div className="w-full px-5 py-[14px]"><Row code={cur.code} k={k} t={t} w={w} id={`${cur.code}-L${i}`} logo i={j} /></div>
              </div>
            ))}
            {(LIST[cur.code] ?? []).length > 0 && !(LIST[cur.code] ?? []).some(([k]) => pass(k)) && <p className="px-5 py-4 text-[14px] font-medium leading-[21px] text-[#8b95a1]">{topic} 소식이 없어요</p>}
            {!(LIST[cur.code] ?? []).length && <p className="px-5 py-4 text-[14px] font-medium leading-[21px] text-[#6b7684]">{AI_OK.includes(cur.code) ? "아직 새 소식이 없어요. AI가 매일 확인하고 있어요." : "AI 연결 준비 중인 종목이에요 · 메모는 바로 쓸 수 있어요"}</p>}
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
