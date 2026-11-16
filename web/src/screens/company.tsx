/* 7 · 기업 정보 — Figma 2.5 (7 · 7.1 도움말 · 7.2 그래프 호버) 그대로. 숫자는 SK하이닉스 = Figma, 다른 종목 = 가격에 맞춘 예시 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { cx, series } from "../kit";
import type { Stock } from "../data";

const won = (n: number) => Math.round(n).toLocaleString("ko-KR");
const jo = (eok: number) => { const neg = eok < 0, a = Math.abs(Math.round(eok)), j = Math.floor(a / 10000), r = a % 10000; return (neg ? "-" : "") + (j && r ? `${j}조 ${r.toLocaleString("ko-KR")}억원` : j ? `${j}조원` : `${r.toLocaleString("ko-KR")}억원`); };
const SK = "000660";
const factor = (s: Stock) => (s.code === SK ? 1 : s.code === "005930" ? 2.5 : s.code === "035420" ? 0.1 : 0.3);

/* ---------- 7 머리 (큰 머리) ---------- */
const SK_MINI = "M1.25024 42.25L13.2502 36.25L24.2502 38.25L36.2502 31.25L47.2502 21.25L59.2502 26.25L71.2502 24.25L83.2502 18.25L95.2502 22.25L107.25 15.25L119.25 12.25L141.25 1.25";
export function BigHead({ s }: { s: Stock }) {
  const up = s.chg >= 0, c = up ? "#E5484D" : "#2F6BDB";
  const pts = useMemo(() => {
    if (s.code === SK) return null;
    const a = series(s.seed + 3, 12, s.price, 0.03), mn = Math.min(...a), mx = Math.max(...a);
    return a.map((v, i) => [1.25 + (i / 11) * 140, 1.25 + ((mx - v) / (mx - mn || 1)) * 41] as const);
  }, [s]);
  const line = pts ? pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(2) + " " + p[1].toFixed(2)).join("") : SK_MINI;
  const area = pts ? pts.map((p, i) => (i ? "L" : "M") + (p[0] - 1.25).toFixed(2) + " " + (p[1] - 2.25).toFixed(2)).join("") + "V51H0Z" : "M0 41L12 35L23 37L35 30L46 20L58 25L70 23L82 17L94 21L106 14L118 11L140 0V51H0V41Z";
  const end = pts ? pts[pts.length - 1] : [141.25, 1.25];
  const start = pts ? pts[2] : [23 + 4 - 4 + 4, 40 + 4 - 7];
  return (
    <div className="flex h-24 w-full shrink-0 items-start justify-between pr-2">
      <div className="flex h-[86px] w-[230px] flex-col items-start gap-[10px]">
        <div className="flex items-center gap-3">
          <div className="dk-keep flex h-10 w-10 items-center justify-center rounded-[12px]" style={{ background: s.logoBg }}><p className="text-center font-bold leading-none text-white" style={{ fontSize: s.logo.length > 1 ? 13.6 : 17 }}>{s.logo}</p></div>
          <p className="whitespace-nowrap text-[36px] font-bold leading-[40px] text-[#191f28]">{s.name}</p>
        </div>
        <div className="flex items-center gap-2">
          <p className="whitespace-nowrap text-[14px] leading-[21px] text-[#6b7684]">{s.code} · {s.market}</p>
          <div className="flex items-center rounded-[6px] bg-[#e8edf5] px-[10px] py-1"><p className="whitespace-nowrap text-[14px] font-medium leading-[21px] text-black">{s.hold === "보유" ? "보유 중" : "관심"}</p></div>
        </div>
      </div>
      <div className="flex h-[78px] w-[330px] items-center gap-6">
        <div className="flex h-[76px] w-[156px] flex-col items-end gap-[2px]">
          <p className="w-[156px] text-center text-[32px] font-bold leading-[40px] text-[#191f28]">{won(s.price)}원</p>
          <p className="w-[156px] whitespace-pre text-center text-[17px] font-bold leading-[26px]" style={{ color: up ? "#e5484d" : "#2f6bdb" }}>{up ? "+" : "-"}{won(Math.abs(s.chg))}  {up ? "+" : "-"}{Math.abs(s.pct).toFixed(2)}%</p>
          <p className="w-[156px] text-center text-[13px] leading-[20px] text-[#6b7684]">10.11 15:30 기준</p>
        </div>
        <div className="relative h-[60px] w-[150px] shrink-0">
          <svg className="absolute left-1 top-[5px]" width="140" height="51" viewBox="0 0 140 51" fill="none"><path d={area} fill={c} fillOpacity="0.11" /></svg>
          <svg className="absolute left-1 top-[54px]" width="140" height="1" viewBox="0 0 140 1" fill="none"><line y1="0.5" x2="140" y2="0.5" stroke="#94A1B0" strokeOpacity="0.5" strokeDasharray="3 4" /></svg>
          <svg className="absolute left-1 top-[7px] overflow-visible" width="143" height="44" viewBox="0 0 143 44" fill="none"><path className="m-line" pathLength={400} d={line} stroke={c} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
          {s.code === SK && <div className="absolute left-[23px] top-[40px] h-2 w-2 rounded-full border-2 border-[#4f5c6e] bg-white" />}
          {s.code !== SK && <div className="absolute h-2 w-2 rounded-full border-2 border-[#4f5c6e] bg-white" style={{ left: 4 + start[0] - 4, top: 7 + start[1] - 4 }} />}
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
const OVERVIEW: Record<string, string> = {
  "000660": "SK하이닉스는 DRAM과 NAND 플래시 등 메모리 반도체를 설계·제조하는 기업입니다. AI 서버용 고대역폭 메모리(HBM)를 비롯한 고성능 메모리 제품을 공급하며, 반도체 업황과 AI 수요에 따라 실적이 크게 움직이는 종목이에요.",
  "005930": "삼성전자는 메모리 반도체와 파운드리, 스마트폰·가전을 함께 만드는 기업입니다. 반도체 업황과 스마트폰 수요, 주주환원 정책에 따라 실적과 주가가 움직이는 종목이에요.",
  "035420": "네이버는 검색 포털을 중심으로 커머스·핀테크·콘텐츠·클라우드 사업을 하는 기업입니다. 광고·커머스 업황과 AI 서비스 경쟁에 따라 실적이 움직이는 종목이에요.",
};

/* ---------- 주가 · 거래량 (Figma 캔들 그대로 · 안내선은 마우스 따라) ---------- */
const CANDLES: number[][] = [[11,118.5,26.1,7,123.6,7.6,220.4,23.6,0],[25,98.3,32.8,21,109.3,10.1,224.3,19.7,0],[39,95.8,21.9,34,110.1,1.7,214.7,29.3,0],[52,93.3,30.3,48,105.9,10.1,210.2,33.8,1],[66,99.2,26.9,62,106.7,7.6,211.5,32.5,1],[81,98.3,26.9,76,108.4,4.2,218.5,25.5,0],[95,95,37,90,108.4,10.9,229.3,14.7,0],[109,108.4,26.9,103,121.9,4.2,230.6,13.4,0],[122,121,22.7,117,130.3,7.6,219.2,24.8,1],[136,121.9,29.4,131,129.4,10.1,196.2,47.8,1],[150,110.9,26.9,146,123.6,1.7,210.2,33.8,1],[164,90.8,36.2,161,105.1,10.1,214.1,29.9,0],[177,84.9,28.6,174,95.8,8.4,223,21,0],[191,89.9,15.1,188,95.8,3.4,235.1,8.9,1],[205,79.8,32.8,202,91.6,10.9,225.5,18.5,1],[219,79,32,216,93.3,5,215.3,28.7,1],[234,80.7,32,229,92.4,6.7,210.2,33.8,0],[247,91.6,26.9,243,98.3,10.9,211.5,32.5,0],[261,107.6,16.8,257,117.7,1.7,202,42,0],[275,112.6,32.8,271,126.9,9.2,228.7,15.3,1],[289,116.8,34.5,285,129.4,8.4,231.9,12.1,1],[303,116.8,24.4,299,125.2,2.5,220.4,23.6,0],[316,101.7,29.4,313,110.1,10.9,212.8,31.2,0],[330,92.4,25.2,327,105.1,5.9,210.2,33.8,0],[344,88.2,29.4,341,102.5,5.9,213.4,30.6,1],[358,85.7,33.6,355,95.8,10.9,222.3,21.7,1],[372,88.2,21.9,368,94.1,2.5,234.4,9.6,1],[386,76.5,32,382,88.2,9.2,210.9,33.1,0],[400,81.5,30.3,396,95.8,9.2,216,28,0],[414,101.7,21.9,410,113.5,1.7,210.9,33.1,1],[429,114.3,28.6,423,120.2,10.9,210.9,33.1,1],[442,112.6,30.3,438,122.7,6.7,217.2,26.8,1],[456,100.8,31.1,452,115.1,5.9,227.4,16.6,0],[470,89.1,31.1,466,101.7,10.9,233.2,10.8,0],[484,90.8,18.5,480,98.3,2.5,221.1,22.9,0],[498,80.7,29.4,493,89.1,8.4,212.8,31.2,1],[511,65.5,36.2,507,79,9.2,194.3,49.7,1],[526,58,26.9,521,71.4,1.7,212.8,31.2,0],[540,52.1,28.6,535,61.3,10.1,221.1,22.9,0],[554,62.2,21,549,68.9,6.7,233.2,10.8,0],[567,70.6,28.6,562,83.2,5,227.4,16.6,1],[581,86.6,17.7,576,93.3,7.6,222.3,21.7,0]];
const GRID_Y = [17.6, 57.1, 96.6, 136.2, 175.7], GRID_X = [4, 101, 199, 296, 393, 491, 588];
const PRICE_LBL = [[220000, 12], [200000, 51], [180000, 91], [160000, 130], [145000, 170]] as const;
const DATES = [["08.19", 4], ["09.02", 88.5], ["09.16", 186.5], ["09.30", 283.5], ["10.14", 380.5], ["10.28", 478.5]] as const;
const round100 = (v: number) => Math.round(v / 100) * 100;
function PriceChart({ s }: { s: Stock }) {
  const r = s.price / 180500;
  const [hov, setHov] = useState<{ x: number; y: number; label?: [string, string] }>({ x: 360.3, y: 73.6, label: [won(round100(188500 * r)), "2026-10-03"] });
  const ref = useRef<SVGSVGElement>(null);
  const move = (e: React.MouseEvent) => {
    const b = ref.current!.getBoundingClientRect(), z = b.width / 816, mx = (e.clientX - b.left) / z / PX, my = (e.clientY - b.top) / z;
    if (mx < 4 || mx > 588) return;
    const c = CANDLES.reduce((a, k) => (Math.abs(k[0] - mx) < Math.abs(a[0] - mx) ? k : a));
    setHov({ x: c[0] + 0.3, y: Math.max(GRID_Y[0], Math.min(GRID_Y[4], my)) });
  };
  const price = hov.label ? hov.label[0] : won(round100((200000 - (hov.y - 57.1) * (20000 / 39.5)) * r));
  const d = new Date(2026, 7, 19 + Math.round((hov.x - 4) / 6.964));
  const date = hov.label ? hov.label[1] : `2026-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return (
    <Card className="h-[349px]">
      <div className="absolute left-[22px] top-[25px] h-[300px] w-[816px]">
        <p className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#191f28]">주가 · 거래량</p>
        <div className="absolute left-0 top-[34px] h-[266px] w-[816px]">
          <svg ref={ref} width="816" height="266" viewBox="0 0 816 266" className="absolute inset-0 cursor-crosshair" onMouseMove={move}>
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
            <rect x={hov.x * PX - 0.3} y="15.2" width="0.6" height="228.8" fill="#7a8594" fillOpacity="0.55" />
            <rect x={4 * PX} y={hov.y - 0.5} width={584 * PX} height="1" fill="#7a8594" fillOpacity="0.55" />
            <ellipse cx={hov.x * PX} cy={hov.y - 1.1} rx="2.4" ry="4" fill="#fff" stroke="#141a24" strokeWidth="2" />
          </svg>
          {PRICE_LBL.map(([v, y]) => <p key={v} className="pointer-events-none absolute w-[37px] whitespace-nowrap text-[11px] leading-[16px] text-[#6b788c]" style={{ top: y, left: 596 * PX }}>{won(round100(v * r))}</p>)}
          <p className="pointer-events-none absolute left-1 top-[184px] whitespace-nowrap text-[13px] font-medium leading-[20px] text-[#141a24]">거래량</p>
          <p className="pointer-events-none absolute left-10 top-[184px] whitespace-nowrap text-[13px] font-bold leading-[20px] text-[#6b788c]">4,862,120</p>
          {DATES.map(([t, x]) => <p key={t} className="pointer-events-none absolute top-[254px] w-[25px] whitespace-nowrap text-[11px] leading-[16px] text-[#6b788c]" style={{ left: x * PX }}>{t}</p>)}
          <div className="pointer-events-none absolute flex h-5 w-[57px] items-center justify-center rounded-[4px] bg-[#383b40]" style={{ top: hov.y - 12.8, left: 589 * PX }}><p className="text-[13px] font-bold leading-[20px] text-white">{price}</p></div>
          <div className="pointer-events-none absolute top-[247px] flex h-5 w-[68px] items-center justify-center rounded-[4px] bg-[#383b40]" style={{ left: hov.x * PX - 34 }}><p className="text-[11px] font-medium leading-[16px] text-white">{date}</p></div>
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
  const sk = s.code === SK, r = s.price / 180500, f = factor(s);
  const prev = sk ? 174400 : s.price - s.chg;
  const L: [string, string, boolean][] = [["전일", won(prev), false], ["시가", won(sk ? 175000 : round100(prev * 1.0034)), true], ["고가", won(sk ? 181200 : round100(s.price * 1.0039)), true], ["저가", won(sk ? 174800 : round100(prev * 1.0023)), true], ["거래량", (sk ? "3,214,560" : won(3214560 / Math.max(0.3, r) / 1.7)) + "주", false], ["거래대금", (sk ? "5,742" : won((3214560 / Math.max(0.3, r) / 1.7) * s.price / 1e8)) + "억원", false]];
  const shares = sk ? 728002365 : Math.round(728002365 * f / r / 10) * 10;
  const eps = sk ? 58980 : round100(58980 * r * 1.3);
  const bps = sk ? 95100 : round100(95100 * r * 1.1);
  const R: [string, string][] = [["PER", (s.price / eps).toFixed(2) + "배"], ["EPS", won(eps) + "원"], ["PBR", (s.price / bps).toFixed(2) + "배"], ["BPS", won(bps) + "원"], ["시가총액", sk ? "131조 4,100억원" : jo((s.price * shares) / 1e8)], ["상장주수", won(shares) + "주"]];
  const lo = sk ? 140000 : round100(140000 * r), hi = sk ? 299500 : round100(299500 * r), pos = (s.price - lo) / (hi - lo);
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
const QL = ["24.3Q", "24.4Q", "25.1Q", "25.2Q", "25.3Q", "25.4Q", "26.1Q", "26.2Q"], QF = ["2024년 3분기", "2024년 4분기", "2025년 1분기", "2025년 2분기", "2025년 3분기", "2025년 4분기", "2026년 1분기", "2026년 2분기"];
/* 조 원 (SK하이닉스 기준, 화면 예시) · 앞 4개는 전년 동기 계산용(23.3Q~24.2Q) */
const FQ: Record<FinK, { color: string; v: (number | null)[]; prev: number[]; help: [string, string, string] }> = {
  매출: { color: "#b9aed8", v: [17.6, 19.8, 17.6, 22.2, 24.4, 33.5, 30.1, 33.5], prev: [9.1, 11.3, 12.4, 16.4], help: ["매출이란?", "상품을 팔거나 서비스를 제공해 벌어들인 금액이에요. 아직 비용을 빼기 전의 금액으로, 기업의 사업 규모를 보여줘요.", "한눈에 · 얼마나 팔았나요?"] },
  영업이익: { color: "#51c38b", v: [7.0, 8.1, 7.4, 9.2, 11.4, 16.8, 14.2, 16.1], prev: [0.6, 0.3, 2.9, 5.5], help: ["영업이익이란?", "매출에서 제품을 만드는 비용과 판매·관리에 든 비용을 뺀 이익이에요. 본업으로 얼마나 벌었는지 보여주며, 금액이 음수라면 영업손실이에요.", "한눈에 · 본업으로 얼마나 남겼나요?"] },
  당기순이익: { color: "#e8cf7e", v: [5.8, 8.0, 8.1, 7.0, 12.6, 13.2, 11.8, 13.9], prev: [0.4, 0.5, 1.9, 4.1], help: ["당기순이익이란?", "모든 수익과 비용, 법인세까지 반영한 최종 이익이에요. 본업 외의 손익도 포함하며, 금액이 음수라면 당기순손실이에요.", "한눈에 · 최종적으로 얼마나 남았나요?"] },
};
/* 금융업(KB금융)은 매출을 공시하지 않아 null → 화면엔 — 로 (11.16 사용자 결정: 금융업 화면은 따로 만들지 않음) */
const FIN_CO = new Set(["105560"]);
const finVals = (s: Stock, k: FinK) => (FIN_CO.has(s.code) && k === "매출" ? FQ[k].v.map(() => null) : FQ[k].v.map((x) => (x == null ? null : x * factor(s))));
const yoyOf = (vals: (number | null)[], k: FinK, f: number) => { const prev = [...FQ[k].prev.map((x) => x * f), ...vals.slice(0, 4)]; return vals.map((v, i) => (v == null || prev[i] == null || !prev[i] ? null : ((v as number) / (prev[i] as number) - 1) * 100)); };
const CX0 = 70 * FX, CX1 = 631 * FX, CY0 = 16, CY1 = 218, BW = 46, TIP_W = 159, TIP_H = 94;
const qx = (i: number) => CX0 + ((CX1 - CX0) / 8) * (i + 0.5);
const tipLeft = (i: number) => (qx(i) + BW / 2 + 10 + TIP_W <= 810 ? qx(i) + BW / 2 + 10 : qx(i) - BW / 2 - 10 - TIP_W);
function Financials({ s, ctl }: { s: Stock; ctl: TipCtl }) {
  const [k, setK] = useState<FinK>("매출");
  const [h, setH] = useState<number | null>(null);
  const F = FQ[k], vals = finVals(s, k), yoy = yoyOf(vals, k, factor(s));
  const nums = vals.filter((x): x is number => x != null), max = nums.length ? Math.max(...nums) : 1;
  const step = Math.pow(10, Math.floor(Math.log10(max))) * (max / Math.pow(10, Math.floor(Math.log10(max))) > 5 ? 2 : 1);
  const top = Math.ceil(max / step) * step, ticks = nums.length ? Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step) : [0];
  const y = (v: number) => CY1 - (v / top) * (CY1 - CY0);
  const ys = yoy.filter((x): x is number => x != null), yMax = Math.max(1, ...ys.map(Math.abs));
  const ly = (p: number) => CY0 + 8 + ((yMax - p) / (2 * yMax)) * (CY1 - CY0 - 16);
  const last = vals[7], lastY = yoy[7];
  const lbl = (n: number) => (n === 0 ? "0" : `${Number.isInteger(n) ? n : n.toFixed(1)}조`);
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
        <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">2026년 2분기 기준 · 연결재무제표 · 분기</p>
      </div>
      <div className="flex h-12 items-start gap-1 rounded-[24px] bg-[#f2f3f5] p-1">
        {(Object.keys(FQ) as FinK[]).map((t) => <button key={t} onClick={() => { setK(t); setH(null); }} className={cx("flex h-10 items-center rounded-[20px] px-5 text-[15px] font-medium leading-[23px] transition-colors", k === t ? "bg-black text-white" : "text-[#8f8f8f] hover:text-[#191f28]")}>{t}</button>)}
      </div>
      <div className="flex h-[43px] w-[810px] items-center gap-6">
        <div className="flex flex-col items-start gap-[6px]"><p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">2026년 2분기 {k}</p><p data-fin-last className="whitespace-nowrap text-[14px] font-bold leading-[21px] text-[#191f28]">{last == null ? "—" : jo(last * 10000)}</p></div>
        <div className="flex flex-col items-start gap-[6px]"><p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">2025년 2분기 대비</p><p className="whitespace-nowrap text-[14px] font-bold leading-[21px]" style={{ color: lastY == null ? "#191f28" : lastY >= 0 ? "#ff3d45" : "#477aff" }}>{lastY == null ? "—" : `${lastY >= 0 ? "+" : ""}${lastY.toFixed(2)}%`}</p></div>
        {!nums.length && <p className="ml-auto text-[13px] leading-[20px] text-[#8b95a1]">이 회사는 {k}을 공시하지 않아요 · 값이 없으면 — 로 보여요</p>}
      </div>
      <div key={k} className="relative h-[246px] w-[810px]" onMouseLeave={() => setH(null)}>
        <svg width="810" height="246" viewBox="0 0 810 246" className="absolute inset-0">
          {ticks.map((t) => <rect key={t} x={CX0} y={y(t)} width={CX1 - CX0} height="1" fill={t === 0 ? "#b8bfc8" : "#e5e8eb"} />)}
          {vals.map((v, i) => v == null ? null : <rect key={i} className="m-bar-grow" x={qx(i) - BW / 2} y={y(v)} width={BW} height={CY1 - y(v)} rx="2" fill={F.color} opacity={h === null || h === i ? 1 : 0.55} style={{ transformOrigin: `0 ${CY1}px` }} />)}
          {line.some(Boolean) && <path className="m-line" pathLength={400} d={line.filter(Boolean).map((p, i) => (i ? "L" : "M") + p![0] + " " + p![1]).join("")} stroke="#33404b" strokeWidth="1.6" fill="none" />}
          {line.map((p, i) => p && <ellipse key={i} cx={p[0]} cy={p[1]} rx="3" ry="3.5" fill="#fff" stroke="#33404b" strokeWidth="1.5" />)}
        </svg>
        {ticks.map((t) => <p key={t} style={{ top: y(t) - 6, left: 20 * FX }} className="absolute w-7 text-right text-[11px] leading-[16px] text-[#6b788c]">{lbl(t)}</p>)}
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
  { k: "영업이익률", c: "#000000", v: [39.8, 40.9, 42.0, 41.4, 46.7, 50.1, 47.2, 48.1], help: "매출 중 본업으로 남긴 이익의 비율이에요.\n\n영업이익 ÷ 매출\n× 100" },
  { k: "순이익률", c: "#4a74b8", v: [33.0, 40.4, 46.0, 31.5, 51.6, 39.4, 39.2, 41.5], help: "매출 중 모든 비용과 세금을 뺀 최종 이익의 비율이에요.\n\n당기순이익 ÷ 매출 × 100" },
  { k: "ROE", c: "#c0392b", v: [18.2, 21.5, 22.0, 19.4, 28.1, 27.3, 24.0, 25.6], help: "주주의 자본으로 얼마나 이익을 냈는지 보여줘요.\n\n당기순이익(연환산) ÷\n평균 자기자본 × 100" },
  { k: "ROA", c: "#2fae68", v: [11.0, 13.2, 13.8, 12.1, 17.9, 17.5, 15.2, 16.3], help: "가진 자산 전체로 얼마나 이익을 냈는지 보여줘요.\n\n당기순이익(연환산) ÷\n평균 총자산 × 100" },
];
function Profit({ ctl, s }: { ctl: TipCtl; s: Stock }) {
  const X = (i: number) => (95 + i * (493 / 7)) * FX;
  const Y = (v: number) => 142 - v * 2.1;
  const nullK = (k: string) => FIN_CO.has(s.code) && (k === "영업이익률" || k === "순이익률"); /* 금융업은 매출이 없어 — */
  return (
    <Card className="flex h-[404px] flex-col items-start gap-5 p-6">
      <div className="flex h-[29px] w-[810px] items-center justify-between"><p className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#191f28]">수익성</p><p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">분기 · 화면 예시</p></div>
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
          {PROFIT.filter((p) => !nullK(p.k)).map((p) => <g key={p.k}><path className="m-line" pathLength={400} d={p.v.map((v, i) => (i ? "L" : "M") + X(i).toFixed(1) + " " + Y(v)).join("")} stroke={p.c} strokeWidth="2.5" fill="none" strokeLinejoin="round" />{p.v.map((v, i) => <circle key={i} cx={X(i)} cy={Y(v)} r="3.5" fill={p.c} />)}</g>)}
        </svg>
        {[["60%", 16, 27], ["40%", 58, 27], ["20%", 100, 27], ["0%", 142, 35], ["-20%", 184, 21], ["-40%", 226, 21]].map(([t, y, x]) => <p key={t as string} className="absolute whitespace-nowrap text-[11px] leading-[16px] text-[#6b7684]" style={{ left: (x as number) * FX + (FX - 1) * 10, top: y as number }}>{t}</p>)}
        {QL.map((q, i) => <p key={q} className="absolute top-[246px] w-[40px] whitespace-nowrap text-center text-[11px] leading-[16px] text-[#6b7684]" style={{ left: X(i) - 20 }}>{q}</p>)}
      </div>
    </Card>
  );
}

/* ---------- 기업 건전성 (지표 고르면 조금 진하게 · 색 추가 없음) ---------- */
const HEALTH = [
  { k: "부채비율", v: "58%", d: "자기자본에 비해 부채가 얼마나 많은지 보여줘요.", f: "부채 ÷ 자기자본 × 100" },
  { k: "유동비율", v: "170%", d: "1년 안에 갚을 빚을 1년 안에 현금이 되는 자산으로 얼마나 덮는지예요.", f: "유동자산 ÷ 유동부채 × 100 · 높을수록 단기 지급 여유가 커요." },
  { k: "당좌비율", v: "125%", d: "재고자산을 제외한 유동자산으로 단기 부채를 갚을 여력을 봐요.", f: "당좌자산 ÷ 유동부채 × 100" },
  { k: "이자보상비율", v: "25배", d: "본업에서 번 이익으로 이자를 얼마나 감당할 수 있는지 봐요.", f: "영업이익 ÷ 이자비용" },
  { k: "유보율", v: "1,750%", d: "자본금 대비 쌓인 잉여금의 비율이에요.", f: "(자본잉여금 + 이익잉여금) ÷ 자본금 × 100" },
];
/* 레이더 꼭짓점 순서: 위 부채비율, 오른쪽 위 유보율, 오른쪽 아래 이자보상비율, 왼쪽 아래 당좌비율, 왼쪽 위 유동비율 */
const HX = 40, HL = 310 + 110, HW = 330 + 60; // 레이더 살짝 안쪽, 오른쪽 지표 목록 넓힘
const AX = ["부채비율", "유보율", "이자보상비율", "당좌비율", "유동비율"];
const PTS: [number, number][] = [[150, 96], [213, 129.5], [194.5, 211.5], [113, 201], [89, 130]];
const LBL: [number, number][] = [[128, 42], [238, 114], [206, 219], [49, 219], [17, 114]];
function Health({ s }: { s: Stock }) {
  const [sel, setSel] = useState<string | null>(null);
  const sk = s.code === SK, seed = s.seed;
  const isNull = (name: string) => FIN_CO.has(s.code) && (name === "유동비율" || name === "당좌비율"); /* 금융업은 값이 없음 → — */
  const k = (i: number) => (isNull(AX[i]) ? 0 : sk ? 1 : 0.82 + ((Math.sin(seed * 7.1 + i * 2.3) + 1) / 2) * 0.3);
  const pts = PTS.map(([x, y], i) => [150 + (x - 150) * k(i), 150 + (y - 150) * k(i)] as const);
  const val = (h: (typeof HEALTH)[number]) => { if (isNull(h.k)) return "—"; if (sk) return h.v; const i = AX.indexOf(h.k); const n = parseFloat(h.v.replace(/,/g, "")) * k(i); return (h.v.endsWith("배") ? Math.round(n) + "배" : Math.round(n).toLocaleString("ko-KR") + "%"); };
  const ring = (r: number) => [0, 1, 2, 3, 4].map((i) => { const a = -Math.PI / 2 + (i * 2 * Math.PI) / 5; return `${(150 + Math.cos(a) * r).toFixed(1)},${(150 + Math.sin(a) * r).toFixed(1)}`; }).join(" ");
  const cur = HEALTH.find((h) => h.k === sel);
  return (
    <Card className="flex h-[404px] flex-col items-start gap-5 p-6">
      <div className="flex h-[25px] w-[810px] items-center justify-between">
        <p className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#191f28]">기업 건전성</p>
        <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b7684]">2026년 06월 기준</p>
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
            <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#6b788c]">바깥 테두리는 메모스톡 자체 기준 · 예시 수치</p>
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
        <p className="min-w-0 flex-1 text-[14px] leading-[1.65] text-[#191f28]">{OVERVIEW[s.code] ?? `${s.name}은(는) ${s.market}에 상장된 기업입니다. 업황과 실적 발표에 따라 주가가 움직이는 종목이에요.`}</p>
      </Card>
      <div className="flex w-[860px] flex-col items-start gap-6"><PriceChart s={s} /><Quote s={s} ctl={ctl} /></div>
      <Financials s={s} ctl={ctl} />
      <div className="flex w-[860px] flex-col items-start gap-6"><Profit ctl={ctl} s={s} /><Health s={s} /></div>
    </div>
  );
}
