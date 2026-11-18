/* 2.1 홈 기본 템플릿 — Figma 3792:67043 home/main 그대로 */
import { FixedFrame } from "./stock";
import { useState, type ReactNode } from "react";
import { cx, PageTitle } from "../kit";
import { useApp, hm, ago, mmdd } from "../store";
import { api, useQ } from "../api";
import type { NewsItem } from "../api/types";
import { paperBg } from "../data";
import { SLogo, Plug12 } from "../fig";
import { CustomPage } from "./custom";
import { SkelPage, WidgetFail } from "../x";
import { HomeGrid, EditBar, AddWidget, ResetConfirm, CheckWidget, MarketDetail, FirstMemo } from "./homex";

/* ---------- 시장 카드 ---------- */
import { mkData, RANGES, type MkKey, type Range } from "../marketData";
const MK: { key: MkKey }[] = [{ key: "kospi" }, { key: "kosdaq" }, { key: "usd" }];
export function MarketCardBase({ k, h = 264, usdLabel }: { k: MkKey; h?: number; usdLabel?: string }) {
  const { askNudge, setX } = useApp();
  const [r, setR] = useState<Range>("1일");
  const md = mkData(k, r), m = { key: k, name: md.name, flag: md.flag, v: md.v };
  const d = [md.label, md.when, md.up ? 1 : -1, md.path, md.base] as const;
  const up = md.up, col = up ? "#E5484D" : "#2F6BDB";
  const pts = d[3].replace(/[ML]/g, " ").trim().split(/\s+/).map(Number);
  const ex = pts[pts.length - 2], ey = pts[pts.length - 1];
  const gid = `mg-${m.key}`;
  return (
    <div data-market={k} onClick={k === "usd" ? () => askNudge("lab") : undefined} className="flex min-w-0 flex-1 flex-col items-start justify-between overflow-hidden rounded-[20px] border border-[#e5e7eb] bg-white px-4 py-3" style={{ height: h }}>
      <div className="relative flex h-[62px] w-full flex-col items-start gap-[3px]">
        <button data-market-more={k} aria-label={`${m.name} 자세히`} onClick={(e) => { e.stopPropagation(); setX((v) => ({ ...v, market: k })); }} className="absolute right-[-6px] top-[-2px] flex h-7 items-center gap-[2px] rounded-[8px] px-[6px] text-[13px] font-medium text-[#8b95a1] hover:bg-[#f3f4f6] hover:text-[#15171a]">자세히<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M4.5 2.5L8 6L4.5 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
        <div className="flex items-center gap-[5px]"><span className="block h-3 w-3">{m.flag()}</span><p className="whitespace-nowrap text-[13px] font-medium leading-[20px] text-[#575b63]">{k === "usd" && usdLabel ? usdLabel : m.name}</p></div>
        <p className="whitespace-nowrap text-[26px] font-bold leading-[35px] text-[#16171a]">{m.v}</p>
        <div className="flex items-center gap-[6px]">
          <p className="whitespace-nowrap text-[13px] font-bold leading-[20px]" style={{ color: up ? "#e5484d" : "#2f6bdb" }}>{d[0]}</p>
          <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7078]">{d[1]}</p>
        </div>
      </div>
      <div className="relative h-[110px] w-full">
        {/* 11.13: 그래프를 세로로 늘림 (66 → 110). 좌표는 그대로 두고 세로만 늘려 그림 */}
        <svg key={r} className="m-line-in absolute left-0 top-0 overflow-visible" width="100%" height="110" viewBox="0 0 218.67 66" preserveAspectRatio="none" fill="none">
          <defs><linearGradient id={gid} x1="0" y1="18" x2="0" y2="66" gradientUnits="userSpaceOnUse"><stop stopColor={col} stopOpacity="0.18" /><stop offset="1" stopColor={col} stopOpacity="0" /></linearGradient></defs>
          <path d={`M0.35 ${d[4] + 0.35}H219`} stroke="#747D8D" strokeWidth="0.7" strokeLinecap="round" strokeDasharray="2 4" opacity="0.25" vectorEffect="non-scaling-stroke" />
          <path d={`${d[3]}V48H0Z`} transform="translate(0 18)" fill={`url(#${gid})`} />
          <path className="m-line" d={d[3]} transform="translate(1 19)" stroke={col} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        </svg>
        <div className="absolute h-[11px] w-[11px] rounded-full border" style={{ left: `calc(${(ex / 218.67) * 100}% - 5.5px)`, top: (ey + 18) * (110 / 66) - 5.5, borderColor: col }} />
        <div className="absolute h-[6px] w-[6px] rounded-full border-[1.5px] border-white" style={{ left: `calc(${(ex / 218.67) * 100}% - 3px)`, top: (ey + 18) * (110 / 66) - 3, background: col }} />
      </div>
      <div className="flex h-12 w-full items-start rounded-[14px] bg-[#f3f4f6] p-1">
        {RANGES.map((x) => (
          <button key={x} onClick={() => setR(x)} className={cx("flex h-10 min-w-0 flex-1 items-center justify-center rounded-[12px] text-[15px] leading-[23px] transition-colors", r === x ? "bg-white font-bold text-[#16171a]" : "font-medium text-[#575b63] hover:text-[#16171a]")}>{x}</button>
        ))}
      </div>
    </div>
  );
}
export function MarketWidget() {
  const { x } = useApp();
  if (x.widgetFail) return (
    <div className="flex h-[308px] w-full flex-col items-start gap-4">
      <div className="flex h-6 w-full items-center gap-2"><p className="text-[17px] font-bold leading-[26px] tracking-[-0.01em] text-[#16171a]">시장 한눈에 보기</p></div>
      <WidgetFail what="시장 정보" h={264} />
    </div>
  );
  return (
    <div className="flex h-[308px] w-full flex-col items-start gap-4">
      <div className="flex h-6 w-full items-center gap-2"><p className="text-[17px] font-bold leading-[26px] tracking-[-0.01em] text-[#16171a]">시장 한눈에 보기</p></div>
      <div className="flex h-[264px] w-full items-start gap-4">{MK.map((m) => <MarketCardBase key={m.key} k={m.key} />)}</div>
    </div>
  );
}

