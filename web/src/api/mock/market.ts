/* 가상 시장 데이터 생성기 — 종목코드·날짜로 항상 같은 값이 나와요(결정적). 백엔드 연결 후 삭제 */
import type { Candle, ChartRange, Financials, FinQuarter, Health, IndexQuote, MacroRow, MarketEvent, NewsItem, Quote, StockInfo, UpdateItem } from "../types";
import { BY_CODE, UNIVERSE, POPULAR, ONBOARD_PICKS, type UStock } from "./universe";
export { POPULAR, ONBOARD_PICKS };

/* ---------- 난수 · 날짜 ---------- */
const hash = (s: string) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; };
export const rng = (seed: string) => { let a = hash(seed); return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; };
const pick = <T,>(r: () => number, a: T[]) => a[Math.floor(r() * a.length) % a.length];
const pad = (n: number) => String(n).padStart(2, "0");
export const ymd = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const at = (day: string, h: number, m: number) => `${day}T${pad(h)}:${pad(m)}:00+09:00`;

/* 한국 시간 기준 '지금' (테스트에서 바꿀 수 있게) */
let NOW_OVERRIDE: number | null = null;
export const setNow = (t: number | null) => { NOW_OVERRIDE = t; CACHE.clear(); };
export const now = () => new Date(NOW_OVERRIDE ?? Date.now());
const kst = (d: Date) => new Date(d.getTime() + (d.getTimezoneOffset() + 540) * 60000); // 브라우저 시간대와 무관하게 KST 벽시계
const isWeekend = (d: Date) => d.getDay() === 0 || d.getDay() === 6;

/* 최근 거래일 목록 (오래된 → 최근). 오늘 15:30 이전이면 오늘 종가는 아직 없음 — 종가는 어제까지 */
export function tradingDays(n: number): string[] {
  const k = kst(now());
  const d = new Date(k.getFullYear(), k.getMonth(), k.getDate());
  const closed = k.getHours() * 60 + k.getMinutes() >= 15 * 60 + 30;
  if (!closed || isWeekend(d)) d.setDate(d.getDate() - 1);
  const out: string[] = [];
  while (out.length < n) { if (!isWeekend(d)) out.unshift(ymd(d)); d.setDate(d.getDate() - 1); }
  return out;
}
export const lastClose = () => tradingDays(1)[0];

const CACHE = new Map<string, unknown>();
const memo = <T,>(k: string, f: () => T): T => { if (CACHE.has(k)) return CACHE.get(k) as T; const v = f(); CACHE.set(k, v); return v; };

/* 호가 단위 */
const tick = (p: number) => (p < 2000 ? 1 : p < 5000 ? 5 : p < 20000 ? 10 : p < 50000 ? 50 : p < 200000 ? 100 : p < 500000 ? 500 : 1000);
const rt = (p: number) => Math.max(tick(p), Math.round(p / tick(p)) * tick(p));

/* ---------- 종목 ---------- */
export const universe = (): StockInfo[] => UNIVERSE.map(({ base: _b, shares: _s, scale: _c, themes: _t, ...i }) => i);
const U = (code: string): UStock => BY_CODE.get(code) ?? UNIVERSE[0];

