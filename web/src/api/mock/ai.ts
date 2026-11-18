/* 가상 AI — 메모에서 추적 항목 찾기 · 소식 매칭 · 스튜디오 결과 만들기 (규칙 기반)
   실제 서비스에서는 서버(LLM·RAG)가 하는 일이에요. 같은 입력이면 같은 결과가 나와요. */
import type { AudioEp, LabDir, LabPath, LabResult, Memo, Quiz, ReportStock, TrackItem, UpdateItem, WeeklyReport } from "../types";
import { closes, feedAll, indexHistory, info, lastClose, quote, rng, themesOf, tradingDays, universe, updates } from "./market";

/* ---------- 메모 → 추적 항목 ---------- */
const TOPIC: [RegExp, string, string, string, string[]][] = [
  [/실적|분기|어닝|영업이익|순이익|매출|보고서|가이던스|컨센/, "earn", "실적·사업 현황", "공시·뉴스 · 정기보고서와 실적 기사", ["실적", "보고서", "IR", "매출"]],
  [/배당|주주환원/, "div", "배당 정책", "공시 · 배당 관련 공시", ["배당", "주주환원"]],
  [/자사주|자기주식|소각/, "buyback", "자사주 매입", "공시 · 자기주식 취득·소각", ["자사주", "주주환원"]],
  [/수주|계약|공급|납품|고객사/, "order", "수주·공급 계약", "공시·뉴스 · 계약 공시와 기사", ["수주", "공급", "매출"]],
  [/투자|증설|공장|설비|캐파/, "capex", "투자·증설 소식", "공시·뉴스 · 시설투자 공시", ["투자", "시설투자"]],
  [/외국인|기관|수급|순매수/, "flow", "수급 변화", "뉴스 · 외국인·기관 매매 기사", ["수급"]],
  [/경쟁|점유율|가격 ?인하/, "comp", "경쟁 상황", "뉴스 · 업계 기사", ["경쟁"]],
  [/분위기|흐름|추세|급등|급락|변동|거래량|차트/, "move", "주가 흐름", "시세 · 큰 변동·거래량 급증", ["주가", "거래량"]],
  [/전망|목표가|리포트|증권사|분석/, "view", "증권사 분석", "뉴스 · 증권사 분석 기사", ["분석", "보고서"]],
];
const won = (n: number) => n.toLocaleString("ko-KR");
export function parsePrice(text: string): TrackItem["price"] | undefined {
  const m = text.replace(/,/g, "").match(/(\d+(?:\.\d+)?)\s*(만\s*원?|원)?\s*(?:선|대|근처|이)?\s*(밑|아래|미만|이하|빠지|떨어|깨지|위|이상|넘|돌파|오르)/);
  if (!m) return undefined;
  let v = parseFloat(m[1]); if (/만/.test(m[2] ?? "")) v *= 10000; else if (!m[2] && v < 10000) v *= 10000;
  if (v < 100) return undefined;
  return { v: Math.round(v), dir: /밑|아래|미만|이하|빠지|떨어|깨지/.test(m[3]) ? "down" : "up" };
}
export function findItems(text: string, code: string): TrackItem[] {
  const out: TrackItem[] = [];
  const p = parsePrice(text);
  if (p) out.push({ k: "price", t: `종가 ${p.v >= 10000 && p.v % 10000 === 0 ? `${p.v / 10000}만` : won(p.v)} 원 ${p.dir === "down" ? "이하" : "이상"}`, d: "가격 조건 · 전일 확정 종가로 코드가 계산해요", tags: ["가격 조건"], price: p });
  for (const [re, k, t, d, tags] of TOPIC) if (re.test(text)) out.push({ k, t, d, tags });
  const th = themesOf(code).filter((x) => text.toUpperCase().includes(x.toUpperCase()) || x.split(" ").some((w) => w.length > 1 && text.includes(w)));
  if (th.length) out.push({ k: "theme", t: `${th.slice(0, 2).join("·")} 소식`, d: "뉴스·공시 · 관련 기사와 공시", tags: th });
  if (!out.length) out.push({ k: "all", t: "이 종목의 중요한 공시·뉴스", d: "공시·뉴스 · 종목 전체에서 중요한 것만", tags: ["*"] });
  return out.slice(0, 4);
}

