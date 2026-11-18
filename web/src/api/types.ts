/* MEMO'S 프론트 ↔ 백엔드 데이터 모양 (API 계약)
   화면은 이 타입만 알면 돼요. 백엔드는 이 모양대로 JSON을 돌려주면 돼요. 자세한 설명은 web/API.md */

/* ---------- 종목 · 시세 ---------- */
export type Market = "KOSPI" | "KOSDAQ";
export type Hold = "보유" | "관심";
export type StockInfo = {
  stock_code: string; name: string; market: Market; sector: string;
  logo: string; logo_bg: string; logo_ink?: string;
  financial: boolean;            // 은행·보험·증권: 매출·영업이익 대신 '—'
  overview: string;              // 기업 개요 한 줄
  about?: string;                // 기업 개요 긴 설명 (기업 정보 화면, 없으면 화면이 만들어요)
};
export type Quote = {
  stock_code: string; price: number; chg: number; pct: number;
  open: number; high: number; low: number; prev_close: number;
  volume: number; value: number;  // 거래량(주), 거래대금(원)
  w52_high: number; w52_low: number; market_cap: number;
  per: number | null; pbr: number | null; eps: number | null; bps: number | null; div_yield: number | null;
  foreign_pct: number;
  as_of: string;                  // ISO, 장 마감 기준 시각
};
export type Candle = { t: string; o: number; h: number; l: number; c: number; v: number }; // t = YYYY-MM-DD
export type ChartRange = "1D" | "1W" | "1M" | "3M" | "1Y";

/* 재무 (분기) */
export type FinQuarter = {
  q: string; label: string;      // "26.2Q", "2026년 2분기"
  revenue: number | null; op: number | null; net: number | null; // 억 원
  op_margin: number | null; net_margin: number | null; roe: number | null; roa: number | null; // %
};
export type Health = { debt: number | null; reserve: number | null; interest: number | null; quick: number | null; current: number | null }; // %, 배
export type Financials = { stock_code: string; quarters: FinQuarter[] /* 오래된 → 최근, 12개 */; health: Health; health_prev: Health; as_of: string };

/* ---------- 소식 (공시 · 뉴스 · 주가) ---------- */
export type UpKind = "공시" | "뉴스" | "주가";
export type UpdateItem = {
  id: string; stock_code: string; kind: UpKind;
  title: string;                 // 한 줄 (카드 제목)
  summary: string;               // AI 요약 2~3문장
  at: string;                    // ISO
  src: string;                   // DART · 한국경제 · 시세 …
  url?: string;
  tags: string[];                // 메모 매칭용 주제 (실적, 배당, 자사주, 수주 …)
  important?: boolean;
};
export type NewsItem = { id: string; title: string; src: "연합뉴스" | "한국경제" | "매일경제" | "서울경제"; at: string; url: string; stock_codes: string[] };
export type IndexKey = "kospi" | "kosdaq" | "usd";
export type IndexQuote = { key: IndexKey; name: string; flag: string; v: number; c: number; p: number; as_of: string };
export type MacroRow = { name: string; v: string; c: string };
export type MarketEvent = { date: string; title: string; who: string };

/* ---------- 내 데이터 ---------- */
export type ColorKey = "yellow" | "green" | "blue" | "purple" | "pink";
export type TrackItem = { k: string; t: string; d: string; tags: string[]; price?: { v: number; dir: "down" | "up" } };
export type MemoEdit = { at: string; title: string; body: string };
export type Memo = {
  id: number; stock_code: string;
  title: string; body: string; color: ColorKey;
  created_at: string; updated_at: string;
  ai: boolean; ai_since?: string; tracks?: TrackItem[];
  pinned: boolean; pinned_at?: number; col: number;
  seen_at?: string;               // AI 업데이트를 마지막으로 본 시각 (새 소식 배지 계산)
  edits: MemoEdit[];             // 수정 전 내용 (오래된 순)
};
export type CheckItem = { id: number; t: string; d: boolean };
export type Checklist = { stock_code: string; title: string; items: CheckItem[]; updated_at: string };
export type Journal = { id: number; title: string; created_at: string; updated_at: string; body: string[]; html?: string; todo: { t: string; d: boolean }[]; pinned?: boolean };
export type MyStock = { stock_code: string; hold: Hold; added_at: string; order: number };
export type TrashKind = "메모" | "투자 기록" | "종목" | "체크리스트 항목";
export type TrashItem = { id: string; kind: TrashKind; title: string; sub: string; deleted_at: string; data: unknown };
export type Profile = { name: string; job: string; email: string; provider: "kakao" | "naver" | "google"; photo?: string; joined_at: string };
export type Settings = { noti_upd: boolean; noti_studio: boolean; dark: boolean };

/* 스튜디오 */
export type JobKind = "audio" | "report" | "lab";
export type LabDir = "상승" | "유지" | "하락";
export type Made = { id: number; kind: JobKind; title: string; stock_codes: string[]; created_at: string; meta: string; data: AudioEp | WeeklyReport | LabResult };
export type AudioEp = { kind: "audio"; days: number; dur: number; chapters: [string, string, number][]; script: [string, string][] };
export type ReportStock = {
  stock_code: string; name: string; pct: number; close: number; closes: number[]; days: string[];
  counts: { 공시: number; 뉴스: number; 주가: number };
  items: UpdateItem[]; memo_links: { memo_id: number; title: string; n: number }[];
  one_line: string; check: string[];
};
export type WeeklyReport = { kind: "report"; from: string; to: string; market: { kospi: number; kosdaq: number; usd: number }; stocks: ReportStock[]; summary: string; flow: string[] };
export type LabPath = { from: string; to: string; why: string; sign: 1 | -1 | 0 };
export type LabResult = { kind: "lab"; stock_code: string; name: string; vars: [string, LabDir][]; score: number; verdict: "긍정" | "부정" | "중립"; paths: LabPath[]; notes: string[] };
export type Quiz = { id: string; date: string; label: string; type: "ox" | "four"; q: string; options: string[]; answer: number; exp: string; concept: string; src: string };
export type QuizResult = { quiz_id: string; picked: number; correct: boolean; at: string };
export type Notif = { id: number; kind: "upd" | "studio"; t: string; s: string; at: string; read: boolean; stock_code?: string; memo?: number; made?: number };
export type Usage = { pct: number; reset_at: string };

/* 서버가 사용자 한 명에게 돌려주는 전체 상태 (처음 로그인 · 새로고침 때 한 번에 받음) */
export type UserState = {
  profile: Profile | null; settings: Settings;
  stocks: MyStock[]; memos: Memo[]; checklists: Record<string, Checklist>; journal: Journal[]; trash: TrashItem[];
  made: Made[]; quiz: QuizResult[]; notifs: Notif[]; usage: Usage;
  onboarded: boolean; coach_done: boolean; home: { mode: "template" | "custom"; widgets: string[]; board: { id: string; x: number; y: number; w: number; h: number }[] };
  recent: string[];
  /* 종목 보드의 카드 순서 (11.18): 종목 코드 → 왼쪽→오른쪽, 위→아래 순서의 "cl"(체크리스트)·"m{메모 id}". 3칸 격자로 그려요. 없으면 기본 순서 */
  boards?: Record<string, string[]>;
};