/* 일별 종가 260거래일 — 마지막 종가가 기준가 근처 */
function daily(code: string): Candle[] {
  return memo("d" + code + lastClose(), () => {
    const u = U(code), days = tradingDays(260), r = rng("px" + code);
    const vol = u.sector === "바이오" || u.sector === "2차전지" ? 0.024 : u.financial ? 0.012 : 0.018;
    const end = rt(u.base);
    const closes = [end];
    for (let i = 1; i < days.length; i++) {
      const drift = 0.0006 * Math.sin((i + (hash(code) % 50)) / 23);
      closes.unshift(closes[0] / (1 + (r() - 0.5) * 2 * vol + drift));
    }
    const vr = rng("vol" + code), baseVol = (u.shares * 1e6) * 0.0025;
    return days.map((t, i) => {
      const c = rt(closes[i]), o = rt(i ? closes[i - 1] * (1 + (vr() - 0.5) * vol * 0.6) : c);
      const h = rt(Math.max(o, c) * (1 + vr() * vol * 0.5)), l = rt(Math.min(o, c) * (1 - vr() * vol * 0.5));
      const spike = vr() < 0.04 ? 2.4 + vr() * 1.5 : 1;
      return { t, o, h, l, c, v: Math.round(baseVol * (0.6 + vr() * 0.8) * spike) };
    });
  });
}
export function candles(code: string, range: ChartRange): Candle[] {
  const d = daily(code);
  if (range === "1D") return intraday(code);
  const n = range === "1W" ? 5 : range === "1M" ? 22 : range === "3M" ? 66 : 250;
  return d.slice(-n);
}
function intraday(code: string): Candle[] {
  return memo("i" + code + lastClose(), () => {
    const d = daily(code), last = d[d.length - 1], prev = d[d.length - 2], r = rng("in" + code + last.t);
    const n = 78, out: Candle[] = []; let p = prev.c;
    for (let i = 0; i < n; i++) {
      const target = prev.c + (last.c - prev.c) * ((i + 1) / n);
      p = p + (target - p) * 0.35 + (r() - 0.5) * last.c * 0.004;
      const m = 9 * 60 + i * 5, c = i === n - 1 ? last.c : rt(p);
      out.push({ t: `${last.t} ${pad(Math.floor(m / 60))}:${pad(m % 60)}`, o: c, h: c, l: c, c, v: Math.round(last.v / n) });
    }
    return out;
  });
}
export function quote(code: string): Quote {
  return memo("q" + code + lastClose(), () => {
    const u = U(code), d = daily(code), last = d[d.length - 1], prev = d[d.length - 2], y = d.slice(-250);
    const chg = last.c - prev.c, r = rng("qt" + code);
    const eps = u.financial ? Math.round(last.c / (5 + r() * 3)) : Math.round(last.c / (8 + r() * 22));
    const bps = Math.round(last.c / (0.4 + r() * 2.2));
    return {
      stock_code: code, price: last.c, chg, pct: Math.round((chg / prev.c) * 10000) / 100, open: last.o, high: last.h, low: last.l, prev_close: prev.c,
      volume: last.v, value: last.v * last.c, w52_high: Math.max(...y.map((x) => x.h)), w52_low: Math.min(...y.map((x) => x.l)),
      market_cap: Math.round(last.c * u.shares * 1e6), per: Math.round((last.c / eps) * 100) / 100, pbr: Math.round((last.c / bps) * 100) / 100,
      eps, bps, div_yield: Math.round((u.financial ? 3 + r() * 3 : 0.3 + r() * 2.5) * 100) / 100, foreign_pct: Math.round((15 + r() * 40) * 10) / 10,
      as_of: at(last.t, 15, 30),
    };
  });
}
export const closes = (code: string, n: number) => daily(code).slice(-n);

