/* MEMO'S API — 화면은 이 파일의 api 객체만 써요.
   기본은 가상 서버(mock, 시연 모드). VITE_USE_API=true 이면 실제 FastAPI(/api/v1)에 있는 것만 http(remote.ts)로 바꿔요.
   백엔드에 없는 기능(시세·소식·지수·스튜디오 …)은 API 모드에서도 mock 그대로예요 (WEB_README.md 'API 모드').
   함수는 값 또는 Promise 를 돌려줄 수 있어요(MaybeP). 화면은 useQ 훅으로 받아요. */
import type { AudioEp, Candle, ChartRange, Financials, IndexQuote, LabDir, LabResult, MacroRow, MarketEvent, Memo, NewsItem, Profile, Quiz, Quote, StockInfo, TrackItem, UpdateItem, UserState, WeeklyReport } from "./types";
import * as M from "./mock/market";
import * as AI from "./mock/ai";
import { db } from "./mock/db";
import { seedState } from "./mock/seed";
import { API_MODE } from "./config";
import { remote, serverInfo } from "./remote";

export { API_MODE };
export type MaybeP<T> = T | Promise<T>;
export type TLItem = AI.TLItem;
/* 화면에 보이는 내 종목 가격. 시세 API가 생기면 이 한 곳(market.price)만 바꾸면 돼요 */
export type PriceView = { price: number; chg: number; pct: number; as_of: string };

export const api = {
  /* 로그인 · 내 데이터 — 시연: localStorage 가상 서버 / API: /auth · /stocks · 보드 API + 서버에 없는 것은 이 기기 저장 */
  auth: {
    session: (): MaybeP<UserState | null> => (API_MODE ? remote.session() : db.current()),
    login: (p: Profile["provider"]): MaybeP<{ state: UserState; is_new: boolean }> => (API_MODE ? remote.login(p) : db.login(p)),
    logout: (): MaybeP<void> => (API_MODE ? remote.logout() : db.logout()),
    withdraw: (): MaybeP<void> => { if (API_MODE) throw new Error("회원 탈퇴는 아직 지원하지 않아요"); return db.withdraw(); },
  },
  me: {
    save: (s: UserState): MaybeP<void> => (API_MODE ? remote.save(s) : db.save(s)),
    demoAccount: (s: UserState): MaybeP<UserState> => seedState(s), // 발표용 예시 데이터 (mock 전용)
  },
  /* 시장 데이터 (GET) — 백엔드에 시세·소식 API가 없어 API 모드에서도 mock. 종목 검색만 /stocks/search */
  market: {
    universe: (): MaybeP<StockInfo[]> => M.universe(),
    info: (code: string): StockInfo | undefined => M.info(code) ?? (API_MODE ? serverInfo(code) : undefined),
    search: (q: string): Promise<{ stock_code: string; name: string; market: string }[]> => remote.search(q), // API 모드 전용
    price: (code: string): PriceView | null => { if (API_MODE) return null; const q = M.quote(code); return { price: q.price, chg: q.chg, pct: q.pct, as_of: q.as_of }; },
    popular: (): string[] => M.POPULAR,          // 검색창 추천 종목 코드
    onboardPicks: (): string[] => M.ONBOARD_PICKS, // 첫 가입 종목 고르기 목록
    quote: (code: string): MaybeP<Quote> => M.quote(code),
    candles: (code: string, range: ChartRange): MaybeP<Candle[]> => M.candles(code, range),
    closes: (code: string, n: number): MaybeP<Candle[]> => M.closes(code, n),
    financials: (code: string): MaybeP<Financials> => M.financials(code),
    updates: (codes: string[], days = 30): MaybeP<UpdateItem[]> => M.updates(codes, days),
    news: (codes: string[]): MaybeP<NewsItem[]> => M.news(codes),
    indices: (): MaybeP<IndexQuote[]> => M.indices(),
    indexSeries: (key: string, range: "1일" | "1주" | "1달" | "1년"): MaybeP<number[]> => M.indexSeries(key, range),
    macro: (): MaybeP<MacroRow[]> => M.macro(),
    schedule: (codes: string[]): MaybeP<MarketEvent[]> => M.schedule(codes),
    lastClose: (): string => M.lastClose(),
    tradingDays: (n: number): string[] => M.tradingDays(n),
  },
  /* AI (POST) */
  ai: {
    findItems: (text: string, code: string): MaybeP<TrackItem[]> => (API_MODE ? [] : AI.findItems(text, code)), // API 모드는 linkStart가 실제 분석 결과를 줌
    /* API 모드 전용: AI 연결 켜기(PUT /memos/{id}/ai-link) → analysis.items / 창을 닫을 때 켜둠·끔 */
    linkStart: (memoId: number) => remote.linkStart(memoId),
    linkEnd: (memoId: number, keep: boolean) => remote.linkEnd(memoId, keep),
    timeline: (m: Memo): TLItem[] => (API_MODE ? remote.timeline(m) : AI.timeline(m)),
    unseen: (m: Memo): number => (API_MODE ? remote.unseen(m) : AI.unseen(m)),
    audio: (codes: string[], days: 1 | 3 | 7, summary: boolean, memos: Memo[]): MaybeP<AudioEp> => AI.makeAudio(codes, days, summary, memos),
    report: (codes: string[], memos: Memo[], withMarket: boolean): MaybeP<WeeklyReport> => AI.makeReport(codes, memos, withMarket),
    lab: (code: string, vars: [string, LabDir][]): MaybeP<LabResult> => AI.makeLab(code, vars),
    quiz: (day?: string, force?: "ox" | "four"): MaybeP<Quiz> => AI.quizFor(day, force),
    labVars: AI.LAB_VARS,
  },
  /* 테스트용 */
  _mock: { setNow: M.setNow, wipe: db.wipeAll },
};

/* 가벼운 데이터 훅: 값이면 바로, Promise 면 로딩 후 */
import { useEffect, useRef, useState } from "react";
const QC = new Map<string, unknown>();
export function useQ<T>(key: string | null, f: () => MaybeP<T>): T | undefined {
  const [, force] = useState(0);
  const fr = useRef(f); fr.current = f;
  let v = key ? (QC.get(key) as T | undefined) : undefined;
  if (key && v === undefined) {
    const r = fr.current();
    if (!(r instanceof Promise)) { QC.set(key, r); v = r; }
  }
  useEffect(() => {
    if (!key || QC.has(key)) return;
    let alive = true;
    Promise.resolve(fr.current()).then((r) => { QC.set(key, r); if (alive) force((n) => n + 1); });
    return () => { alive = false; };
  }, [key]);
  return v;
}
export const clearQ = () => QC.clear();
