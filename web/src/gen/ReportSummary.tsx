/* AI 주간보고서 · 스튜디오 요약 (412) — 만든 보고서 데이터로 그려요. 모양은 Figma 'report summary' 그대로 */
import type { Made, ReportStock, WeeklyReport } from "../api/types";
import { api } from "../api";

const UPC = "#e5484d", DNC = "#2f6fe0";
export const sign = (v: number) => `${v > 0 ? "+" : v < 0 ? "-" : ""}${Math.abs(v).toFixed(1)}%`;
const day = (d: string) => { const t = new Date(d + "T12:00:00+09:00"); return `${t.getMonth() + 1}.${String(t.getDate()).padStart(2, "0")}(${"일월화수목금토"[t.getDay()]})`; };
export const reportRange = (r: WeeklyReport) => `${day(r.from)} ~ ${day(r.to)}`;
export const reportWeek = (r: WeeklyReport) => { const t = new Date(r.to + "T12:00:00+09:00"); return `${t.getFullYear()}년 ${t.getMonth() + 1}월 ${Math.ceil(t.getDate() / 7)}주`; };
export function Mini({ v, w = 50, h = 20 }: { v: number[]; w?: number; h?: number }) {
  const mn = Math.min(...v), mx = Math.max(...v), up = v[v.length - 1] >= v[0], c = up ? UPC : DNC;
  const pts = v.map((x, i) => [0.9 + (i / (v.length - 1)) * (w - 2), 0.9 + ((mx - x) / (mx - mn || 1)) * (h - 2)] as const);
  const [ex, ey] = pts[pts.length - 1];
  return (
    <div className="relative shrink-0" style={{ width: w + 2, height: h + 2 }}>
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} fill="none" className="absolute left-0 top-0"><path d={pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(2)} ${p[1].toFixed(2)}`).join("")} stroke={c} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" /></svg>
      <div className="absolute h-[5px] w-[5px] rounded-full" style={{ left: ex - 2.5, top: ey - 2.5, background: c }} />
    </div>
  );
}
export function StockRow({ s, first }: { s: ReportStock; first: boolean }) {
  const i = api.market.info(s.stock_code);
  const c = s.counts, bits = [c.공시 ? `공시 ${c.공시}` : "", c.뉴스 ? `뉴스 ${c.뉴스}` : ""].filter(Boolean);
  const memo = s.memo_links.length ? `메모 ${s.memo_links.length}개와 연결` : "";
  return (
    <div data-report-row={s.stock_code} className={"flex gap-[12px] items-center py-[12px] px-[14px] self-stretch" + (first ? "" : " border-t border-[#eef0f3]")}>
      <div className="dk-keep flex h-[28px] w-[28px] shrink-0 items-center justify-center rounded-[8.4px]" style={{ background: i?.logo_bg ?? "#111" }}><p className="whitespace-nowrap text-center font-bold" style={{ color: i?.logo_ink ?? "#fff", fontSize: (i?.logo.length ?? 1) > 1 ? 11 : 15 }}>{i?.logo}</p></div>
      <div className="flex min-w-0 flex-1 flex-col items-start gap-[2px]">
        <p className="w-full truncate text-[15px] font-bold text-[#15171a]">{s.name}</p>
        <p className="w-full truncate text-[14px] text-[#747d8d]">{[bits.length ? bits.join(" · ") : "새 소식 없음", memo || (bits.length ? "" : "연결된 메모 없음")].filter(Boolean).join(" · ")}</p>
      </div>
      <Mini v={s.closes.slice(1)} />
      <p className="w-[54px] shrink-0 text-right text-[15px] font-bold" style={{ color: s.pct >= 0 ? UPC : DNC }}>{sign(s.pct)}</p>
    </div>
  );
}

export function ReportSummary({ r, made, onDetail }: { r: WeeklyReport; made: Made; onDetail: () => void }) {
  const M = [["코스피", r.market.kospi], ["코스닥", r.market.kosdaq], ["원/달러", r.market.usd]] as const;
  return (
    <div data-report-summary className="relative flex w-full flex-col items-start gap-[16px] overflow-hidden">
      <div className="flex flex-col items-start gap-[4px] self-stretch">
        <p className="text-[14px] font-medium text-[#747d8d]">MEMO'S 주간보고서 · {reportWeek(r)}</p>
        <p className="text-[22px] font-bold text-[#15171a]">{made.title}</p>
        <p className="text-[14px] text-[#747d8d]">{reportRange(r)} · 거래일 5일 · {r.stocks.length}종목</p>
      </div>
      <div className="flex flex-col items-start gap-[6px] self-stretch rounded-[12px] bg-[#f5f6f8] px-[16px] py-[14px]">
        <p className="text-[15px] font-bold text-[#575b63]">이번 주 한눈에</p>
        <p className="self-stretch text-[15px] leading-[23px] text-[#2b2f36]">{r.summary}</p>
      </div>
      <div className="flex items-start gap-[8px] self-stretch">
        {M.map(([n, v]) => (
          <div key={n} className="flex min-w-0 flex-1 flex-col items-start gap-[2px] rounded-[10px] bg-[#f5f6f8] px-[12px] py-[10px]">
            <p className="text-[14px] text-[#747d8d]">{n}</p>
            <p className="text-[15px] font-bold" style={{ color: v >= 0 ? UPC : DNC }}>{sign(v)}</p>
          </div>
        ))}
      </div>
      <p className="text-[15px] font-bold text-[#15171a]">종목별 흐름</p>
      <div className="flex flex-col items-start self-stretch overflow-hidden rounded-[12px] border border-[#e8ecf3]">
        {r.stocks.map((s, i) => <StockRow key={s.stock_code} s={s} first={i === 0} />)}
      </div>
      <button data-act="detail" onClick={onDetail} className="flex items-center justify-center self-stretch rounded-[12px] bg-[#15171a] py-[13px] text-[15px] font-bold text-white hover:bg-[#2a2c31]">자세히 보기</button>
      <p className="self-stretch text-[14px] leading-[21px] text-[#8e8a97]">공시·뉴스·시세에서 가져온 정보예요. 투자 권유나 주가 예측이 아니에요.</p>
    </div>
  );
}
