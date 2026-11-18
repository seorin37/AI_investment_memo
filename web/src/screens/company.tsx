/* 7 · 기업 정보 — Figma 2.5 (7 · 7.1 도움말 · 7.2 그래프 호버) 그대로. 숫자는 모두 api(시세·재무)에서 받아요 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { cx } from "../kit";
import { api } from "../api";
import type { Candle, Financials as Fin, Quote as QuoteT } from "../api/types";
import { mmdd } from "../store";
import type { Stock } from "../data";

const won = (n: number) => Math.round(n).toLocaleString("ko-KR");
const jo = (eok: number) => { const neg = eok < 0, a = Math.abs(Math.round(eok)), j = Math.floor(a / 10000), r = a % 10000; return (neg ? "-" : "") + (j && r ? `${j}조 ${r.toLocaleString("ko-KR")}억원` : j ? `${j}조원` : `${r.toLocaleString("ko-KR")}억원`); };

/* ---------- 7 머리 (큰 머리) ---------- */
export function BigHead({ s }: { s: Stock }) {
  const up = s.chg >= 0, c = up ? "#E5484D" : "#2F6BDB";
  const pts = useMemo(() => {
    const a = (api.market.closes(s.stock_code, 12) as Candle[]).map((x) => x.c), mn = Math.min(...a), mx = Math.max(...a);
    return a.map((v, i) => [1.25 + (i / 11) * 140, 1.25 + ((mx - v) / (mx - mn || 1)) * 41] as const);
  }, [s.stock_code, s.price]);
  const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(2) + " " + p[1].toFixed(2)).join("");
  const area = pts.map((p, i) => (i ? "L" : "M") + (p[0] - 1.25).toFixed(2) + " " + (p[1] - 2.25).toFixed(2)).join("") + "V51H0Z";
  const end = pts[pts.length - 1], start = pts[2];
  return (
    <div className="flex h-24 w-full shrink-0 items-start justify-between pr-2">
      <div className="flex h-[86px] w-[230px] flex-col items-start gap-[10px]">
        <div className="flex items-center gap-3">
          <div className="dk-keep flex h-10 w-10 items-center justify-center rounded-[12px]" style={{ background: s.logo_bg }}><p className="text-center font-bold leading-none" style={{ fontSize: s.logo.length > 2 ? 11 : s.logo.length > 1 ? 13.6 : 17, color: s.logo_ink ?? "#fff" }}>{s.logo}</p></div>
          <p className="whitespace-nowrap text-[36px] font-bold leading-[40px] text-[#191f28]">{s.name}</p>
        </div>
        <div className="flex items-center gap-2">
          <p className="whitespace-nowrap text-[14px] leading-[21px] text-[#6b7684]">{s.stock_code} · {s.market}</p>
          <div className="flex items-center rounded-[6px] bg-[#e8edf5] px-[10px] py-1"><p className="whitespace-nowrap text-[14px] font-medium leading-[21px] text-black">{s.hold === "보유" ? "보유 중" : "관심"}</p></div>
        </div>
      </div>
      <div className="flex h-[78px] w-[330px] items-center gap-6">
        <div className="flex h-[76px] w-[156px] flex-col items-end gap-[2px]">
          <p className="w-[156px] text-center text-[32px] font-bold leading-[40px] text-[#191f28]">{won(s.price)}원</p>
          <p className="w-[156px] whitespace-pre text-center text-[17px] font-bold leading-[26px]" style={{ color: up ? "#e5484d" : "#2f6bdb" }}>{up ? "+" : "-"}{won(Math.abs(s.chg))}  {up ? "+" : "-"}{Math.abs(s.pct).toFixed(2)}%</p>
          <p className="w-[156px] text-center text-[13px] leading-[20px] text-[#6b7684]">{mmdd(s.as_of)} 종가 기준</p>
        </div>
        <div className="relative h-[60px] w-[150px] shrink-0">
          <svg className="absolute left-1 top-[5px]" width="140" height="51" viewBox="0 0 140 51" fill="none"><path d={area} fill={c} fillOpacity="0.11" /></svg>
          <svg className="absolute left-1 top-[54px]" width="140" height="1" viewBox="0 0 140 1" fill="none"><line y1="0.5" x2="140" y2="0.5" stroke="#94A1B0" strokeOpacity="0.5" strokeDasharray="3 4" /></svg>
          <svg className="absolute left-1 top-[7px] overflow-visible" width="143" height="44" viewBox="0 0 143 44" fill="none"><path className="m-line" pathLength={400} d={line} stroke={c} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
          {<div className="absolute h-2 w-2 rounded-full border-2 border-[#4f5c6e] bg-white" style={{ left: 4 + start[0] - 4, top: 7 + start[1] - 4 }} />}
          <div className="absolute h-5 w-5 rounded-full" style={{ left: 4 + end[0] - 11.25, top: 7 + end[1] - 11.25, background: up ? "rgba(229,72,77,0.18)" : "rgba(47,107,219,0.18)" }} />
          <div className="absolute h-3 w-3 rounded-full border-2 bg-white" style={{ left: 4 + end[0] - 7.25, top: 7 + end[1] - 7.25, borderColor: c }} />
          <div className="absolute h-[6px] w-[6px] rounded-full" style={{ left: 4 + end[0] - 4.25, top: 7 + end[1] - 4.25, background: c }} />
        </div>
      </div>
    </div>
  );
}