/* ---------- 메모에 붙은 소식 (AI 업데이트 타임라인) ---------- */
export type TLItem =
  | { kind: "공시" | "뉴스" | "주가"; at: string; title: string; body: string; src: string; url?: string; id: string }
  | { kind: "edit" | "first"; at: string; old: { title: string; body: string } }
  | { kind: "start"; at: string };
const LOOKBACK = 7; // AI 연결을 켜면 최근 7거래일 소식부터 찾아봐요
const fmtSrc = (u: UpdateItem) => { const d = new Date(u.at); return `${u.kind === "주가" ? "시세" : "출처"}  ${u.src} · ${d.getFullYear()}. ${String(d.getMonth() + 1).padStart(2, "0")}. ${String(d.getDate()).padStart(2, "0")}. ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
export function matched(m: Memo): TLItem[] {
  if (!m.ai || !m.ai_since) return [];
  const from = ymdOf(new Date(new Date(m.ai_since).getTime() - LOOKBACK * 1.4 * 864e5));
  const tracks = m.tracks ?? [];
  const tags = new Set(tracks.flatMap((t) => t.tags));
  const all = tags.has("*");
  const out: TLItem[] = [];
  for (const u of feedAll(m.stock_code)) {
    if (u.at.slice(0, 10) < from) continue;
    const hit = all ? !!u.important || u.kind === "공시" : u.tags.some((t) => tags.has(t));
    if (hit) out.push({ kind: u.kind, at: u.at, title: titleFor(u), body: u.summary + reason(u, tracks), src: fmtSrc(u), url: u.url, id: u.id });
  }
  const price = tracks.find((t) => t.price)?.price;
  if (price) {
    let near = false, hitP = false;
    for (const c of closes(m.stock_code, 60)) {
      if (c.t < from) continue;
      const gap = (c.c - price.v) / price.v;
      const reached = price.dir === "down" ? c.c <= price.v : c.c >= price.v;
      if (reached && !hitP) { hitP = true; out.push({ kind: "주가", at: c.t + "T15:30:00+09:00", id: "p" + c.t, title: `${pv(price.v)} 조건가에 도달했어요`, body: `종가 ${won(c.c)}원으로 설정한 조건(${pv(price.v)} ${price.dir === "down" ? "이하" : "이상"})에 닿았어요.`, src: `시세  한국거래소 종가 · ${c.t.replace(/-/g, ". ")}. 15:30\n설정한 가격 조건과 비교해 자동 계산했어요.` }); }
      else if (!reached && Math.abs(gap) < 0.05 && !near) { near = true; out.push({ kind: "주가", at: c.t + "T15:30:00+09:00", id: "q" + c.t, title: `${pv(price.v)} 조건가에 가까워졌어요`, body: `종가 ${won(c.c)}원으로, 설정한 ${pv(price.v)}까지 ${won(Math.abs(c.c - price.v))}원(${Math.abs(gap * 100).toFixed(1)}%) 남았어요.`, src: `시세  한국거래소 종가 · ${c.t.replace(/-/g, ". ")}. 15:30\n설정한 가격 조건과 비교해 자동 계산했어요.` }); }
      if (!reached && Math.abs(gap) >= 0.08) near = false;
    }
  }
  return out.sort((a, b) => b.at.localeCompare(a.at));
}
const pv = (v: number) => (v >= 10000 && v % 10000 === 0 ? `${v / 10000}만원` : `${won(v)}원`);
const titleFor = (u: UpdateItem) => (u.kind === "공시" && !/요|다$/.test(u.title) ? `${u.title} 공시가 나왔어요` : u.title);
function reason(u: UpdateItem, tracks: TrackItem[]) {
  const t = tracks.find((x) => x.tags.some((g) => u.tags.includes(g)));
  return t ? ` 메모에서 지켜보는 '${t.t}'와(과) 관련 있어요.` : "";
}
const ymdOf = (d: Date) => { const k = new Date(d.getTime() + (d.getTimezoneOffset() + 540) * 60000); return `${k.getFullYear()}-${String(k.getMonth() + 1).padStart(2, "0")}-${String(k.getDate()).padStart(2, "0")}`; };
export function timeline(m: Memo): TLItem[] {
  const tl: TLItem[] = [...matched(m)];
  const orig = m.edits[0] ?? m;
  tl.push({ kind: "first", at: m.created_at, old: { title: orig.title, body: orig.body } });
  m.edits.forEach((e) => tl.push({ kind: "edit", at: e.at, old: { title: e.title, body: e.body } }));
  if (m.ai && m.ai_since) tl.push({ kind: "start", at: m.ai_since });
  /* 소식이 먼저(최신순), 그 아래 메모 이력(수정 → AI 연결 시작 → 처음 메모) */
  return tl.sort((a, b) => rank(a) - rank(b) || b.at.localeCompare(a.at));
}
const rank = (x: TLItem) => (x.kind === "edit" ? 1 : x.kind === "start" ? 2 : x.kind === "first" ? 3 : 0);
export const unseen = (m: Memo) => matched(m).filter((x) => !m.seen_at || x.at > m.seen_at).length;

/* ---------- 스튜디오 ---------- */
const nm = (c: string) => info(c)?.name ?? c;
const josa = (w: string, a: string, b: string) => { const ch = w.charCodeAt(w.length - 1) - 0xac00; return ch >= 0 && ch < 11172 && ch % 28 ? a : b; };
const pctOf = (code: string, n: number) => { const c = closes(code, n + 1); return ((c[c.length - 1].c - c[0].c) / c[0].c) * 100; };
const idxPct = (key: string, n: number) => { const c = indexHistory(key, n + 1); return Math.round(((c[c.length - 1].c - c[0].c) / c[0].c) * 1000) / 10; };
const md = (s: string) => `${+s.slice(5, 7)}.${s.slice(8, 10)}`;

export function makeAudio(codes: string[], days: 1 | 3 | 7, summary: boolean, memos: Memo[]): AudioEp {
  const items = updates(codes, days);
  const ch: [string, string, number][] = []; const sc: [string, string][] = []; let t = 0;
  const add = (title: string, lines: [string, string][]) => { ch.push([String(ch.length + 1).padStart(2, "0"), title, t]); lines.forEach((l) => { sc.push(l); t += Math.max(6, Math.round(l[1].length / 7)); }); };
  add("오프닝", [["A · 메인", `오늘은 고르신 종목 ${codes.length}곳의 소식을 들려 드릴게요.`], ["B · 해설", days === 1 ? "직전 거래일에 나온 공시·뉴스·주가 움직임을 모았어요." : `최근 ${days}일 동안 나온 소식을 모았어요.`]]);
  if (summary) { const ix = idxPct("kospi", 1), kq = idxPct("kosdaq", 1), fx = idxPct("usd", 1); add("직전 거래일 증시 요약", [["A · 메인", `먼저 증시부터요. 코스피는 ${Math.abs(ix)}% ${ix >= 0 ? "올랐고" : "내렸고"}, 코스닥은 ${Math.abs(kq)}% ${kq >= 0 ? "올랐어요" : "내렸어요"}.`], ["B · 해설", `원/달러 환율은 ${Math.abs(fx)}% ${fx >= 0 ? "올랐어요" : "내렸어요"}.`]]); }
  for (const c of codes) {
    const mine = items.filter((u) => u.stock_code === c), name = nm(c), q = quote(c);
    const memo = memos.find((m) => m.stock_code === c && m.ai);
    if (!mine.length) { add(`${name} · 새 소식 없음`, [["A · 메인", `${name}${josa(name, "은", "는")} 이 기간에 새로 나온 소식이 없어요. 종가는 ${won(q.price)}원이에요.`]]); continue; }
    const lines: [string, string][] = [["A · 메인", `${name}로 가 볼까요? ${mine.length}건의 소식이 있었어요.${memo ? ` 전에 “${memo.title}” 메모를 남기셨죠?` : ""}`]];
    mine.slice(0, 3).forEach((u, i) => lines.push([i % 2 ? "A · 메인" : "B · 해설", `${u.kind === "공시" ? "공시로는" : u.kind === "뉴스" ? "뉴스로는" : "주가는"} ${u.title}. ${u.summary}`]));
    lines.push(["A · 메인", `종가는 ${won(q.price)}원, 전날보다 ${Math.abs(q.pct).toFixed(2)}% ${q.pct >= 0 ? "올랐어요" : "내렸어요"}.`]);
    add(name, lines);
  }
  add("마무리", [["B · 해설", "오늘 들은 소식은 투자 권유가 아니에요. 메모와 함께 한 번 더 확인해 보세요."], ["A · 메인", "다음에 또 만나요."]]);
  return { kind: "audio", days, dur: t, chapters: ch, script: sc };
}

export function makeReport(codes: string[], memos: Memo[], withMarket: boolean): WeeklyReport {
  const days = tradingDays(5);
  const stocks: ReportStock[] = codes.map((c) => {
    const cl = closes(c, 6), items = updates([c], 5);
    const counts = { 공시: 0, 뉴스: 0, 주가: 0 }; items.forEach((u) => counts[u.kind]++);
    const pct = Math.round(pctOf(c, 5) * 10) / 10;
    const links = memos.filter((m) => m.stock_code === c && m.ai).map((m) => ({ memo_id: m.id, title: m.title, n: matched(m).filter((x) => x.at.slice(0, 10) >= days[0]).length })).filter((x) => x.n > 0);
    const big = items.find((u) => u.kind === "공시") ?? items[0];
    const name = nm(c);
    const oneLine = items.length ? `${name}${josa(name, "은", "는")} 이번 주 ${pct >= 0 ? "+" : ""}${pct}% 움직였고, ${big ? `“${big.title}” 소식이 가장 눈에 띄었어요.` : "큰 소식은 없었어요."}` : `${name}${josa(name, "은", "는")} 이번 주 새 소식 없이 ${pct >= 0 ? "+" : ""}${pct}% 움직였어요.`;
    const check = [...new Set(items.filter((u) => u.kind !== "주가").slice(0, 2).map((u) => `${u.title} — 원문에서 숫자 확인하기`))];
    if (links.length) check.push(`메모 “${links[0].title}”에 붙은 소식 ${links[0].n}건 다시 보기`);
    return { stock_code: c, name, pct, close: cl[cl.length - 1].c, closes: cl.map((x) => x.c), days: cl.map((x) => md(x.t)), counts, items: items.slice(0, 6), memo_links: links, one_line: oneLine, check: check.length ? check : ["이번 주 새로 확인할 소식이 없어요"] };
  });
  const up = stocks.filter((s) => s.pct > 0).length, top = [...stocks].sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct))[0];
  const memoHit = stocks.find((s) => s.memo_links.length);
  const summary = stocks.length ? `내 종목 ${stocks.length}곳 중 ${up}곳이 올랐어요. ${top ? `${top.name}${josa(top.name, "이", "가")} ${top.pct >= 0 ? "+" : ""}${top.pct}%로 가장 크게 움직였고` : ""}${memoHit ? `, ${memoHit.name}에는 메모와 연결된 소식이 ${memoHit.memo_links.reduce((a, b) => a + b.n, 0)}건 있었어요.` : ", 메모와 연결된 새 소식은 없었어요."}` : "고른 종목이 없어요.";
  const flow = withMarket ? [`코스피는 한 주 동안 ${idxPct("kospi", 5) >= 0 ? "+" : ""}${idxPct("kospi", 5)}%, 코스닥은 ${idxPct("kosdaq", 5) >= 0 ? "+" : ""}${idxPct("kosdaq", 5)}% 움직였어요.`, `원/달러 환율은 ${idxPct("usd", 5) >= 0 ? "+" : ""}${idxPct("usd", 5)}% 변했어요.`] : [];
  return { kind: "report", from: days[0], to: days[days.length - 1], market: { kospi: idxPct("kospi", 5), kosdaq: idxPct("kosdaq", 5), usd: idxPct("usd", 5) }, stocks, summary, flow };
}

/* 실험실: 업종별 민감도 (환율, 유가, 국내 금리, 미국 금리) — 방향만 보여 줘요 */
const SENS: Record<string, [number, number, number, number, string[]]> = {
  반도체: [1, -0.3, -0.4, -0.8, ["수출 비중이 커서 원화가 약하면 원화 환산 매출이 늘어요", "전력·소재 원가가 조금 올라요", "설비투자 자금 조달 비용이 늘어요", "성장주 할인율이 올라 평가가 낮아지기 쉬워요"]],
  자동차: [1, -0.5, -0.4, -0.3, ["해외 판매가 많아 환율이 오르면 이익이 늘기 쉬워요", "원자재·물류비 부담이 커져요", "할부 금리가 올라 차 수요가 줄 수 있어요", "글로벌 소비 심리가 약해질 수 있어요"]],
  금융: [-0.2, 0, 1, 0.4, ["외화 자산 평가에 조금 영향이 있어요", "직접 영향은 크지 않아요", "예대마진(이자 차이)이 커지기 쉬워요", "채권 금리 상승은 보유 채권 평가에 부담이에요"]],
  보험: [0, 0, 0.6, 0.6, ["직접 영향은 크지 않아요", "직접 영향은 크지 않아요", "운용 수익률이 오르기 쉬워요", "투자 수익이 늘 수 있어요"]],
  인터넷: [-0.2, -0.1, -0.6, -1, ["해외 서버·콘텐츠 비용이 늘 수 있어요", "직접 영향은 작아요", "광고 경기가 둔해질 수 있어요", "성장주 할인율이 올라 평가가 낮아지기 쉬워요"]],
  "2차전지": [0.6, 0.3, -0.5, -0.9, ["수출이 많아 원화 환산 매출이 늘어요", "유가가 오르면 전기차 관심이 커지기도 해요", "투자 부담이 커져요", "성장주 할인율 영향이 커요"]],
  조선: [0.9, 0.5, -0.3, -0.2, ["달러로 받는 선박 대금이 원화로 늘어요", "유가가 오르면 해양·LNG 발주가 늘기 쉬워요", "선수금 운용에 소폭 영향", "직접 영향은 작아요"]],
};
const DEFAULT_SENS: [number, number, number, number, string[]] = [0.2, -0.4, -0.5, -0.4, ["수출입 비중에 따라 영향이 달라요", "원가 부담이 늘 수 있어요", "자금 조달 비용이 늘어요", "주식 평가에 부담이 될 수 있어요"]];
export const LAB_VARS = ["원/달러 환율", "국제유가(WTI)", "한국 기준금리", "미국 10년물 국채금리"] as const;
export function makeLab(code: string, vars: [string, LabDir][]): LabResult {
  const i = info(code), sec = i?.financial ? (i.sector === "보험" ? "보험" : "금융") : i?.sector ?? "", s = SENS[sec] ?? DEFAULT_SENS;
  let score = 0; const paths: LabPath[] = [];
  vars.forEach(([v, d]) => {
    const k = LAB_VARS.indexOf(v as (typeof LAB_VARS)[number]); if (k < 0 || d === "유지") return;
    const w = s[k] as number;
    const sign = (Math.sign(w) * (d === "상승" ? 1 : -1)) as 1 | -1 | 0;
    score += w * (d === "상승" ? 1 : -1);
    paths.push({ from: `${v} ${d}`, to: sign > 0 ? "실적·평가에 긍정적" : sign < 0 ? "실적·평가에 부담" : "영향 작음", why: d === "상승" ? s[4][k] : s[4][k].replace(/오르면|늘어요|늘기 쉬워요|커져요/g, (w) => ({ 오르면: "내리면", 늘어요: "줄어요", "늘기 쉬워요": "줄기 쉬워요", 커져요: "작아져요" } as Record<string, string>)[w]), sign });
  });
  const verdict = score > 0.3 ? "긍정" : score < -0.3 ? "부정" : "중립";
  return { kind: "lab", stock_code: code, name: i?.name ?? code, vars, score: Math.round(score * 100) / 100, verdict, paths, notes: [`${i?.sector ?? "이 업종"} 기업에 흔히 나타나는 영향 경로를 보여 드렸어요.`, "실제 주가는 수급·실적·심리 등 다른 요인으로도 크게 움직여요."] };
}

export function quizFor(day = lastClose(), force?: "ox" | "four"): Quiz {
  const r = rng("quiz" + day), d = new Date(day + "T00:00:00+09:00");
  const natural = r() < 0.5 ? "ox" : "four", type = force ?? natural, tag = type !== natural ? "-" + type : "";
  const label = `${d.getMonth() + 1}월 ${d.getDate()}일(${"일월화수목금토"[d.getDay()]})`;
  const ix = indexHistory("kospi", 2), up = ix[1].c >= ix[0].c, pct = ((ix[1].c - ix[0].c) / ix[0].c) * 100;
  if (type === "ox") {
    const ask = r() < 0.5; // "올랐다"고 묻거나 "내렸다"고 묻기
    const truth = ask ? up : !up;
    return { id: "q" + day + tag, date: day, label, type: "ox", q: `${label} 코스피는 전 거래일보다 ${ask ? "올라서" : "내려서"} 마감했다.`, options: ["O", "X"], answer: truth ? 0 : 1, exp: `코스피는 ${ix[1].c.toLocaleString("en-US", { minimumFractionDigits: 2 })}로 마감해 전 거래일보다 ${Math.abs(pct).toFixed(2)}% ${up ? "올랐어요" : "내렸어요"}. 지수가 오르면 빨간색, 내리면 파란색으로 표시해요.`, concept: "지수의 등락률은 전 거래일 종가와 비교해 계산해요.", src: "출처 · 한국거래소 지수 종가 (가상 데이터)" };
  }
  const pool = universe().slice(0, 12).map((s) => ({ s, v: quote(s.stock_code).value }));
  const top = [...pool].sort((a, b) => b.v - a.v)[0];
  const opts = [top, ...pool.filter((x) => x !== top).sort(() => r() - 0.5).slice(0, 3)].sort(() => r() - 0.5);
  return { id: "q" + day + tag, date: day, label, type: "four", q: `${label} 이 중 거래대금이 가장 많았던 종목은?`, options: opts.map((x) => x.s.name), answer: opts.indexOf(top), exp: `${top.s.name}의 거래대금은 약 ${Math.round(top.v / 1e8).toLocaleString("ko-KR")}억 원으로 보기 중 가장 많았어요. 거래대금은 거래량에 가격을 곱한 값이에요.`, concept: "거래대금은 하루 동안 거래된 주식 금액을 모두 더한 값이에요.", src: "출처 · 한국거래소 종목별 거래대금 (가상 데이터)" };
}