/* ---------- 재무 (최근 12분기, 공시 기준 — 화면은 뒤 8개를 그리고 앞 4개는 전년 동기 비교에 써요) ---------- */
function lastReportedQuarter(): [number, number] {
  const k = kst(now()); let y = k.getFullYear(), q = Math.floor(k.getMonth() / 3); // 이번 분기 직전
  const qEnd = new Date(y, q * 3, 1); if ((k.getTime() - qEnd.getTime()) / 864e5 < 45) q -= 1; // 분기 끝나고 45일 지나야 공시
  if (q <= 0) { y -= 1; q += 4; }
  return [y, q];
}
export function financials(code: string): Financials {
  return memo("f" + code + lastClose(), () => {
    const u = U(code), r = rng("fin" + code);
    let [y, q] = lastReportedQuarter();
    const list: [number, number][] = [];
    for (let i = 0; i < 12; i++) { list.unshift([y, q]); q -= 1; if (q === 0) { y -= 1; q = 4; } }
    const margin = u.sector === "반도체" ? 0.22 : u.sector === "인터넷" || u.sector === "게임" ? 0.16 : u.sector === "바이오" ? 0.3 : u.sector === "조선" ? 0.06 : 0.08;
    const g = (r() - 0.35) * 0.06;
    const all: FinQuarter[] = list.map(([yy, qq], i) => {
      const rev = u.financial ? null : Math.round(u.scale * Math.pow(1 + g, i - 11) * (0.92 + r() * 0.16));
      const opm = margin * (0.7 + r() * 0.6);
      const op = rev == null ? null : Math.round(rev * opm);
      const net = u.financial ? Math.round(u.base * u.shares * 0.0009 * (0.85 + r() * 0.3)) : Math.round(op! * (0.68 + r() * 0.12));
      const eq = (u.financial ? net * 30 : (rev ?? 0) * 2.2);
      return {
        q: `${String(yy).slice(2)}.${qq}Q`, label: `${yy}년 ${qq}분기`, revenue: rev, op, net,
        op_margin: rev ? Math.round((op! / rev) * 1000) / 10 : null, net_margin: rev ? Math.round((net / rev) * 1000) / 10 : null,
        roe: Math.round(((net * 4) / eq) * 1000) / 10, roa: Math.round(((net * 4) / (eq * (u.financial ? 12 : 1.8))) * 1000) / 10,
      };
    });
    const hp = (k: number): Health => u.financial
      ? { debt: Math.round(900 + k * 80 + r() * 300), reserve: Math.round(800 + r() * 900), interest: null, quick: null, current: null }
      : { debt: Math.round(35 + r() * 90 + k * 4), reserve: Math.round(1500 + r() * 30000), interest: Math.round((4 + r() * 40) * 10) / 10, quick: Math.round(80 + r() * 120), current: Math.round(110 + r() * 140) };
    const [ly, lq] = list[list.length - 1];
    return { stock_code: code, quarters: all, health: hp(0), health_prev: hp(1), as_of: `${ly}-${pad(lq * 3)}-30` };
  });
}
/* 직전 4분기 대비 비교용 (차트 툴팁 '전년 같은 분기') */

/* ---------- 소식 (공시 · 뉴스 · 주가) ---------- */
type T = [string, string, string[]]; // 제목, 요약, 태그
const NEWS_T = (n: string, th: string): T[] => [
  [`${n}, ${th} 관련 보도 뒤 거래 늘어`, `${th} 관련 보도가 나온 뒤 ${n} 거래량이 늘었다는 기사예요. 관련 실적이 언제 반영되는지는 공시로 확인할 수 있어요.`, [th, "주가", "거래량", "분석"]],
  [`${n} ${th} 관련 신규 계약 소식`, `${n}이(가) ${th} 관련 신규 계약을 맺었다는 보도예요. 계약 규모와 기간은 공시로 다시 확인할 수 있어요.`, [th, "수주", "공급", "매출"]],
  [`증권가, ${n} ${th} 사업 분석 보고서`, `여러 증권사가 ${th} 흐름과 ${n} 실적의 관계를 다룬 보고서를 냈어요. 숫자는 다음 실적 공시에서 확인할 수 있어요.`, [th, "분석", "실적", "보고서"]],
  [`${n}, ${th} 사업 투자 확대 발표`, `${n}이(가) ${th} 사업에 투자를 늘리겠다고 밝혔어요. 비용이 늘 수 있어 수익성 영향도 함께 볼 만해요.`, [th, "투자", "시설투자"]],
  [`${n} 실적 시즌 앞두고 관망세`, `실적 발표를 앞두고 ${n} 거래가 줄며 주가가 횡보했다는 기사예요.`, ["실적", "주가"]],
  [`외국인, ${n} 보유 비중 늘어`, `외국인 투자자의 ${n} 보유 비중이 며칠째 늘었다는 기사예요.`, ["수급", "주가"]],
  [`${n}, ${th} 시장 경쟁 구도 변화`, `${th} 시장에 참여하는 기업이 늘고 있다는 분석이에요. 가격·점유율 변화는 실적 공시에서 확인할 수 있어요.`, [th, "경쟁", "분석"]],
  [`${n}, 주주환원 정책에 관심`, `시장에서 ${n}의 배당·자사주 정책에 관심이 커지고 있다는 기사예요.`, ["배당", "자사주", "주주환원"]],
];
const DISC_T = (n: string, th: string): T[] => [
  ["단일판매·공급계약 체결", `${n}이(가) ${th} 관련 공급계약을 맺었다고 공시했어요. 계약금액은 최근 매출의 일부 수준이에요.`, ["수주", "공급", "매출", th]],
  ["신규 시설투자 등", `${n}이(가) ${th} 생산능력을 늘리기 위한 시설투자를 결정했다고 공시했어요.`, ["투자", "시설투자", th]],
  ["자기주식 취득 결정", `${n}이(가) 자사주를 사들이기로 결정했다고 공시했어요. 주주환원 정책의 하나예요.`, ["자사주", "주주환원"]],
  ["기업설명회(IR) 개최", `${n}이(가) 실적 설명회를 연다고 공시했어요. 발표 자료는 DART에 함께 올라와요.`, ["실적", "IR"]],
];
const SRC = ["한국경제", "매일경제", "서울경제", "연합뉴스"] as const;

