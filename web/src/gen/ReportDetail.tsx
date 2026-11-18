/* AI 주간보고서 · 자세히 보기 (가운데 860) — 만든 보고서 데이터로 그려요. 모양은 Figma 4111:68163 v3 그대로 */
import type { Made, ReportStock, WeeklyReport } from "../api/types";
import { api } from "../api";
import { reportRange, reportWeek, sign } from "./ReportSummary";

const UPC = "#e5484d", DNC = "#2f6fe0";
const won = (n: number) => n.toLocaleString("ko-KR");
const md = (iso: string) => { const d = new Date(iso); return `${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`; };
const KCH: Record<string, string> = { 공시: "bg-[#fbeded] text-[#e5484d]", 뉴스: "bg-[#e8edf5] text-[#15171a]", 주가: "bg-[#e6f0e2] text-[#1e8e4e]" };

function HeroCard({ s }: { s: ReportStock }) {
  const i = api.market.info(s.stock_code), v = s.closes.slice(1), mn = Math.min(...v), mx = Math.max(...v), c = s.pct >= 0 ? "#FF7B80" : "#7FA8FF";
  return (
    <div className="flex min-w-0 flex-1 flex-col items-start gap-[10px] overflow-hidden rounded-[14px] border border-[rgba(255,255,255,0.1)] bg-[rgba(255,255,255,0.07)] p-[14px]">
      <div className="flex items-center gap-[8px]">
        <div className="dk-keep flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-[6.6px]" style={{ background: i?.logo_bg }}><p className="text-center text-[11px] font-bold" style={{ color: i?.logo_ink ?? "#fff" }}>{i?.logo}</p></div>
        <p className="truncate text-[15px] font-bold text-white">{s.name}</p>
      </div>
      <div className="flex items-end justify-between self-stretch">
        <p className="text-[26px] font-bold" style={{ color: c }}>{sign(s.pct)}</p>
        <svg width="62" height="24" viewBox="0 0 62 24" fill="none"><path d={v.map((x, k) => `${k ? "L" : "M"}${(0.9 + (k / (v.length - 1)) * 60).toFixed(2)} ${(0.9 + ((mx - x) / (mx - mn || 1)) * 22).toFixed(2)}`).join("")} stroke={c} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </div>
      <p className="text-[15px] text-[#b6b0c9]">{[s.counts.공시 ? `공시 ${s.counts.공시}` : "", s.counts.뉴스 ? `뉴스 ${s.counts.뉴스}` : ""].filter(Boolean).join(" · ") || "새 소식 없음"}</p>
    </div>
  );
}

function Chart({ s }: { s: ReportStock }) {
  const W = 760, H = 210, v = s.closes, mn = Math.min(...v), mx = Math.max(...v), pad = (mx - mn) * 0.15 || mx * 0.01;
  const lo = mn - pad, hi = mx + pad, X = (k: number) => 56 + (k / (v.length - 1)) * (W - 76), Y = (x: number) => 14 + ((hi - x) / (hi - lo)) * (H - 44);
  const c = s.pct >= 0 ? UPC : DNC, unit = Math.pow(10, Math.floor(Math.log10(Math.max(1, (hi - lo) / 3)))), ticks = [0, 1, 2, 3].map((k) => Math.round((lo + ((hi - lo) * (3 - k)) / 3) / unit) * unit);
  const evDays = new Set(s.items.filter((u) => u.kind !== "주가").map((u) => u.at.slice(5, 10).replace("-", ".")));
  return (
    <svg data-report-chart width="100%" viewBox={`0 0 ${W} ${H}`} fill="none">
      {ticks.map((t) => <g key={t}><line x1="56" x2={W - 20} y1={Y(t)} y2={Y(t)} stroke="#eef0f3" /><text x="48" y={Y(t) + 4} textAnchor="end" fontSize="11" fill="#8b95a1">{won(Math.round(t))}</text></g>)}
      <line x1={X(0)} x2={W - 20} y1={Y(v[0])} y2={Y(v[0])} stroke="#9aa0aa" strokeDasharray="4 4" />
      <path d={v.slice(1).map((x, k) => `${k ? "L" : "M"}${X(k + 1).toFixed(1)} ${Y(x).toFixed(1)}`).join("")} stroke={c} strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
      {v.slice(1).map((x, k) => <circle key={k} cx={X(k + 1)} cy={Y(x)} r={evDays.has(s.days[k + 1]) ? 5 : 3} fill={evDays.has(s.days[k + 1]) ? "#15171a" : "#fff"} stroke={c} strokeWidth="2" />)}
      {s.days.slice(1).map((d, k) => <text key={d} x={X(k + 1)} y={H - 6} textAnchor="middle" fontSize="11" fill="#8b95a1">{d}</text>)}
      <text x={X(0) + 4} y={Y(v[0]) - 6} fontSize="11" fill="#8b95a1">지난주 종가</text>
    </svg>
  );
}

