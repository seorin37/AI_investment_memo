/* MEMO'S API — 화면은 이 파일의 api 객체만 써요.
   지금은 가상 서버(mock)가 답해요. 백엔드가 준비되면 VITE_API=http 로 바꾸고 http.ts 를 채우면 돼요.
   함수는 값 또는 Promise 를 돌려줄 수 있어요(MaybeP). 화면은 useQ 훅으로 받아요. */
import type { AudioEp, Candle, ChartRange, Financials, IndexQuote, LabDir, LabResult, MacroRow, MarketEvent, Memo, NewsItem, Profile, Quiz, Quote, StockInfo, TrackItem, UpdateItem, UserState, WeeklyReport } from "./types";
import * as M from "./mock/market";
import * as AI from "./mock/ai";
import { db } from "./mock/db";
import { seedState } from "./mock/seed";

export type MaybeP<T> = T | Promise<T>;
export type TLItem = AI.TLItem;

export const api = {
  /* 로그인 · 내 데이터 (GET/PUT /api/me/state) */
  auth: {
    session: (): MaybeP<UserState | null> => db.current(),
    login: (p: Profile["provider"]): MaybeP<{ state: UserState; is_new: boolean }> => db.login(p),
    logout: (): MaybeP<void> => db.logout(),
    withdraw: (): MaybeP<void> => db.withdraw(),
  },
  me: {
    save: (s: UserState): MaybeP<void> => db.save(s),
    demoAccount: (s: UserState): MaybeP<UserState> => seedState(s), // 발표용 예시 데이터 (mock 전용)
  },
  /* 시장 데이터 (GET) */
  market: {
    universe: (): MaybeP<StockInfo[]> => M.universe(),
    info: (code: string): StockInfo | undefined => M.info(code),
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
    findItems: (text: string, code: string): MaybeP<TrackItem[]> => AI.findItems(text, code),
    timeline: (m: Memo): TLItem[] => AI.timeline(m),
    unseen: (m: Memo): number => AI.unseen(m),
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