/* ---------- 업데이트 ---------- */
const ArrowSub = () => <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 1.5V6C2 6.53043 2.21071 7.03914 2.58579 7.41421C2.96086 7.78929 3.46957 8 4 8H10M7.5 10.5L10 8L7.5 5.5" stroke="#111111" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
export function UpdatesWidget({ w = 320, h = 472 }: { w?: number | string; h?: number }) {
  const { go, stocks, memos, newN: NEW_N } = useApp();
  const total = stocks.reduce((a, s) => a + (NEW_N[s.stock_code] ?? 0), 0);
  const UPD = stocks.map((s) => {
    const ms = memos.filter((m) => m.stock_code === s.stock_code && m.ai && m.news > 0).sort((a, b) => b.badge - a.badge);
    const m = ms[0], t = m?.timeline?.find((e) => e.kind === "공시" || e.kind === "뉴스" || e.kind === "주가");
    return { code: s.stock_code, name: s.name, hold: s.hold, n: NEW_N[s.stock_code] ?? 0, ...(m && t ? { kind: t.kind, t: t.title ?? "", memo: m.title, mc: paperBg(m.color) } : {}) };
  });
  const [sel, setSel] = useState(UPD[0]?.code ?? "");
  return (
    <div className="flex shrink-0 flex-col items-start gap-3 overflow-hidden rounded-[20px] border border-[#e5e7eb] bg-white p-5" style={{ width: w, height: h }}>
      <div className="flex w-full flex-col items-start gap-[2px]">
        <div className="flex w-full items-center justify-between">
          <p className="whitespace-nowrap text-[17px] font-bold leading-[26px] tracking-[-0.01em] text-[#16171a]">업데이트</p>
          <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7078]">새 소식 {total}건</p>
        </div>
        <p className="w-full text-[13px] leading-[20px] text-[#575b63]">내가 남긴 메모와 이어진 소식이에요</p>
      </div>
      <div className="flex min-h-0 w-full flex-1 flex-col items-start gap-[10px]">
        {UPD.length === 0 && <p className="w-full py-6 text-center text-[14px] leading-[21px] text-[#8b95a1]">내 종목을 추가하면 여기에 소식이 모여요</p>}
        <div className="flex min-h-0 w-full flex-1 flex-col items-start gap-[10px] overflow-y-auto">
        {UPD.map((u) => {
          const on = sel === u.code;
          return (
            <button key={u.code} onMouseEnter={() => setSel(u.code)} onFocus={() => setSel(u.code)} onClick={() => go({ name: "updates", code: u.code })}
              className={cx("flex w-full flex-col items-start gap-[10px] rounded-[14px] p-[14px] text-left transition-colors", on ? "bg-[#f8f8f8] shadow-[inset_0_0_0_1.5px_#111111]" : "bg-white shadow-[inset_0_0_0_1px_#e5e7eb]")}>
              {/* 11.18: 이름·보유/관심은 늘 한 줄. 자리가 모자라면 오른쪽 상태 글자가 다음 줄로 내려가요 */}
              <div className="flex w-full flex-wrap items-center gap-x-2 gap-y-1">
                <span className="flex min-w-0 max-w-full items-center gap-2">
                  <SLogo code={u.code} size={28} r={8.4} />
                  <p className="min-w-0 truncate whitespace-nowrap text-[15px] font-bold leading-[23px] text-[#16171a]" title={u.name}>{u.name}</p>
                  <span className="shrink-0 whitespace-nowrap rounded-[6px] bg-[#f3f4f6] px-[6px] py-[2px] text-[13px] font-medium leading-[20px] text-[#575b63]">{u.hold}</span>
                </span>
                {u.n ? <span className="ml-auto grid h-[22px] min-w-[22px] shrink-0 place-items-center rounded-full bg-[#e45d6a] px-1 text-[13px] font-bold leading-none text-white">{u.n}</span> : <span className="ml-auto shrink-0 whitespace-nowrap text-[13px] leading-[20px] text-[#6b7078]">{"memo" in u ? "모두 확인했어요" : "연결된 소식 없음"}</span>}
              </div>
              {"memo" in u && (
                <div className={cx("flex w-full flex-col items-start gap-[6px] rounded-[10px] p-[10px] transition-colors", on ? "bg-[#e7e7e7]" : "bg-[#f3f4f6]")}>
                  <div className="flex w-full items-center gap-[6px]">
                    <span className={cx("rounded-[6px] border bg-white px-[6px] py-[1px] text-[13px] font-bold leading-[20px] text-[#575b63]", on ? "border-[#e5e7eb]" : "border-white")}>{u.kind}</span>
                    <p className="min-w-0 flex-1 truncate text-[13px] font-medium leading-[20px] text-[#16171a]">{u.t}</p>
                  </div>
                  <div className="flex w-full items-center gap-[6px]">
                    <ArrowSub />
                    <span className="h-[10px] w-[10px] shrink-0 rounded-[3px] border border-[rgba(22,23,26,0.12)]" style={{ background: u.mc }} />
                    <p className="min-w-0 flex-1 truncate text-[13px] font-medium leading-[20px] text-[#111111]">{u.memo}</p>
                  </div>
                </div>
              )}
            </button>
          );
        })}
        </div>
      </div>
      <button onClick={() => go({ name: "updates" })} className="w-[200px] text-left text-[13px] font-bold leading-[20px] tracking-[-0.01em] text-[#111111] underline">전체 업데이트 보기  →</button>
    </div>
  );
}