function feed(code: string): UpdateItem[] {
  return memo("u" + code + lastClose(), () => {
    const u = U(code), d = daily(code), days = d.map((x) => x.t).slice(-90), out: UpdateItem[] = [];
    const r = rng("feed" + code);
    const nm = u.name;
    days.forEach((day, i) => {
      const di = d.length - 90 + i, c = d[di], p = d[di - 1];
      const pct = ((c.c - p.c) / p.c) * 100;
      if (r() < 0.42) {
        const th = pick(r, u.themes), [t, s, tags] = pick(r, NEWS_T(nm, th)), src = pick(r, [...SRC]);
        out.push({ id: `${code}-n-${day}`, stock_code: code, kind: "뉴스", title: t, summary: s, at: at(day, 7 + Math.floor(r() * 10), Math.floor(r() * 60)), src, url: "https://search.naver.com/search.naver?where=news&query=" + encodeURIComponent(nm), tags: [...new Set(tags)] });
      }
      if (r() < 0.07) {
        const th = pick(r, u.themes); let [t, s, tags] = pick(r, DISC_T(nm, th));
        if (u.financial && /공급계약|시설투자/.test(t)) [t, s, tags] = DISC_T(nm, th)[2];
        out.push({ id: `${code}-d-${day}`, stock_code: code, kind: "공시", title: t, summary: s, at: at(day, 16, 5 + Math.floor(r() * 50)), src: "DART", url: "https://dart.fss.or.kr", tags, important: true });
      }
      if (Math.abs(pct) >= 3) out.push({ id: `${code}-p-${day}`, stock_code: code, kind: "주가", title: `주가 ${pct > 0 ? "+" : ""}${pct.toFixed(1)}% ${pct > 0 ? "상승" : "하락"}`, summary: `종가 ${c.c.toLocaleString("ko-KR")}원으로 전 거래일보다 ${Math.abs(pct).toFixed(1)}% ${pct > 0 ? "올랐어요" : "내렸어요"}.`, at: at(day, 15, 30), src: "시세", tags: ["주가", pct > 0 ? "상승" : "하락"] });
      else if (c.v > (d[di - 1].v + d[di - 2].v) * 1.2) out.push({ id: `${code}-v-${day}`, stock_code: code, kind: "주가", title: `거래량 급증 (평소의 ${(c.v / ((d[di - 1].v + d[di - 2].v) / 2)).toFixed(1)}배)`, summary: `거래량이 평소보다 크게 늘었어요. 종가는 ${c.c.toLocaleString("ko-KR")}원이에요.`, at: at(day, 15, 30), src: "시세", tags: ["주가", "거래량"] });
    });
    /* 정기 공시: 분기보고서 · 실적 발표 예정 · 배당 */
    const [fy, fq] = lastReportedQuarter();
    const qEnd = new Date(fy, fq * 3, 0), filed = new Date(qEnd.getTime() + 44 * 864e5), annBefore = new Date(qEnd.getTime() + 24 * 864e5);
    const inRange = (dt: Date) => { const s = ymd(dt); return s >= days[0] && s <= days[days.length - 1]; };
    if (inRange(annBefore)) out.push({ id: `${code}-d-ann`, stock_code: code, kind: "공시", title: `${fq}분기 실적 발표가 예정돼 있어요`, summary: `${fq}분기 경영실적(잠정) 발표 일정 공시가 올라왔어요.`, at: at(ymd(annBefore), 17, 5), src: "DART", url: "https://dart.fss.or.kr", tags: ["실적", "보고서", "IR"], important: true });
    if (inRange(filed)) out.push({ id: `${code}-d-q`, stock_code: code, kind: "공시", title: fq === 4 ? "사업보고서 제출" : "분기보고서 제출", summary: `${fy}년 ${fq}분기 보고서가 제출됐어요. 매출·이익과 사업 현황을 확인할 수 있어요.`, at: at(ymd(filed), 16, 30), src: "DART", url: "https://dart.fss.or.kr", tags: ["실적", "보고서"], important: true });
    const divDay = new Date(fy, fq * 3, 6);
    if ((u.financial || u.themes.includes("배당")) && inRange(divDay)) out.push({ id: `${code}-d-div`, stock_code: code, kind: "공시", title: "현금·현물배당 결정", summary: `${nm}이(가) 분기 배당을 결정했다고 공시했어요.`, at: at(ymd(divDay), 16, 0), src: "DART", url: "https://dart.fss.or.kr", tags: ["배당", "주주환원"], important: true });
    return out.sort((a, b) => b.at.localeCompare(a.at));
  });
}
export function updates(codes: string[], sinceDays = 30): UpdateItem[] {
  const cut = tradingDays(sinceDays)[0];
  return codes.flatMap((c) => feed(c)).filter((x) => x.at.slice(0, 10) >= cut).sort((a, b) => b.at.localeCompare(a.at));
}
export const feedAll = (code: string) => feed(code);