function StockSection({ s, onMemo }: { s: ReportStock; onMemo: (code: string, id?: number) => void }) {
  const i = api.market.info(s.stock_code), v = s.closes.slice(1);
  const big = s.items.find((u) => u.kind === "공시") ?? s.items[0];
  const story = s.items.length
    ? `${big ? `${md(big.at)} “${big.title}” 소식이 나왔고, ` : ""}한 주 동안 ${sign(s.pct)} 움직여 ${won(s.close)}원으로 마감했어요.`
    : `이번 주는 새 공시·뉴스 없이 ${sign(s.pct)} 움직여 ${won(s.close)}원으로 마감했어요.`;
  return (
    <section data-report-stock={s.stock_code} className="flex w-full flex-col gap-4 rounded-[20px] border border-[#e8ecf3] bg-white p-6">
      <div className="flex items-center gap-3">
        <div className="dk-keep flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px]" style={{ background: i?.logo_bg }}><p className="text-[15px] font-bold" style={{ color: i?.logo_ink ?? "#fff" }}>{i?.logo}</p></div>
        <p className="min-w-0 flex-1 truncate text-[22px] font-bold text-[#15171a]">{s.name}</p>
        <p className="text-[20px] font-bold text-[#15171a]">{won(s.close)}원</p>
        <p className="w-[72px] text-right text-[17px] font-bold" style={{ color: s.pct >= 0 ? UPC : DNC }}>{sign(s.pct)}</p>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {([["주간 등락", sign(s.pct)], ["주간 최고", won(Math.max(...v))], ["주간 최저", won(Math.min(...v))]] as const).map(([l, x]) => <div key={l} className="flex flex-col gap-[2px] rounded-[12px] bg-[#f5f6f8] px-4 py-3"><span className="text-[14px] text-[#747d8d]">{l}</span><span className="text-[17px] font-bold text-[#15171a]">{x}</span></div>)}
      </div>
      <Chart s={s} />
      <p className="text-[13px] leading-[20px] text-[#8b95a1]">검은 점은 공시·뉴스가 나온 날이에요</p>
      <p className="break-keep text-[15px] leading-[24px] text-[#2b2f36]">{story}</p>
      <div className="flex flex-col gap-2">
        <p className="text-[17px] font-bold text-[#15171a]">이번 주 소식</p>
        {s.items.length === 0 && <p className="text-[14px] text-[#8b95a1]">새로 나온 소식이 없어요</p>}
        {s.items.map((u) => (
          <a key={u.id} href={u.url} target="_blank" rel="noreferrer" className="flex items-center gap-3 rounded-[12px] px-3 py-[10px] hover:bg-[#f7f8fa]">
            <span className={"shrink-0 rounded-[6px] px-2 py-[2px] text-[13px] font-medium " + KCH[u.kind]}>{u.kind}</span>
            <span className="w-[44px] shrink-0 text-[13px] text-[#8b95a1]">{md(u.at)}</span>
            <span className="min-w-0 flex-1 truncate text-[15px] font-medium text-[#15171a]">{u.title}</span>
            <span className="shrink-0 text-[13px] text-[#8b95a1]">{u.src}</span>
          </a>
        ))}
      </div>
      <div className="flex flex-col gap-2 rounded-[14px] bg-[#f7f8fa] p-4">
        <div className="flex items-center justify-between"><p className="text-[17px] font-bold text-[#15171a]">내 메모와의 연결</p>{s.memo_links[0] && <button data-act="memo" onClick={() => onMemo(s.stock_code, s.memo_links[0].memo_id)} className="text-[14px] font-bold text-[#575b63] hover:text-[#15171a]">원본 메모 보기 ›</button>}</div>
        {s.memo_links.length ? s.memo_links.map((l) => <p key={l.memo_id} className="break-keep text-[15px] leading-[23px] text-[#333d4b]">“{l.title}”에 이번 주 소식 {l.n}건이 붙었어요.</p>)
          : <div className="flex items-center justify-between gap-3"><p className="break-keep text-[15px] leading-[23px] text-[#747d8d]">이번 주 소식과 연결된 메모가 없어요.</p><button onClick={() => onMemo(s.stock_code)} className="shrink-0 text-[14px] font-bold text-[#575b63] hover:text-[#15171a]">메모 쓰기 ›</button></div>}
      </div>
      <div className="flex flex-col gap-2">
        <p className="text-[17px] font-bold text-[#15171a]">앞으로 지켜볼 것</p>
        {s.check.map((c) => <p key={c} className="flex items-start gap-2 break-keep text-[15px] leading-[23px] text-[#333d4b]"><span className="mt-[9px] h-[5px] w-[5px] shrink-0 rounded-full bg-[#15171a]" />{c}</p>)}
      </div>
    </section>
  );
}