/* ---------- 뉴스 ---------- */
export function NewsWidget({ h = 472, className }: { h?: number; className?: string }) {
  const { stocks } = useApp();
  const codes = stocks.map((s) => s.stock_code);
  const all = useQ("news:" + codes.join(",") + api.market.lastClose(), () => api.market.news(codes)) ?? [];
  const day = api.market.lastClose(), today = all.filter((n) => n.at.slice(0, 10) === day);
  const head: NewsItem | undefined = all[0], NEWS = all.slice(1, 9);
  return (
    <div className={cx("flex min-w-0 flex-1 flex-col items-start gap-2 overflow-hidden rounded-[20px] border border-[#e5e7eb] bg-white px-6 pb-[14px] pt-[18px]", className)} style={{ height: h }}>
      <div className="flex w-full items-center justify-between">
        <p className="whitespace-nowrap text-[17px] font-bold leading-[26px] text-[#15171a]">뉴스</p>
        <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7078]">{mmdd(day)} · {today.length}건</p>
      </div>
      {head && <a href={head.url} target="_blank" rel="noreferrer" className="flex w-full flex-col items-start gap-2 rounded-[12px] bg-[#f3f4f6] px-[14px] py-3 hover:bg-[#eceef1]">
        <div className="flex w-full items-center justify-between">
          <span className="flex items-center rounded-[10px] border border-[#e5e7eb] bg-white px-2 py-[2px] text-[13px] font-medium leading-[20px] text-[#575b63]">{head.src}</span>
          <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7078]">{hm(head.at)} · {ago(head.at)}</p>
        </div>
        <p className="w-full text-[17px] font-bold leading-[26px] text-[#15171a]">{head.title}</p>
        <p className="whitespace-nowrap text-[13px] font-bold leading-[20px] text-[#111111] underline">원문 읽기 ↗</p>
      </a>}
      <div className="flex min-h-0 w-full flex-1 flex-col items-start overflow-y-auto">
        {NEWS.map((n) => (
          <a key={n.id} href={n.url} target="_blank" rel="noreferrer" className="flex w-full items-start gap-[10px] border-t border-[#e5e7eb] px-[2px] py-[9px] hover:bg-[#fafafa]">
            <p className="w-[38px] shrink-0 text-[13px] leading-[20px] text-[#6b7078]">{n.at.slice(0, 10) === day ? hm(n.at) : mmdd(n.at)}</p>
            <div className="flex min-w-0 flex-1 flex-col items-start gap-[2px]">
              <p className="w-full text-[14px] font-medium leading-[21px] text-[#15171a]">{n.title}</p>
              <p className="whitespace-nowrap text-[13px] font-medium leading-[20px] text-[#575b63]">{n.src}</p>
            </div>
            <p className="whitespace-nowrap text-[14px] font-medium leading-[21px] text-[#6b7078]">↗</p>
          </a>
        ))}
      </div>
    </div>
  );
}

