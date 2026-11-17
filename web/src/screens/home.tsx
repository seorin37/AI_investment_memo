/* 2.1 홈 기본 템플릿 — Figma 3792:67043 home/main 그대로 */
import { FixedFrame } from "./stock";
import { useState, type ReactNode } from "react";
import { cx, PageTitle } from "../kit";
import { useApp } from "../store";
import { FLAG1, FLAG2, FLAG3 } from "../gen/flags";
import { SLogo, Plug12 } from "../fig";
import { CustomPage } from "./custom";
import { NEW_N } from "../data";
import { SkelPage, WidgetFail } from "../x";
import { HomeGrid, EditBar, AddWidget, ResetConfirm, CheckWidget, MarketDetail, FirstMemo } from "./homex";

/* ---------- 시장 카드 ---------- */
type Range = "1일" | "1주" | "1달" | "1년";
const RANGES: Range[] = ["1일", "1주", "1달", "1년"];
/* 1일은 Figma 경로 그대로, 나머지는 예시 (사용자 결정 11.12) */
const MK = [
  { key: "kospi", name: "코스피", flag: FLAG1, v: "2,650.35",
    r: { "1일": ["−12.40 (−0.47%)", "오늘", -1, "M0 6.25L18.9091 0L37.8182 12.5L56.7273 7.5L75.6364 25L94.5455 20L113.455 30L132.364 16.25L151.273 33.75L170.182 27.5L189.091 40L208 35", 24.25, "M0 7.07L18.9 0.82L37.8 13.32L56.7 8.32L75.6 25.82L94.5 20.82L113.4 30.82L132.3 17.07L151.2 34.57L170.1 28.32L189 40.82L208 35.82"],
         "1주": ["+31.80 (+1.21%)", "1주", 1, "M0 34L18.9 30L37.8 33L56.7 25L75.6 27L94.5 20L113.4 22L132.3 14L151.2 17L170.1 9L189 11L208 4", 34],
         "1달": ["+52.10 (+2.01%)", "1달", 1, "M0 30L18.9 36L37.8 26L56.7 31L75.6 20L94.5 24L113.4 16L132.3 21L151.2 12L170.1 15L189 6L208 9", 30],
         "1년": ["+188.40 (+7.65%)", "1년", 1, "M0 38L18.9 33L37.8 35L56.7 27L75.6 30L94.5 21L113.4 24L132.3 15L151.2 18L170.1 10L189 7L208 2", 38] } },
  { key: "kosdaq", name: "코스닥", flag: FLAG2, v: "850.12",
    r: { "1일": ["−4.18 (−0.49%)", "오늘", -1, "M0 2.66667L18.9091 10.6667L37.8182 0L56.7273 16L75.6364 10.6667L94.5455 28L113.455 17.3333L132.364 29.3333L151.273 20L170.182 36L189.091 30.6667L208 40", 20.67, "M0 3.49L18.9 11.49L37.8 0.82L56.7 16.82L75.6 11.49L94.5 28.82L113.4 18.15L132.3 30.15L151.2 20.82L170.1 36.82L189 31.49L208 40.82"],
         "1주": ["−6.02 (−0.70%)", "1주", -1, "M0 8L18.9 4L37.8 12L56.7 10L75.6 18L94.5 15L113.4 22L132.3 19L151.2 27L170.1 25L189 31L208 34", 8],
         "1달": ["+9.44 (+1.12%)", "1달", 1, "M0 32L18.9 28L37.8 34L56.7 24L75.6 27L94.5 19L113.4 23L132.3 15L151.2 19L170.1 11L189 14L208 8", 32],
         "1년": ["−21.30 (−2.44%)", "1년", -1, "M0 10L18.9 6L37.8 14L56.7 9L75.6 19L94.5 13L113.4 24L132.3 18L151.2 28L170.1 23L189 33L208 30", 10] } },
  { key: "usd", name: "원/달러", flag: FLAG3, v: "1,350.20",
    r: { "1일": ["+3.20 (+0.24%)", "오늘", 1, "M0 40L18.9091 34.2857L37.8182 36.5714L56.7273 17.1429L75.6364 22.8571L94.5455 11.4286L113.455 17.1429L132.364 9.14286L151.273 14.8571L170.182 3.42857L189.091 6.85714L208 0", 58, "M0 40.82L18.9 35.11L37.8 37.39L56.7 17.96L75.6 23.68L94.5 12.25L113.4 17.96L132.3 9.96L151.2 15.68L170.1 4.25L189 7.68L208 0.82"],
         "1주": ["−22.10 (−1.61%)", "1주", -1, "M0 4L18.9 9L37.8 6L56.7 14L75.6 11L94.5 19L113.4 16L132.3 24L151.2 21L170.1 29L189 27L208 34", 4],
         "1달": ["+11.80 (+0.88%)", "1달", 1, "M0 30L18.9 34L37.8 27L56.7 29L75.6 22L94.5 25L113.4 18L132.3 21L151.2 15L170.1 17L189 11L208 13", 30],
         "1년": ["+64.50 (+5.02%)", "1년", 1, "M0 38L18.9 35L37.8 30L56.7 32L75.6 24L94.5 27L113.4 19L132.3 22L151.2 13L170.1 16L189 8L208 5", 38] } },
] as const;
export function MarketCardBase({ k, h = 264, usdLabel }: { k: (typeof MK)[number]["key"]; h?: number; usdLabel?: string }) {
  const { askNudge, setX } = useApp();
  const m = MK.find((x) => x.key === k)!;
  const [r, setR] = useState<Range>("1일");
  const d = m.r[r] as readonly [string, string, number, string, number, string?];
  const up = d[2] > 0, col = up ? "#E5484D" : "#2F6BDB";
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
          {d[5] && <path d={d[5]} transform="translate(0 18)" stroke="#747D8D" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" opacity="0.35" vectorEffect="non-scaling-stroke" />}
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
const UPD = [
  { code: "005930", name: "삼성전자", hold: "관심", n: 2, kind: "공시", t: "3분기 실적 발표가 예정돼 있어요", memo: "실적 나오면 다시 보기", mc: "#fff1c1" },
  { code: "000660", name: "SK하이닉스", hold: "보유", n: 3, kind: "뉴스", t: "HBM4 공급 확대 소식이 나왔어요", memo: "요즘 반도체 분위기 좋아 보여", mc: "#d6e6f2" },
  { code: "035420", name: "네이버", hold: "관심", n: 0 },
] as const;
const ArrowSub = () => <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 1.5V6C2 6.53043 2.21071 7.03914 2.58579 7.41421C2.96086 7.78929 3.46957 8 4 8H10M7.5 10.5L10 8L7.5 5.5" stroke="#111111" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
export function UpdatesWidget({ w = 320, h = 472 }: { w?: number | string; h?: number }) {
  const { go, stocks } = useApp();
  const total = stocks.reduce((a, s) => a + (NEW_N[s.code] ?? 0), 0);
  const [sel, setSel] = useState("000660");
  return (
    <div className="flex shrink-0 flex-col items-start gap-3 overflow-hidden rounded-[20px] border border-[#e5e7eb] bg-white p-5" style={{ width: w, height: h }}>
      <div className="flex w-full flex-col items-start gap-[2px]">
        <div className="flex w-full items-center justify-between">
          <p className="whitespace-nowrap text-[17px] font-bold leading-[26px] tracking-[-0.01em] text-[#16171a]">업데이트</p>
          <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7078]">새 소식 {total}건</p>
        </div>
        <p className="w-full text-[13px] leading-[20px] text-[#575b63]">내가 남긴 메모와 이어진 소식이에요</p>
      </div>
      <div className="flex w-full flex-col items-start gap-[10px]">
        {UPD.filter((u) => stocks.some((x) => x.code === u.code)).map((u) => {
          const on = sel === u.code;
          return (
            <button key={u.code} onMouseEnter={() => setSel(u.code)} onFocus={() => setSel(u.code)} onClick={() => go({ name: "updates", code: u.code })}
              className={cx("flex w-full flex-col items-start gap-[10px] rounded-[14px] p-[14px] text-left transition-colors", on ? "bg-[#f8f8f8] shadow-[inset_0_0_0_1.5px_#111111]" : "bg-white shadow-[inset_0_0_0_1px_#e5e7eb]")}>
              <div className="flex w-full items-center gap-2">
                <SLogo code={u.code} size={28} r={8.4} />
                <p className="whitespace-nowrap text-[15px] font-bold leading-[23px] text-[#16171a]">{u.name}</p>
                <span className="rounded-[6px] bg-[#f3f4f6] px-[6px] py-[2px] text-[13px] font-medium leading-[20px] text-[#575b63]">{u.hold}</span>
                <span className="h-1 min-w-0 flex-1" />
                {u.n ? <span className="grid h-[22px] w-[22px] place-items-center rounded-full bg-[#e45d6a] text-[13px] font-bold leading-none text-white">{u.n}</span> : <span className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7078]">모두 확인했어요</span>}
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
      <button onClick={() => go({ name: "updates" })} className="w-[200px] text-left text-[13px] font-bold leading-[20px] tracking-[-0.01em] text-[#111111] underline">전체 업데이트 보기  →</button>
    </div>
  );
}

/* ---------- 뉴스 ---------- */
const NEWS: [string, string, string][] = [["12:48", "SK하이닉스, HBM4 공급 확대 기대감에 강세", "한국경제"], ["11:30", "외국인, 이틀 연속 반도체 순매수", "매일경제"], ["10:05", "3분기 실적 시즌 개막… IT·반도체 주목", "서울경제"], ["09:41", "원·달러 환율, 하락 출발", "연합뉴스"], ["08:52", "삼성전자, 실적 발표 앞두고 관망세", "한국경제"]];
export function NewsWidget({ h = 472, className }: { h?: number; className?: string }) {
  return (
    <div className={cx("flex min-w-0 flex-1 flex-col items-start gap-2 overflow-hidden rounded-[20px] border border-[#e5e7eb] bg-white px-6 pb-[14px] pt-[18px]", className)} style={{ height: h }}>
      <div className="flex w-full items-center justify-between">
        <p className="whitespace-nowrap text-[17px] font-bold leading-[26px] text-[#15171a]">뉴스</p>
        <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7078]">오늘 · 8건</p>
      </div>
      <div className="flex w-full flex-col items-start gap-2 rounded-[12px] bg-[#f3f4f6] px-[14px] py-3">
        <div className="flex w-full items-center justify-between">
          <span className="flex items-center rounded-[10px] border border-[#e5e7eb] bg-white px-2 py-[2px] text-[13px] font-medium leading-[20px] text-[#575b63]">연합뉴스</span>
          <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7078]">13:12 · 방금</p>
        </div>
        <p className="w-full text-[17px] font-bold leading-[26px] text-[#15171a]">반도체 강세에 코스피 상승 출발</p>
        <p className="whitespace-nowrap text-[13px] font-bold leading-[20px] text-[#111111] underline">원문 읽기 ↗</p>
      </div>
      <div className="flex w-full flex-col items-start">
        {NEWS.map(([t, h2, s]) => (
          <div key={t} className="flex w-full items-start gap-[10px] border-t border-[#e5e7eb] px-[2px] py-[9px]">
            <p className="w-[38px] shrink-0 text-[13px] leading-[20px] text-[#6b7078]">{t}</p>
            <div className="flex min-w-0 flex-1 flex-col items-start gap-[2px]">
              <p className="w-full text-[14px] font-medium leading-[21px] text-[#15171a]">{h2}</p>
              <p className="whitespace-nowrap text-[13px] font-medium leading-[20px] text-[#575b63]">{s}</p>
            </div>
            <p className="whitespace-nowrap text-[14px] font-medium leading-[21px] text-[#6b7078]">↗</p>
          </div>
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
  const { stocks, go } = useApp();
  const rows = stocks.map((s) => [s.name, NEW_N[s.code] ?? 0] as const).filter(([, n]) => n > 0);
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
  const mk = MK.find((m) => m.key === x.market) as unknown as Parameters<typeof MarketDetail>[0]["m"];
  return <MarketDetail m={x.market ? mk : null} onClose={() => setX((v) => ({ ...v, market: null }))} />;
}
export function HomePage() {
  const { homeMode, x } = useApp();
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