export function ReportDetail({ r, made, onMemo }: { r: WeeklyReport; made: Made; onMemo: (code: string, id?: number) => void }) {
  const tot = r.stocks.reduce((a, s) => ({ d: a.d + s.counts.공시, n: a.n + s.counts.뉴스, m: a.m + s.memo_links.length }), { d: 0, n: 0, m: 0 });
  const made_ = new Date(made.created_at);
  return (
    <div data-report-detail className="flex flex-col gap-[20px]">
      <div className="relative flex w-full flex-col items-start gap-[18px] overflow-hidden rounded-[20px] bg-[linear-gradient(90deg,#17151f,#2e2550)] p-[28px]">
        <div className="flex items-center justify-between self-stretch">
          <p className="text-[15px] font-bold tracking-[1.6px] text-[#b9a8e8]">MEMO'S WEEKLY REPORT</p>
          <div className="rounded-[999px] bg-[rgba(255,255,255,0.12)] px-[10px] py-[4px]"><p className="text-[15px] font-medium text-white">{reportWeek(r)}</p></div>
        </div>
        <div className="flex flex-col items-start gap-[6px]">
          <p className="text-[30px] font-bold text-white">{made.title}</p>
          <p className="text-[15px] text-[#c9c3dc]">{reportRange(r)} · 거래일 5일 · {r.stocks.length}종목 · {md(made.created_at)} {String(made_.getHours()).padStart(2, "0")}:{String(made_.getMinutes()).padStart(2, "0")} 작성</p>
        </div>
        <div className="h-px self-stretch bg-[rgba(255,255,255,0.14)]" />
        <div className="grid w-full grid-cols-3 gap-[10px]">{r.stocks.slice(0, 6).map((s) => <HeroCard key={s.stock_code} s={s} />)}</div>
        <div className="flex gap-6">{([["공시", tot.d], ["뉴스", tot.n], ["메모와 연결", tot.m]] as const).map(([l, n]) => <p key={l} className="text-[15px] text-[#c9c3dc]">{l} <b className="text-white">{n}{l === "메모와 연결" ? "개" : "건"}</b></p>)}</div>
      </div>
      <div className="flex flex-col gap-2 rounded-[20px] bg-[#f5f6f8] p-6"><p className="text-[17px] font-bold text-[#575b63]">이번 주 한눈에</p><p className="break-keep text-[17px] leading-[27px] text-[#2b2f36]">{r.summary}</p></div>
      {r.flow.length > 0 && (
        <section className="flex flex-col gap-4 rounded-[20px] border border-[#e8ecf3] bg-white p-6">
          <p className="text-[20px] font-bold text-[#15171a]"><span className="mr-2 text-[#8b95a1]">01</span>국내 증시 주간 요약</p>
          <div className="grid grid-cols-3 gap-2">{([["코스피", r.market.kospi], ["코스닥", r.market.kosdaq], ["원/달러", r.market.usd]] as const).map(([l, v]) => <div key={l} className="flex flex-col gap-[2px] rounded-[12px] bg-[#f5f6f8] px-4 py-3"><span className="text-[14px] text-[#747d8d]">{l}</span><span className="text-[17px] font-bold" style={{ color: v >= 0 ? UPC : DNC }}>{sign(v)}</span></div>)}</div>
          {r.flow.map((f) => <p key={f} className="break-keep text-[15px] leading-[23px] text-[#333d4b]">{f}</p>)}
        </section>
      )}
      {r.stocks.map((s) => <StockSection key={s.stock_code} s={s} onMemo={onMemo} />)}
      <p className="text-center text-[14px] leading-[21px] text-[#8e8a97]">공시·뉴스·시세에서 가져온 정보예요. 투자 권유나 주가 예측이 아니에요.</p>
    </div>
  );
}
