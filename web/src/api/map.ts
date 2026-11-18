/* 서버 응답 → 기존 화면 데이터 모양(data.ts의 Stock · Memo · TL). 화면 컴포넌트는 그대로 두고 여기서만 바꾼다. */
import { ALL_STOCKS, NEW_LOGO, type ColorKey, type Hold, type Memo, type Stock, type TL, type UpKind } from "../data";
import type { ChecklistWire, MemoWire, MyStockWire, StockStatus, TimelineWire } from "./client";

export const toHold = (s: StockStatus): Hold => (s === "holding" ? "보유" : "관심");
export const toStatus = (h: Hold): StockStatus => (h === "보유" ? "holding" : "watching");

/* 시세 API가 아직 없어서(분류 C) 가격·등락은 0으로 둔다. 화면에서는 API 모드일 때 '시세 준비 중'으로 표시 (board.tsx StockHead). */
export function stockLook(code: string, name: string): { logo: string; logoBg: string } {
  const base = ALL_STOCKS.find((s) => s.code === code);
  if (base) return { logo: base.logo, logoBg: base.logoBg };
  const [logo, logoBg] = NEW_LOGO[code] ?? [name.slice(0, 1) || "?", "#111"];
  return { logo, logoBg };
}
export function toStock(w: MyStockWire): Stock {
  const code = w.code.trim(), name = w.name;
  const { logo, logoBg } = stockLook(code, name);
  return { code, name, short: logo, logo, logoBg, hold: toHold(w.status), market: w.market, price: 0, chg: 0, pct: 0, seed: Number(code.slice(-2)) || 5, unread: w.unread_updates ?? 0 };
}
export function newStock(code: string, name: string, market: string, hold: Hold): Stock {
  const { logo, logoBg } = stockLook(code, name);
  return { code, name, short: logo, logo, logoBg, hold, market, price: 0, chg: 0, pct: 0, seed: Number(code.slice(-2)) || 5 };
}

/* 기업정보 탭(분류 C) 예시 수치는 가격에서 계산하므로, API 모드에서도 같은 예시 가격을 넣어 둔다. 화면 위에 '예시 데이터' 안내가 붙음 (apimode.tsx) */
export function samplePriced(s: Stock): Stock {
  const base = ALL_STOCKS.find((x) => x.code === s.code);
  return base ? { ...s, price: base.price, chg: base.chg, pct: base.pct } : { ...s, price: 48250, chg: 650, pct: 1.37 };
}

/* 날짜 (한국 시간) */
const KST = (iso: string) => {
  const d = new Date(iso);
  const p = Object.fromEntries(new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false })
    .formatToParts(d).filter((x) => x.type !== "literal").map((x) => [x.type, x.value]));
  return { y: p.year, m: p.month, d: p.day, hh: p.hour === "24" ? "00" : p.hour, mm: p.minute };
};
export const mmdd = (iso: string) => { const k = KST(iso); return `${k.m}.${k.d}`; };
const md = (iso: string) => { const k = KST(iso); return `${+k.m}월 ${+k.d}일`; };
const full = (iso: string) => { const k = KST(iso); return `${k.y}. ${k.m}. ${k.d}. ${k.hh}:${k.mm}`; };

const COLORS: ColorKey[] = ["yellow", "blue", "pink", "green", "purple"];
export function toMemo(w: MemoWire, col: number): Memo {
  return {
    id: Number(w.id), code: w.stock_code.trim(), date: mmdd(w.created_at), title: w.title, body: w.body,
    color: COLORS.includes(w.color) ? w.color : "yellow", ai: w.ai_linked, pinned: w.pinned, badge: w.unread_updates ?? 0, col,
  };
}

export type Check = { t: string; d: boolean };
export type BoardChecklist = { title: string; items: Check[] };
export const toChecklist = (w: ChecklistWire): BoardChecklist => ({ title: w.title, items: w.items.map((i) => ({ t: i.text, d: i.done })) });

/* 메모 타임라인 → 메모 팝업 'AI 업데이트' 칸 (TL). 서버가 이미 최신순으로 준다. */
const KIND: Record<string, UpKind> = { news: "뉴스", disclosure: "공시", price: "주가" };
export function toTimeline(w: TimelineWire): { timeline: TL[]; tracks?: string; unread: string[] } {
  const timeline: TL[] = [];
  const unread: string[] = [];
  for (const e of w.entries) {
    if (e.kind === "update") {
      const u = e.update;
      if (!u.read) unread.push(u.id);
      timeline.push({ kind: KIND[u.type] ?? "뉴스", date: md(e.at), title: u.headline || u.title, body: u.summary ?? "", src: `출처  ${u.source || "—"} · ${full(u.published_at || e.at)}` });
    } else if (e.kind === "memo_created" || e.kind === "memo_edit") {
      const first = e.kind === "memo_created";
      timeline.push({ kind: first ? "first" : "edit", date: mmdd(e.at), old: { when: first ? `${md(e.at)} · 처음 작성한 메모` : `${md(e.at)} ${KST(e.at).hh}:${KST(e.at).mm} · 수정 당시 메모`, title: e.version.title, body: e.version.body.replace(/\n/g, " ") } });
    } else if (e.kind === "ai_linked") {
      timeline.push({ kind: "start", date: md(e.at) });
    }
  }
  const items = w.tracking_items ?? [];
  const price = items.filter((i) => i.type === "price_below" || i.type === "price_above").length, other = items.length - price;
  const tracks = [other ? `공시·뉴스 ${other}개` : "", price ? `가격 조건 ${price}개` : ""].filter(Boolean).join(" · ") || undefined;
  return { timeline, tracks, unread };
}