/* ---------- 공통 ---------- */
/* 11.13: 기업 화면 860px 고정 — Figma 7(690)을 가로만 넓힘. 글자 크기·세로 배치는 그대로 */
const CW = 860, IW = 810;            // 카드 폭, 카드 안쪽 폭 (Figma 690 / 640)
const FX = IW / 640;                 // 실적·수익성·건전성 안쪽 가로 비율
const PX = 816 / 646;                // 주가 차트 가로 비율
const QX = CW / 690;                 // 시세정보 카드 가로 비율
const Card = ({ children, className, style }: { children: ReactNode; className?: string; style?: React.CSSProperties }) => (
  <div className={cx("relative w-[860px] shrink-0 rounded-[16px] border border-[#e5e8eb] bg-white", className)} style={style}>{children}</div>
);
const TIPBOX = "absolute z-30 rounded-[16px] border border-[#deeaf5] bg-white shadow-[0px_8px_24px_0px_rgba(31,46,84,0.1)]";
type TipCtl = { open: string | null; set: (k: string | null) => void };
function HelpBtn({ k, ctl, size = 14, className }: { k: string; ctl: TipCtl; size?: 14 | 16 | 18; className?: string }) {
  return (
    <button data-tip aria-label={`${k} 설명`} aria-expanded={ctl.open === k} onClick={(e) => { e.stopPropagation(); ctl.set(ctl.open === k ? null : k); }}
      className={cx("flex shrink-0 items-center justify-center rounded-full border border-[#e8ecf3] bg-[#eef3f8] hover:bg-[#e3eaf2]", className)} style={{ width: size, height: size }}>
      <span className={cx("text-center font-bold leading-[20px] text-[#747d8d]", size === 14 ? "text-[11px]" : "text-[13px]")}>?</span>
    </button>
  );
}
const X = ({ onClick }: { onClick: () => void }) => <button aria-label="닫기" onClick={(e) => { e.stopPropagation(); onClick(); }} className="shrink-0 whitespace-nowrap text-[20px] leading-[29px] text-[#747d8d] hover:text-[#191f28]">×</button>;

/* ---------- 기업 개요 ---------- */

const overview = (s: Stock) => api.market.info(s.stock_code)?.about ?? (() => { const i = api.market.info(s.stock_code); return i ? `${i.overview}이에요. ${i.sector} 업종으로, 업황과 실적 발표에 따라 주가가 움직이는 종목이에요.` : `${s.name}은(는) ${s.market}에 상장된 기업이에요.`; })();

/* ---------- 주가 · 거래량 (Figma 캔들 그대로 · 안내선은 마우스 따라) ---------- */
const GRID_Y = [17.6, 57.1, 96.6, 136.2, 175.7], GRID_X = [4, 101, 199, 296, 393, 491, 588];
const NC = 42; // 캔들 수 (약 두 달)
function PriceChart({ s }: { s: Stock }) {
  const cs = useMemo(() => (api.market.candles(s.stock_code, "3M") as Candle[]).slice(-NC), [s.stock_code, s.price]);
  const lo0 = Math.min(...cs.map((c) => c.l)), hi0 = Math.max(...cs.map((c) => c.h)), padP = (hi0 - lo0) * 0.08;
  const lo = lo0 - padP, hi = hi0 + padP, vmax = Math.max(...cs.map((c) => c.v));
  const PY = (p: number) => GRID_Y[0] + ((hi - p) / (hi - lo)) * (GRID_Y[4] - GRID_Y[0]);
  const CXp = (i: number) => 11 + (i * (581 - 11)) / (NC - 1);
  const CANDLES = cs.map((c, i) => { const up = c.c >= c.o; const bt = PY(Math.max(c.o, c.c)), bb = PY(Math.min(c.o, c.c)); const vh = Math.max(2, (c.v / vmax) * 48); return [CXp(i), PY(c.h), Math.max(1, PY(c.l) - PY(c.h)), 0, bt, Math.max(1.2, bb - bt), 244 - vh, vh, up ? 1 : 0]; });
  const PRICE_LBL = [0, 1, 2, 3, 4].map((k) => { const v = hi - ((hi - lo) * k) / 4; return [Math.round(v / (v > 100000 ? 1000 : v > 10000 ? 100 : 10)) * (v > 100000 ? 1000 : v > 10000 ? 100 : 10), GRID_Y[k] - 5.6] as const; });
  const DATES = [0, 1, 2, 3, 4, 5].map((k) => { const i = Math.round((k * (NC - 1)) / 5.3); return [mmdd(cs[i].t + "T12:00:00+09:00"), CXp(i) - 7] as const; });
  const last = cs.length - 1;
  const [hov, setHov] = useState<{ i: number; y: number } | null>(null);
  const ref = useRef<SVGSVGElement>(null);
  const move = (e: React.MouseEvent) => {
    const b = ref.current!.getBoundingClientRect(), z = b.width / 816, mx = (e.clientX - b.left) / z / PX, my = (e.clientY - b.top) / z;
    if (mx < 4 || mx > 588) return;
    const i = Math.max(0, Math.min(last, Math.round(((mx - 11) / (581 - 11)) * (NC - 1))));
    setHov({ i, y: Math.max(GRID_Y[0], Math.min(GRID_Y[4], my)) });
  };
  const hi_ = hov ?? { i: last, y: PY(cs[last].c) };
  const hx = CXp(hi_.i), pv = hov ? hi - ((hi_.y - GRID_Y[0]) / (GRID_Y[4] - GRID_Y[0])) * (hi - lo) : cs[last].c;
  const price = won(Math.round(pv / (pv > 100000 ? 500 : pv > 10000 ? 50 : 5)) * (pv > 100000 ? 500 : pv > 10000 ? 50 : 5));
  const date = cs[hi_.i].t;
  return (
    <Card className="h-[349px]">
      <div className="absolute left-[22px] top-[25px] h-[300px] w-[816px]">
        <p className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#191f28]">주가 · 거래량</p>
        <div className="absolute left-0 top-[34px] h-[266px] w-[816px]">
          <svg ref={ref} data-price-chart width="816" height="266" viewBox="0 0 816 266" className="absolute inset-0 cursor-crosshair" onMouseMove={move} onMouseLeave={() => setHov(null)}>
            {GRID_Y.map((y) => <rect key={y} x={4 * PX} y={y} width={584 * PX} height="1" fill="#e5ebf2" />)}
            {GRID_X.map((x) => <rect key={x} x={x * PX} y="17.6" width="0.6" height="158.1" fill="#e5ebf2" />)}
            <rect x={4 * PX} y="244" width={584 * PX} height="1" fill="#e5ebf2" />
            {CANDLES.map((k, i) => { const col = k[8] ? "#f04545" : "#3b82f5"; return (
              <g key={i}>
                <rect x={k[0] * PX} y={k[1]} width="0.6" height={k[2]} fill={col} />
                <rect x={k[0] * PX + 0.3 - 5} y={k[4]} width="10" height={k[5]} rx="1" fill={col} />
                <rect x={k[0] * PX + 0.3 - 5} y={k[6]} width="10" height={k[7]} rx="1" fill={col} />
              </g>
            ); })}
            <rect x={hx * PX - 0.3} y="15.2" width="0.6" height="228.8" fill="#7a8594" fillOpacity="0.55" />
            <rect x={4 * PX} y={hi_.y - 0.5} width={584 * PX} height="1" fill="#7a8594" fillOpacity="0.55" />
            <ellipse cx={hx * PX} cy={hi_.y - 1.1} rx="2.4" ry="4" fill="#fff" stroke="#141a24" strokeWidth="2" />
          </svg>
          {PRICE_LBL.map(([v, y]) => <p key={v} className="pointer-events-none absolute w-[37px] whitespace-nowrap text-[11px] leading-[16px] text-[#6b788c]" style={{ top: y, left: 596 * PX }}>{won(v)}</p>)}
          <p className="pointer-events-none absolute left-1 top-[184px] whitespace-nowrap text-[13px] font-medium leading-[20px] text-[#141a24]">거래량</p>
          <p className="pointer-events-none absolute left-10 top-[184px] whitespace-nowrap text-[13px] font-bold leading-[20px] text-[#6b788c]">{won(cs[hi_.i].v)}</p>
          {DATES.map(([t, x]) => <p key={t} className="pointer-events-none absolute top-[254px] w-[25px] whitespace-nowrap text-[11px] leading-[16px] text-[#6b788c]" style={{ left: x * PX }}>{t}</p>)}
          <div className="pointer-events-none absolute flex h-5 w-[57px] items-center justify-center rounded-[4px] bg-[#383b40]" style={{ top: hi_.y - 12.8, left: 589 * PX }}><p className="text-[13px] font-bold leading-[20px] text-white">{price}</p></div>
          <div className="pointer-events-none absolute top-[247px] flex h-5 w-[68px] items-center justify-center rounded-[4px] bg-[#383b40]" style={{ left: hx * PX - 34 }}><p className="text-[11px] font-medium leading-[16px] text-white">{date}</p></div>
        </div>
      </div>
    </Card>
  );
}