/* ---------- 시장 ---------- */
const IDX: Record<string, [string, string, number, number]> = { kospi: ["코스피", "🇰🇷", 2650.35, 0.009], kosdaq: ["코스닥", "🇰🇷", 850.12, 0.012], usd: ["원/달러", "🇺🇸", 1350.2, 0.004] };
function idxDaily(key: string) {
  return memo("x" + key + lastClose(), () => {
    const [, , base, vol] = IDX[key], days = tradingDays(260), r = rng("idx" + key), a = [base];
    for (let i = 1; i < days.length; i++) a.unshift(a[0] / (1 + (r() - 0.5) * 2 * vol));
    return days.map((t, i) => ({ t, c: Math.round(a[i] * 100) / 100 }));
  });
}
export function indices(): IndexQuote[] {
  return (["kospi", "kosdaq", "usd"] as const).map((key) => {
    const d = idxDaily(key), l = d[d.length - 1], p = d[d.length - 2], [name, flag] = IDX[key];
    return { key, name, flag, v: l.c, c: Math.round((l.c - p.c) * 100) / 100, p: Math.round(((l.c - p.c) / p.c) * 10000) / 100, as_of: at(l.t, 15, 30) };
  });
}
export function indexSeries(key: string, range: "1일" | "1주" | "1달" | "1년"): number[] {
  const d = idxDaily(key);
  if (range === "1일") { const r = rng("idi" + key + d[d.length - 1].t), p = d[d.length - 2].c, l = d[d.length - 1].c; let v = p; return Array.from({ length: 40 }, (_, i) => (i === 39 ? l : (v = v + (p + ((l - p) * (i + 1)) / 40 - v) * 0.4 + (r() - 0.5) * l * 0.002))); }
  const n = range === "1주" ? 5 : range === "1달" ? 22 : 250;
  return d.slice(-n).map((x) => x.c);
}
export const indexHistory = (key: string, n: number) => idxDaily(key).slice(-n);
export function macro(): MacroRow[] {
  const r = rng("macro" + lastClose()), s = (x: number) => (x >= 0 ? "+" : "") + x.toFixed(2);
  return [["국고채 3년", `${(2.61 + (r() - 0.5) * 0.1).toFixed(2)}%`, s((r() - 0.5) * 0.06)], ["미국채 10년", `${(4.18 + (r() - 0.5) * 0.1).toFixed(2)}%`, s((r() - 0.5) * 0.06)], ["금 (g)", `${Math.round(128450 * (1 + (r() - 0.5) * 0.02)).toLocaleString("ko-KR")}원`, s((r() - 0.5) * 1.6) + "%"], ["WTI", `$${(71.2 * (1 + (r() - 0.5) * 0.04)).toFixed(1)}`, s((r() - 0.5) * 2) + "%"]].map(([name, v, c]) => ({ name, v, c }));
}
export function news(codes: string[]): NewsItem[] {
  const pool = UNIVERSE.slice(0, 20).map((u) => u.stock_code);
  const all = [...new Set([...codes, ...pool])].flatMap((c) => feed(c).filter((x) => x.kind === "뉴스").slice(0, 6));
  const day = lastClose();
  const mk = rng("mk" + day), ix = indices()[0];
  const market: NewsItem[] = [
    { id: "mk1-" + day, title: `코스피 ${ix.p >= 0 ? "상승" : "하락"} 마감… ${ix.v.toLocaleString("en-US", { minimumFractionDigits: 2 })}`, src: "연합뉴스", at: at(day, 15, 40), url: "https://www.yna.co.kr", stock_codes: [] },
    { id: "mk2-" + day, title: `외국인 수급 ${mk() > 0.5 ? "유입" : "유출"} 전환… 반도체·자동차 거래 늘어`, src: "매일경제", at: at(day, 11, 30), url: "https://www.mk.co.kr", stock_codes: [] },
    { id: "mk3-" + day, title: `원·달러 환율 ${indices()[2].c >= 0 ? "상승" : "하락"} 출발`, src: "연합뉴스", at: at(day, 9, 41), url: "https://www.yna.co.kr", stock_codes: [] },
  ];
  return [...market, ...all.map((x) => ({ id: x.id, title: x.title, src: x.src as NewsItem["src"], at: x.at, url: x.url ?? "", stock_codes: [x.stock_code] }))]
    .filter((x) => (SRC as readonly string[]).includes(x.src)).sort((a, b) => b.at.localeCompare(a.at)).slice(0, 40);
}
export function schedule(codes: string[]): MarketEvent[] {
  const days: string[] = []; const k = kst(now()); const d = new Date(k.getFullYear(), k.getMonth(), k.getDate());
  while (days.length < 10) { d.setDate(d.getDate() + 1); if (!isWeekend(d)) days.push(ymd(d)); }
  const r = rng("sch" + days[0]);
  const ev: MarketEvent[] = [
    { date: days[1], title: "한국은행 금융통화위원회", who: "시장" }, { date: days[3], title: "미국 소비자물가 발표", who: "시장" }, { date: days[6], title: "옵션 만기일", who: "시장" },
    ...codes.slice(0, 3).map((c, i) => ({ date: days[2 + i * 2 + Math.floor(r() * 2)], title: `${U(c).name} 기업설명회`, who: U(c).name })),
  ];
  return ev.sort((a, b) => a.date.localeCompare(b.date));
}
export const info = (code: string): StockInfo | undefined => { const u = BY_CODE.get(code); if (!u) return undefined; const { base: _b, shares: _s, scale: _c, themes: _t, ...i } = u; return i; };
export const themesOf = (code: string) => U(code).themes;
