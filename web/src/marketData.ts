/* 시장 카드·상세 공통 데이터: 지수 + 기간별 선 (208×40 좌표) */
import { api } from "./api";
import type { IndexQuote } from "./api/types";
import { FLAG1, FLAG2, FLAG3 } from "./gen/flags";
export type Range = "1일" | "1주" | "1달" | "1년";
export const RANGES: Range[] = ["1일", "1주", "1달", "1년"];
const FLAGS = { kospi: FLAG1, kosdaq: FLAG2, usd: FLAG3 } as const;
export type MkKey = "kospi" | "kosdaq" | "usd";
const nf = (n: number) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export function mkData(key: MkKey, r: Range) {
  const q = (api.market.indices() as IndexQuote[]).find((x) => x.key === key)!;
  const sr = api.market.indexSeries(key, r) as number[];
  const first = r === "1일" ? q.v - q.c : sr[0], last = sr[sr.length - 1];
  const all = [...sr, first], mn = Math.min(...all), mx = Math.max(...all);
  const Y = (v: number) => ((mx - v) / (mx - mn || 1)) * 40;
  const path = sr.map((v, i) => `${i ? "L" : "M"}${((i / (sr.length - 1)) * 208).toFixed(2)} ${Y(v).toFixed(2)}`).join("");
  const chg = last - first, pct = (chg / first) * 100, sign = chg >= 0 ? "+" : "−";
  return { q, sr, path, base: Y(first), up: chg >= 0, label: `${sign}${nf(Math.abs(chg))} (${sign}${Math.abs(pct).toFixed(2)}%)`, when: r === "1일" ? `${q.as_of.slice(5, 7)}.${q.as_of.slice(8, 10)} 종가 기준` : r, v: nf(last), name: q.name, flag: FLAGS[key] };
}
/* 기간별 x축 날짜 라벨 */
export function rangeLabels(r: Range): string[] {
  if (r === "1일") return ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:30"];
  const n = r === "1주" ? 5 : r === "1달" ? 22 : 250, d = api.market.tradingDays(n), k = r === "1주" ? 5 : 5;
  return Array.from({ length: k }, (_, i) => d[Math.round((i / (k - 1)) * (d.length - 1))]).map((t) => (r === "1년" ? `${t.slice(2, 4)}.${t.slice(5, 7)}` : `${t.slice(5, 7)}.${t.slice(8, 10)}`));
}