/* ---------- 시세정보 · 투자정보 ---------- */
const HELP_SMALL: Record<string, [string, string]> = {
  PER: ["PER · 주가수익비율", "이익에 비해 주가가 얼마나 높은지 보여줘요.\n계산: 주가 ÷ 주당순이익(EPS)"],
  EPS: ["EPS · 주당순이익", "회사가 벌어들인 순이익 중 보통주 한 주에 해당하는 금액이에요.\n계산: 최근 4개 분기 순이익 합 ÷ 주식 수"],
  PBR: ["PBR · 주가순자산비율", "순자산에 비해 주가가 얼마나 높은지 보여줘요.\n계산: 주가 ÷ 주당순자산(BPS)"],
  BPS: ["BPS · 주당순자산", "자산에서 부채를 뺀 순자산 중 보통주 한 주에 해당하는 금액이에요.\n계산: 최근 분기 자본총계 ÷ 주식 수"],
  시가총액: ["시가총액", "주식시장에서 평가하는 기업의 전체 주식 가치예요.\n계산: 현재 주가 × 상장주식 수"],
  상장주수: ["상장주수", "거래소에 상장된 주식의 총수예요. 실제 시장에서 거래 가능한 유통주식 수와는 다를 수 있어요."],
};
function Quote({ s, ctl }: { s: Stock; ctl: TipCtl }) {
  const q = api.market.quote(s.stock_code) as QuoteT;
  const shares = Math.round(q.market_cap / q.price);
  const L: [string, string, boolean][] = [["전일", won(q.prev_close), false], ["시가", won(q.open), q.open > q.prev_close], ["고가", won(q.high), q.high > q.prev_close], ["저가", won(q.low), q.low > q.prev_close], ["거래량", won(q.volume) + "주", false], ["거래대금", won(q.value / 1e8) + "억원", false]];
  const R: [string, string][] = [["PER", q.per == null ? "—" : q.per.toFixed(2) + "배"], ["EPS", q.eps == null ? "—" : won(q.eps) + "원"], ["PBR", q.pbr == null ? "—" : q.pbr.toFixed(2) + "배"], ["BPS", q.bps == null ? "—" : won(q.bps) + "원"], ["시가총액", jo(q.market_cap / 1e8)], ["상장주수", won(shares) + "주"]];
  const lo = q.w52_low, hi = q.w52_high, pos = (q.price - lo) / (hi - lo || 1);
  const cell = (k: string, v: string, red?: boolean, help?: boolean) => (
    <div key={k} className="relative flex min-w-0 flex-1 items-center justify-between border-b border-[#e5e8eb] py-[7px]">
      <div className="flex items-center gap-1"><p className="whitespace-nowrap text-[13px] font-medium leading-[20px] text-[#6b7684]">{k}</p>{help && <HelpBtn k={k} ctl={ctl} />}</div>
      <p className="whitespace-nowrap text-[13px] font-bold leading-[20px]" style={{ color: red ? "#e5484d" : "#191f28" }}>{v}</p>
      {help && ctl.open === k && (
        <div data-tipbox className={cx(TIPBOX, "left-[-12px] top-[30px] flex w-[218px] flex-col items-start gap-[6px] p-3")} onClick={(e) => e.stopPropagation()}>
          <div className="flex h-5 w-[194px] items-center justify-between"><p className="min-w-0 flex-1 text-[13px] font-bold leading-[20px] text-[#477bff]">{HELP_SMALL[k][0]}</p><X onClick={() => ctl.set(null)} /></div>
          <p className="w-[194px] whitespace-pre-line text-[13px] leading-[20px] text-[#747d8d]">{HELP_SMALL[k][1]}</p>
        </div>
      )}
    </div>
  );
  return (
    <Card className="h-[230px]">
      <div className="absolute left-[21.56px] top-6 flex flex-col items-start gap-[3px]" style={{ width: 270 * QX }}>
        <div className="relative h-[68px] w-full"><p className="absolute left-0 top-5 whitespace-nowrap pb-[2px] text-[20px] font-bold leading-[29px] text-[#191f28]">시세정보 · 투자정보</p></div>
        {[0, 2, 4].map((i) => <div key={i} className="flex w-full items-start gap-5">{cell(L[i][0], L[i][1], L[i][2])}{cell(L[i + 1][0], L[i + 1][1], L[i + 1][2])}</div>)}
      </div>
      <p style={{ left: 343.82 * QX }} className="absolute top-10 w-[46px] whitespace-nowrap text-right text-[13px] leading-[20px] text-[#6b788c]">52주 최저</p>
      <p style={{ left: 339.33 * QX }} className="absolute top-[55px] w-[51px] whitespace-nowrap text-right text-[13px] font-bold leading-[20px] text-[#141a24]">{won(lo)}</p>
      <p style={{ left: 627.11 * QX }} className="absolute top-10 w-[46px] whitespace-nowrap text-[13px] leading-[20px] text-[#6b788c]">52주 최고</p>
      <p style={{ left: 627.11 * QX }} className="absolute top-[55px] w-[51px] whitespace-nowrap text-[13px] font-bold leading-[20px] text-[#141a24]">{won(hi)}</p>
      <div className="absolute top-[54px] h-[6px] rounded-[3px] bg-[#d1d6de]" style={{ left: 396.33 * QX, width: 220 * QX + (QX - 1) * 6 }} />
      <div className="absolute top-[46px] flex h-[22px] w-[67px] items-center justify-center rounded-[11px] bg-[#383b40]" style={{ left: 396.33 * QX + Math.max(0, Math.min(1.74, pos / 0.254)) * 22.36 * QX }}><p className="text-[13px] font-bold leading-[20px] text-white">{won(s.price)}</p></div>
      <div className="absolute top-[94px] flex flex-col items-start gap-[3px]" style={{ left: 307.56 * QX, width: 358.44 * QX + (QX - 1) * 24 }}>
        {[0, 2, 4].map((i) => <div key={i} className="flex w-full items-start gap-3">{cell(R[i][0], R[i][1], false, true)}{cell(R[i + 1][0], R[i + 1][1], false, true)}</div>)}
      </div>
    </Card>
  );
}