/* ---------- 홈 ---------- */
export function HomeHead({ right }: { right?: ReactNode }) {
  const { stocks, memos, setX, x } = useApp();
  return (
    <PageTitle title="홈" sub="떠오른 생각을 적어 두면, AI가 관련 소식을 대신 확인해요." right={<>
        {right}
        <span className="flex items-center gap-[6px] rounded-full border border-[#e5e7eb] bg-white px-3 py-[6px] text-[13px] font-medium leading-[20px] text-[#575b63]">내 종목 <b className="font-bold text-[#16171a]">{stocks.length}</b></span>
        <span className="flex items-center gap-[6px] rounded-full bg-[#e7e7e7] px-3 py-[6px] text-[13px] font-medium leading-[20px] text-[#111111]"><Plug12 c="#111111" />AI 연결 메모 <b className="font-bold">{memos.filter((m) => m.ai).length}</b></span>
        {!x.homeEdit && <button data-home-edit onClick={() => setX((v) => ({ ...v, homeEdit: true }))} className="flex items-center gap-1 rounded-full border border-[#e5e7eb] bg-white px-3 py-[6px] text-[13px] font-bold leading-[20px] text-[#15171a] hover:bg-[#f9f9f9]"><svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9.5 3.5l3 3M3 13l.6-3L10.8 2.8a1 1 0 0 1 1.4 0l1 1a1 1 0 0 1 0 1.4L6 12.4z" /></svg>홈 편집</button>}
      </>} />
  );
}
/* v2: 오늘 내 생각에 붙은 소식 — 홈 맨 위 한 줄 요약 + 바로가기 (11.14 멘토링 반영) */
export function TodayStrip() {
  const { stocks, go, newN: NEW_N } = useApp();
  const rows = stocks.map((s) => [s.name, NEW_N[s.stock_code] ?? 0] as const).filter(([, n]) => n > 0);
  const total = rows.reduce((a, [, n]) => a + n, 0);
  return (
    <div data-today className="flex h-[76px] w-full shrink-0 items-center gap-4 rounded-[20px] border border-[#e5e7eb] bg-white pl-5 pr-4">
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-[#111111]"><Plug12 size={20} c="#ffffff" /></span>
      <div className="flex min-w-0 flex-1 flex-col items-start">
        <p className="w-full truncate text-[17px] font-bold leading-[26px] tracking-[-0.01em] text-[#16171a]">{total ? <>오늘 내 생각에 붙은 소식 {total}건</> : "오늘은 내 생각에 붙은 새 소식이 없어요"}</p>
        <p className="w-full truncate text-[14px] leading-[21px] text-[#575b63]">{total ? rows.map(([n, c]) => `${n} ${c}건`).join(" · ") : "AI가 매일 확인하고 있어요. 새 소식이 오면 알려 드릴게요."}</p>
      </div>
      {total > 0 && <button onClick={() => go({ name: "updates" })} className="flex h-11 shrink-0 items-center gap-1 rounded-[12px] bg-[#111111] px-4 text-[15px] font-bold leading-[23px] text-white hover:bg-[#2a2a2a]">확인하기<svg width="16" height="16" viewBox="0 0 14 14" fill="none"><path d="M3 7h8M7.5 3.5 11 7l-3.5 3.5" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg></button>}
    </div>
  );
}
export function MarketDetailHost() {
  const { x, setX } = useApp();
  return <MarketDetail m={(x.market as MkKey | null) ?? null} onClose={() => setX((v) => ({ ...v, market: null }))} />;
}
export function HomePage() {
  const { ud, x } = useApp();
  const homeMode = ud.home.mode;
  const [add, setAdd] = useState(false), [reset, setReset] = useState(false);
  if (homeMode === "custom") return <CustomPage />;
  return (
    <FixedFrame>
    <SkelPage id="home">
    <div className={cx("flex w-[860px] flex-col items-start gap-8 pb-8 pt-8", x.homeEdit && "he-on")}>
      <HomeHead />
      {x.homeEdit ? <EditBar onAdd={() => setAdd(true)} onReset={() => setReset(true)} /> : x.first ? <div data-sk className="w-full"><FirstMemo /></div> : <div data-sk className="w-full"><TodayStrip /></div>}
      <HomeGrid onAdd={() => setAdd(true)} render={(id, w) => id === "market" ? <MarketWidget /> : id === "updates" ? <UpdatesWidget w={w === undefined ? "100%" : w} /> : id === "news" ? <NewsWidget /> : <CheckWidget />} />
    </div>
    </SkelPage>
    <AddWidget open={add} onClose={() => setAdd(false)} />
    <ResetConfirm open={reset} onClose={() => setReset(false)} />
    </FixedFrame>
  );
}