/* ---------- 실적 (매출 · 영업이익 · 당기순이익) — 11.16 앱 통일: 분기 8개(24.3Q~26.2Q) · 전년 동기 대비 선 · 값이 없으면(null) — ---------- */
type FinK = "매출" | "영업이익" | "당기순이익";
const FQ: Record<FinK, { color: string; key: "revenue" | "op" | "net"; help: [string, string, string] }> = {
  매출: { color: "#b9aed8", key: "revenue", help: ["매출이란?", "상품을 팔거나 서비스를 제공해 벌어들인 금액이에요. 아직 비용을 빼기 전의 금액으로, 기업의 사업 규모를 보여줘요.", "한눈에 · 얼마나 팔았나요?"] },
  영업이익: { color: "#51c38b", key: "op", help: ["영업이익이란?", "매출에서 제품을 만드는 비용과 판매·관리에 든 비용을 뺀 이익이에요. 본업으로 얼마나 벌었는지 보여주며, 금액이 음수라면 영업손실이에요.", "한눈에 · 본업으로 얼마나 남겼나요?"] },
  당기순이익: { color: "#e8cf7e", key: "net", help: ["당기순이익이란?", "모든 수익과 비용, 법인세까지 반영한 최종 이익이에요. 본업 외의 손익도 포함하며, 금액이 음수라면 당기순손실이에요.", "한눈에 · 최종적으로 얼마나 남았나요?"] },
};
/* 금융업은 매출·영업이익을 공시하지 않아 null → 화면엔 — 로 (11.16 사용자 결정: 금융업 화면은 따로 만들지 않음) */
const useFin = (code: string) => useMemo(() => api.market.financials(code) as Fin, [code]);
/* 화면 단위: 조 원 (값은 억 원으로 와요) */
const finVals = (f: Fin, k: FinK) => f.quarters.slice(-8).map((q) => (q[FQ[k].key] == null ? null : (q[FQ[k].key] as number) / 10000));
const yoyOf = (f: Fin, k: FinK) => { const all = f.quarters.map((q) => q[FQ[k].key]), n = all.length; return all.slice(-8).map((v, i) => { const p = all[n - 8 + i - 4]; return v == null || p == null || !p ? null : (v / p - 1) * 100; }); };
const CX0 = 70 * FX, CX1 = 631 * FX, CY0 = 16, CY1 = 218, BW = 46, TIP_W = 159, TIP_H = 94;
const qx = (i: number) => CX0 + ((CX1 - CX0) / 8) * (i + 0.5);
const tipLeft = (i: number) => (qx(i) + BW / 2 + 10 + TIP_W <= 810 ? qx(i) + BW / 2 + 10 : qx(i) - BW / 2 - 10 - TIP_W);
function Financials({ s, ctl }: { s: Stock; ctl: TipCtl }) {
  const [k, setK] = useState<FinK>("매출");
  const [h, setH] = useState<number | null>(null);
  const fin = useFin(s.stock_code), Q8 = fin.quarters.slice(-8), QL = Q8.map((q) => q.q), QF = Q8.map((q) => q.label);
  const F = FQ[k], vals = finVals(fin, k), yoy = yoyOf(fin, k);
  const nums = vals.filter((x): x is number => x != null), max = nums.length ? Math.max(...nums) : 1;
  const step = Math.pow(10, Math.floor(Math.log10(max))) * (max / Math.pow(10, Math.floor(Math.log10(max))) > 5 ? 2 : 1);
  const top = Math.ceil(max / step) * step, ticks = nums.length ? Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step) : [0];
  const y = (v: number) => CY1 - (v / top) * (CY1 - CY0);
  const ys = yoy.filter((x): x is number => x != null), yMax = Math.max(1, ...ys.map(Math.abs));
  const ly = (p: number) => CY0 + 8 + ((yMax - p) / (2 * yMax)) * (CY1 - CY0 - 16);
  const last = vals[7], lastY = yoy[7];
  const lbl = (n: number) => (n === 0 ? "0" : n >= 1 ? `${Number.isInteger(n) ? n : n.toFixed(1)}조` : `${Math.round(n * 10000).toLocaleString("ko-KR")}억`);
  const tipTop = (i: number) => Math.max(0, Math.min(226 - TIP_H, (vals[i] == null ? CY1 : y(vals[i] as number)) - TIP_H / 2));
  const line = yoy.map((p, i) => (p == null ? null : [qx(i), ly(p)] as const));
  return (
    <Card className="flex flex-col items-start gap-5 p-6">
      <div className="flex h-[26px] w-[810px] items-center justify-between">
        <div className="relative flex items-center gap-2">
          <p className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#191f28]">실적</p>
          <HelpBtn k="fin" ctl={ctl} size={18} />
          {ctl.open === "fin" && (
            <div data-tipbox className={cx(TIPBOX, "left-[14px] top-[32px] flex w-[280px] flex-col items-start gap-[14px] px-5 py-[18px]")} onClick={(e) => e.stopPropagation()}>
              <svg className="absolute left-7 top-[-9px]" width="18" height="10" viewBox="0 0 18 10" fill="none"><path d="M1 10L7 3C8.33333 1.66667 9.66667 1.66667 11 3L17 10" fill="white" /><path d="M1 10L7 3C8.33333 1.66667 9.66667 1.66667 11 3L17 10" stroke="#DEEAF5" /></svg>
              <div className="flex h-6 w-[240px] items-center justify-between"><p className="w-[222px] text-[17px] font-bold leading-[26px] text-[#477bff]">{F.help[0]}</p><X onClick={() => ctl.set(null)} /></div>
              <p className="w-[240px] text-[13px] leading-[20px] text-[#747d8d]">{F.help[1]}</p>
              <div className="flex rounded-[9px] bg-[#eef3f8] px-3 py-[10px]"><p className="w-[216px] text-[13px] leading-[20px] text-[#477bff]">{F.help[2]}</p></div>
            </div>
          )}
        </div>
        <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">{QF[7]} 기준 · 연결재무제표 · 분기</p>
      </div>
      <div className="flex h-12 items-start gap-1 rounded-[24px] bg-[#f2f3f5] p-1">
        {(Object.keys(FQ) as FinK[]).map((t) => <button key={t} onClick={() => { setK(t); setH(null); }} className={cx("flex h-10 items-center rounded-[20px] px-5 text-[15px] font-medium leading-[23px] transition-colors", k === t ? "bg-black text-white" : "text-[#8f8f8f] hover:text-[#191f28]")}>{t}</button>)}
      </div>
      <div className="flex h-[43px] w-[810px] items-center gap-6">
        <div className="flex flex-col items-start gap-[6px]"><p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">{QF[7]} {k}</p><p data-fin-last className="whitespace-nowrap text-[14px] font-bold leading-[21px] text-[#191f28]">{last == null ? "—" : jo(last * 10000)}</p></div>
        <div className="flex flex-col items-start gap-[6px]"><p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">{fin.quarters[fin.quarters.length - 5].label} 대비</p><p className="whitespace-nowrap text-[14px] font-bold leading-[21px]" style={{ color: lastY == null ? "#191f28" : lastY >= 0 ? "#ff3d45" : "#477aff" }}>{lastY == null ? "—" : `${lastY >= 0 ? "+" : ""}${lastY.toFixed(2)}%`}</p></div>
        {!nums.length && <p className="ml-auto text-[13px] leading-[20px] text-[#8b95a1]">이 회사는 {k}을 공시하지 않아요 · 값이 없으면 — 로 보여요</p>}
      </div>
      <div key={k} className="relative h-[246px] w-[810px]" onMouseLeave={() => setH(null)}>
        <svg width="810" height="246" viewBox="0 0 810 246" className="absolute inset-0">
          {ticks.map((t) => <rect key={t} x={CX0} y={y(t)} width={CX1 - CX0} height="1" fill={t === 0 ? "#b8bfc8" : "#e5e8eb"} />)}
          {vals.map((v, i) => v == null ? null : <rect key={i} className="m-bar-grow" x={qx(i) - BW / 2} y={y(v)} width={BW} height={CY1 - y(v)} rx="2" fill={F.color} opacity={h === null || h === i ? 1 : 0.55} style={{ transformOrigin: `0 ${CY1}px` }} />)}
          {line.some(Boolean) && <path className="m-line" pathLength={400} d={line.filter(Boolean).map((p, i) => (i ? "L" : "M") + p![0] + " " + p![1]).join("")} stroke="#33404b" strokeWidth="1.6" fill="none" />}
          {line.map((p, i) => p && <ellipse key={i} cx={p[0]} cy={p[1]} rx="3" ry="3.5" fill="#fff" stroke="#33404b" strokeWidth="1.5" />)}
        </svg>
        {ticks.map((t) => <p key={t} style={{ top: y(t) - 6, left: 20 * FX - 18 }} className="absolute w-[46px] text-right text-[11px] leading-[16px] text-[#6b788c]">{lbl(t)}</p>)}
        {!nums.length && <p className="absolute left-1/2 top-[100px] -translate-x-1/2 text-[28px] font-bold text-[#c9ccd2]">—</p>}
        {QL.map((q, i) => <p key={q} className="absolute top-[230px] w-12 whitespace-nowrap text-center text-[11px] leading-[16px] text-[#6b788c]" style={{ left: qx(i) - 24 }}>{q}</p>)}
        {QL.map((_, i) => <div key={"h" + i} data-fin-bar={i} className="absolute top-0 h-[226px] cursor-pointer" style={{ left: qx(i) - (CX1 - CX0) / 16, width: (CX1 - CX0) / 8 }} onMouseEnter={() => setH(i)} />)}
        {h !== null && (
          <div data-fintip={h} className="m-pop pointer-events-none absolute z-20 flex w-[159px] flex-col items-start gap-1 rounded-[16px] border border-[#deeaf5] bg-white px-3 py-[10px] shadow-[0px_8px_24px_0px_rgba(31,46,84,0.1)]" style={{ left: tipLeft(h), top: tipTop(h) }}>
            <div className="pointer-events-auto flex h-5 w-full items-center justify-between"><p className="text-[13px] font-bold leading-[20px] text-[#477bff]">{QF[h]}</p><X onClick={() => setH(null)} /></div>
            <p className="whitespace-nowrap text-[17px] font-bold leading-[26px] text-[#747d8d]">{vals[h] == null ? "—" : jo((vals[h] as number) * 10000)}</p>
            <p className="whitespace-nowrap text-[13px] font-medium leading-[20px]" style={{ color: yoy[h] == null ? "#8b95a1" : (yoy[h] as number) >= 0 ? "#ff4047" : "#477aff" }}>{yoy[h] == null ? "—" : `${(yoy[h] as number) >= 0 ? "+" : ""}${(yoy[h] as number).toFixed(1)}%`} · 전년 동기 대비</p>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ---------- 수익성 — 분기 8개 + ROA (앱과 같게) ---------- */
const PROFIT = [
  { k: "영업이익률", c: "#000000", key: "op_margin", help: "매출 중 본업으로 남긴 이익의 비율이에요.\n\n영업이익 ÷ 매출\n× 100" },
  { k: "순이익률", c: "#4a74b8", key: "net_margin", help: "매출 중 모든 비용과 세금을 뺀 최종 이익의 비율이에요.\n\n당기순이익 ÷ 매출 × 100" },
  { k: "ROE", c: "#c0392b", key: "roe", help: "주주의 자본으로 얼마나 이익을 냈는지 보여줘요.\n\n당기순이익(연환산) ÷\n평균 자기자본 × 100" },
  { k: "ROA", c: "#2fae68", key: "roa", help: "가진 자산 전체로 얼마나 이익을 냈는지 보여줘요.\n\n당기순이익(연환산) ÷\n평균 총자산 × 100" },
] as const;
function Profit({ ctl, s }: { ctl: TipCtl; s: Stock }) {
  const X = (i: number) => (95 + i * (493 / 7)) * FX;
  const fin = useFin(s.stock_code), Q8 = fin.quarters.slice(-8), QL = Q8.map((q) => q.q);
  const Y = (v: number) => Math.max(10, Math.min(232, 142 - v * 2.1));
  const vals = (key: (typeof PROFIT)[number]["key"]) => Q8.map((q) => q[key]);
  const nullK = (k: string) => vals(PROFIT.find((p) => p.k === k)!.key).every((v) => v == null); /* 금융업은 매출이 없어 — */
  return (
    <Card className="flex h-[404px] flex-col items-start gap-5 p-6">
      <div className="flex h-[29px] w-[810px] items-center justify-between"><p className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#191f28]">수익성</p><p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">분기 · {Q8[7].label} 기준</p></div>
      <div className="flex h-[18px] items-center gap-[18px]">
        {PROFIT.map((p) => (
          <div key={p.k} className="relative flex items-center gap-[6px]">
            <span className="h-[10px] w-[10px] rounded-[5px]" style={{ background: p.c }} />
            <p className="whitespace-nowrap text-[13px] font-medium leading-[20px] text-[#6b7684]">{p.k}{nullK(p.k) ? " —" : ""}</p>
            <HelpBtn k={p.k} ctl={ctl} size={16} />
            {ctl.open === p.k && (
              <div data-tipbox className={cx(TIPBOX, "top-[26px] flex w-[166px] flex-col items-start gap-[10px] px-3 py-[14px]")} style={{ left: "calc(100% - 28px)" }} onClick={(e) => e.stopPropagation()}>
                <div className="flex h-6 w-[142px] items-center justify-between"><p className="min-w-0 flex-1 text-[14px] font-bold leading-[21px] text-[#477bff]">{p.k}</p></div>
                <p className="w-[142px] whitespace-pre-line text-[13px] leading-[20px] text-[#747d8d]">{p.help}</p>
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="relative h-[260px] w-[810px]">
        <svg width="810" height="260" viewBox="0 0 810 260" className="absolute inset-0">
          {[16, 58, 100, 142, 184, 226].map((y) => <rect key={y} x={51 * FX} y={y} width={581 * FX} height="1" fill={y === 142 ? "#b8bfc8" : "#e5e8eb"} />)}
          {PROFIT.filter((p) => !nullK(p.k)).map((p) => { const v = vals(p.key) as number[]; return <g key={p.k} data-profit={p.k}><path className="m-line" pathLength={400} d={v.map((x, i) => (i ? "L" : "M") + X(i).toFixed(1) + " " + Y(x).toFixed(1)).join("")} stroke={p.c} strokeWidth="2.5" fill="none" strokeLinejoin="round" />{v.map((x, i) => <circle key={i} cx={X(i)} cy={Y(x)} r="3.5" fill={p.c}><title>{`${p.k} ${QL[i]} ${x.toFixed(1)}%`}</title></circle>)}</g>; })}
        </svg>
        {[["60%", 16, 27], ["40%", 58, 27], ["20%", 100, 27], ["0%", 142, 35], ["-20%", 184, 21], ["-40%", 226, 21]].map(([t, y, x]) => <p key={t as string} className="absolute whitespace-nowrap text-[11px] leading-[16px] text-[#6b7684]" style={{ left: (x as number) * FX + (FX - 1) * 10, top: y as number }}>{t}</p>)}
        {QL.map((q, i) => <p key={q} className="absolute top-[246px] w-[40px] whitespace-nowrap text-center text-[11px] leading-[16px] text-[#6b7684]" style={{ left: X(i) - 20 }}>{q}</p>)}
      </div>
    </Card>
  );
}

/* ---------- 기업 건전성 (지표 고르면 조금 진하게 · 색 추가 없음) ---------- */
const HEALTH = [
  { k: "부채비율", key: "debt", d: "자기자본에 비해 부채가 얼마나 많은지 보여줘요.", f: "부채 ÷ 자기자본 × 100" },
  { k: "유동비율", key: "current", d: "1년 안에 갚을 빚을 1년 안에 현금이 되는 자산으로 얼마나 덮는지예요.", f: "유동자산 ÷ 유동부채 × 100 · 높을수록 단기 지급 여유가 커요." },
  { k: "당좌비율", key: "quick", d: "재고자산을 제외한 유동자산으로 단기 부채를 갚을 여력을 봐요.", f: "당좌자산 ÷ 유동부채 × 100" },
  { k: "이자보상비율", key: "interest", d: "본업에서 번 이익으로 이자를 얼마나 감당할 수 있는지 봐요.", f: "영업이익 ÷ 이자비용" },
  { k: "유보율", key: "reserve", d: "자본금 대비 쌓인 잉여금의 비율이에요.", f: "(자본잉여금 + 이익잉여금) ÷ 자본금 × 100" },
] as const;
/* 안정성 점수 0.3~1 (바깥쪽일수록 안정적) — 메모스톡 자체 기준 */
const SCORE: Record<string, (v: number) => number> = { debt: (v) => 1 - v / 400, current: (v) => v / 250, quick: (v) => v / 200, interest: (v) => v / 30, reserve: (v) => Math.log10(Math.max(10, v)) / 4.5 };
/* 레이더 꼭짓점 순서: 위 부채비율, 오른쪽 위 유보율, 오른쪽 아래 이자보상비율, 왼쪽 아래 당좌비율, 왼쪽 위 유동비율 */
const HX = 40, HL = 310 + 110, HW = 330 + 60; // 레이더 살짝 안쪽, 오른쪽 지표 목록 넓힘
const AX = ["부채비율", "유보율", "이자보상비율", "당좌비율", "유동비율"];
const PTS: [number, number][] = [[150, 96], [213, 129.5], [194.5, 211.5], [113, 201], [89, 130]];
const LBL: [number, number][] = [[128, 42], [238, 114], [206, 219], [49, 219], [17, 114]];
function Health({ s }: { s: Stock }) {
  const [sel, setSel] = useState<string | null>(null);
  const fin = useFin(s.stock_code), H = fin.health;
  const raw = (name: string) => { const h = HEALTH.find((x) => x.k === name)!; return H[h.key]; };
  const k = (i: number) => { const v = raw(AX[i]); if (v == null) return 0; const key = HEALTH.find((x) => x.k === AX[i])!.key; return Math.max(0.3, Math.min(1, SCORE[key](v))); };
  const R0: [number, number][] = [0, 1, 2, 3, 4].map((i) => { const a = -Math.PI / 2 + (i * 2 * Math.PI) / 5; return [150 + Math.cos(a) * 72, 150 + Math.sin(a) * 72]; });
  void PTS;
  const pts = R0.map(([x, y], i) => [150 + (x - 150) * k(i), 150 + (y - 150) * k(i)] as const);
  const val = (h: (typeof HEALTH)[number]) => { const v = H[h.key]; if (v == null) return "—"; return h.key === "interest" ? `${v.toFixed(1)}배` : `${Math.round(v).toLocaleString("ko-KR")}%`; };
  const ring = (r: number) => [0, 1, 2, 3, 4].map((i) => { const a = -Math.PI / 2 + (i * 2 * Math.PI) / 5; return `${(150 + Math.cos(a) * r).toFixed(1)},${(150 + Math.sin(a) * r).toFixed(1)}`; }).join(" ");
  const cur = HEALTH.find((h) => h.k === sel);
  return (
    <Card className="flex h-[404px] flex-col items-start gap-5 p-6">
      <div className="flex h-[25px] w-[810px] items-center justify-between">
        <p className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#191f28]">기업 건전성</p>
        <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">{fin.as_of.slice(0, 4)}년 {fin.as_of.slice(5, 7)}월 기준</p>
      </div>
      <div className="relative h-[300px] w-[810px]">
        <svg width="300" height="300" viewBox="0 0 300 300" className="absolute top-0" style={{ left: HX }}>
          {[18, 36, 54, 72].map((r) => <polygon key={r} points={ring(r)} fill="none" stroke="#b4b2a9" strokeOpacity="0.55" strokeWidth="0.8" />)}
          {[0, 1, 2, 3, 4].map((i) => { const a = -Math.PI / 2 + (i * 2 * Math.PI) / 5; return <line key={i} x1="150" y1="150" x2={150 + Math.cos(a) * 72} y2={150 + Math.sin(a) * 72} stroke="#b4b2a9" strokeOpacity="0.55" strokeWidth="0.8" />; })}
          <polygon points={pts.map((p) => p.join(",")).join(" ")} fill="#378add" fillOpacity="0.18" stroke="#378add" strokeWidth="1.8" style={{ transformOrigin: "150px 150px", animation: "m-nw calc(.7s * var(--k)) var(--sheet) both" }} />
          {pts.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={sel === AX[i] ? 4 : 3} fill="#378add" stroke="#fff" strokeWidth="1.5" style={{ transition: "r calc(.2s * var(--k))" }} />)}
        </svg>
        {AX.map((a, i) => <button key={a} onClick={() => setSel(sel === a ? null : a)} className={cx("absolute whitespace-nowrap text-[13px] leading-[20px] transition-colors", sel === a ? "font-bold text-[#191f28]" : "font-medium text-[#333d4b] hover:text-[#191f28]")} style={{ left: LBL[i][0] + HX, top: LBL[i][1] }}>{a}</button>)}
        <div className="absolute top-[10px] flex items-center gap-[6px]" style={{ left: HL }}><span className="h-[7px] w-[7px] rounded-full bg-[#378add]" /><p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b788c]">{s.name}</p></div>
        <div className="absolute top-[34px] flex flex-col" style={{ left: HL, width: HW }}>
          {HEALTH.map((h) => { const on = sel === h.k; return (
            <button key={h.k} onClick={() => setSel(on ? null : h.k)} style={{ width: HW }} className="flex h-[30px] items-center justify-between border-b border-[#e5e8eb] text-left">
              <span className={cx("whitespace-nowrap text-[13px] leading-[20px] transition-colors", on ? "font-bold text-[#191f28]" : "font-medium text-[#333d4b]")}>{h.k}</span>
              <span className={cx("whitespace-nowrap text-[13px] leading-[20px] transition-colors", on ? "font-bold text-[#191f28]" : "font-medium text-[#333d4b]")}>{val(h)}</span>
            </button>
          ); })}
        </div>
        <div key={sel ?? "base"} style={{ left: HL, width: HW }} className="m-in absolute top-[192px] flex flex-col items-start gap-1 rounded-[10px] bg-[#f5f6f8] px-3 py-[10px]">
          {cur ? (<>
            <p className="text-[13px] font-bold leading-[20px] text-[#333d4b]">{cur.k} · {val(cur)}</p>
            <p style={{ width: HW - 24 }} className="text-[13px] leading-[20px] text-[#4e5968]">{cur.d}</p>
            <p style={{ width: HW - 24 }} className="text-[13px] leading-[20px] text-[#6b788c]">{cur.f}</p>
          </>) : (<>
            <p className="text-[13px] font-bold leading-[20px] text-[#333d4b]">{s.name} 재무 건전성</p>
            <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#4e5968]">바깥쪽으로 갈수록 안정적이에요. 지표 이름을 누르면 설명이 나와요.</p>
            <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b788c]">바깥 테두리는 메모스톡 자체 기준 · 최근 분기 재무제표</p>
          </>)}
        </div>
      </div>
    </Card>
  );
}

/* ---------- 7 본문 ---------- */
export function CompanyInfo({ s }: { s: Stock }) {
  const [open, setOpen] = useState<string | null>(null);
  const ctl = { open, set: setOpen };
  useEffect(() => { if (!open) return; const f = (e: MouseEvent) => { if (!(e.target as HTMLElement).closest("[data-tip],[data-tipbox]")) setOpen(null); }; document.addEventListener("mousedown", f); return () => document.removeEventListener("mousedown", f); }, [open]);
  return (
    <div className="flex w-[860px] flex-col items-start gap-8">
      <Card className="flex items-center gap-10 p-6">
        <p className="shrink-0 whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#191f28]">기업 개요</p>
        <p className="min-w-0 flex-1 text-[14px] leading-[1.65] text-[#191f28]">{overview(s)}</p>
      </Card>
      <div className="flex w-[860px] flex-col items-start gap-6"><PriceChart s={s} /><Quote s={s} ctl={ctl} /></div>
      <Financials s={s} ctl={ctl} />
      <div className="flex w-[860px] flex-col items-start gap-6"><Profit ctl={ctl} s={s} /><Health s={s} /></div>
    </div>
  );
}
