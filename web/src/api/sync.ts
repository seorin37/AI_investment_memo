/* 내 데이터(UserState) ↔ 서버 동기화 (API 모드 전용, ee7a16e의 sync를 팀원 UserState 모양에 맞춤).
   화면은 지금처럼 act.* 로 상태만 바꾸고, store가 0.3초 모아 api.me.save(state)를 부르면 여기서
   '서버에 저장된 것으로 알고 있는 값(known)'과 비교해 필요한 요청만 한 줄로 보낸다.
   - 서버에 있는 것: 내 종목(보유/관심) · 메모(제목·본문·색·고정·AI 연결) · 체크리스트(종목마다 하나) · AI 업데이트 읽음
   - 삭제는 6초 뒤에 보낸다: 화면의 '되돌리기' 안에 다시 나타나면 보내지 않는다.
   - 요청이 실패하면 onError → 서버 상태를 다시 불러온다. 저장된 척하지 않기 위해서다.
   - 종목 순서 · 메모 칸/고정 시각/본 시각 · 보드 카드 순서는 저장할 API가 없어 이 기기(localStorage)에만 남는다 (remote.ts). */
import type { Checklist, Hold, Memo, MyStock, UserState } from "./types";
import { api, type ChecklistWire, type MemoColorWire, type StockStatus } from "./client";

export const toStatus = (h: Hold): StockStatus => (h === "보유" ? "holding" : "watching");
export type SyncSnapshot = Pick<UserState, "stocks" | "memos" | "checklists">;
/* 서버 id: 메모(로컬 id → 서버 id), 체크리스트(종목 코드 → 서버 체크리스트) */
export type ServerIds = { memos: Map<number, string>; checks: Map<string, ChecklistWire> };

type KnownMemo = { sid: string | null; code: string; title: string; body: string; color: string; pinned: boolean; ai: boolean; seen_at?: string };
type KnownCheck = { sid: string | null; title: string; items: { id: string; t: string; d: boolean }[] };

const DELETE_DELAY = 6000;
const memoOf = (m: Memo, sid: string | null): KnownMemo => ({ sid, code: m.stock_code, title: m.title, body: m.body, color: m.color, pinned: m.pinned, ai: m.ai, seen_at: m.seen_at });
const cleanItems = (c: Checklist) => c.items.filter((i) => i.t.trim()).map((i) => ({ text: i.t.trim(), done: i.d }));

export function createSync(hooks: { onError: (message: string) => void; unreadOf: (memoId: number) => string[]; markedRead: (memoId: number, ids: string[]) => void }) {
  let gen = 0;
  let queue: Promise<void> = Promise.resolve();
  let latest: SyncSnapshot = { stocks: [], memos: [], checklists: {} };
  const stocks = new Map<string, Hold>();
  const memos = new Map<number, KnownMemo>();
  const checks = new Map<string, KnownCheck>();
  const timers = new Map<string, number>();
  const linking = new Set<number>();

  /* 한 줄 대기열. 다시 불러오기(reset) 뒤에는 그 전에 쌓인 요청을 버린다. */
  const run = (fn: () => Promise<void>) => {
    const g = gen;
    queue = queue.then(async () => {
      if (g !== gen) return;
      try { await fn(); } catch (e) {
        if (g !== gen) return;
        gen++;
        hooks.onError(e instanceof Error ? e.message : "요청을 처리하지 못했어요");
      }
    });
  };
  const memoSid = (id: number) => { const s = memos.get(id)?.sid; if (!s) throw new Error("메모가 아직 서버에 저장되지 않았어요"); return s; };
  const later = (key: string, fn: () => void) => {
    if (timers.has(key)) return;
    timers.set(key, window.setTimeout(() => { timers.delete(key); fn(); }, DELETE_DELAY));
  };
  const cancel = (key: string) => { const t = timers.get(key); if (t !== undefined) { window.clearTimeout(t); timers.delete(key); } };

  function reset(s: SyncSnapshot, ids: ServerIds) {
    gen++;
    timers.forEach((t) => window.clearTimeout(t)); timers.clear();
    stocks.clear(); memos.clear(); checks.clear();
    s.stocks.forEach((x) => stocks.set(x.stock_code, x.hold));
    s.memos.forEach((m) => memos.set(m.id, memoOf(m, ids.memos.get(m.id) ?? null)));
    for (const [code, c] of Object.entries(s.checklists)) {
      const w = ids.checks.get(code);
      checks.set(code, { sid: w?.id ?? null, title: c.title, items: (w?.items ?? []).map((i) => ({ id: i.id, t: i.text, d: i.done })) });
    }
    latest = s;
  }

  function apply(next: SyncSnapshot) {
    latest = next;
    /* ---- 종목 ---- */
    const nextCodes = new Set(next.stocks.map((x: MyStock) => x.stock_code));
    for (const s of next.stocks) {
      cancel("s:" + s.stock_code);
      const known = stocks.get(s.stock_code);
      if (known === undefined) { stocks.set(s.stock_code, s.hold); run(async () => { await api.addStock(s.stock_code, toStatus(s.hold)); }); }
      else if (known !== s.hold) { stocks.set(s.stock_code, s.hold); run(async () => { await api.setStockStatus(s.stock_code, toStatus(s.hold)); }); }
    }
    for (const code of stocks.keys()) {
      if (nextCodes.has(code)) continue;
      later("s:" + code, () => {
        if (latest.stocks.some((x) => x.stock_code === code)) return;
        stocks.delete(code);
        run(async () => { await api.removeStock(code); });
      });
    }

    /* ---- 메모 ---- */
    const nextIds = new Set(next.memos.map((m) => m.id));
    for (const m of next.memos) {
      cancel("m:" + m.id);
      const k = memos.get(m.id);
      if (!k) {
        /* 새 메모 (휴지통 복원 포함). AI 연결은 연결 창에서 따로 켠다(ai-link) — 여기서는 항상 꺼진 채로 만든다 */
        const entry = memoOf(m, null); entry.ai = false;
        memos.set(m.id, entry);
        run(async () => {
          const w = await api.createMemo(m.stock_code, { title: m.title.trim() || "제목 없음", body: m.body, color: m.color as MemoColorWire, pinned: m.pinned, ai_linked: false });
          entry.sid = w.id;
        });
        continue;
      }
      const patch: Record<string, unknown> = {};
      if (k.title !== m.title) patch.title = m.title.trim() || "제목 없음";
      if (k.body !== m.body) patch.body = m.body;
      if (k.color !== m.color) patch.color = m.color;
      if (k.pinned !== m.pinned) patch.pinned = m.pinned;
      if (Object.keys(patch).length) run(async () => { await api.patchItem(memoSid(m.id), patch); });
      if (k.ai !== m.ai && !linking.has(m.id)) { const on = m.ai; run(async () => { await api.setAiLink(memoSid(m.id), on); }); }
      if (m.seen_at && k.seen_at !== m.seen_at) {
        const ids = hooks.unreadOf(m.id);
        if (ids.length) run(async () => { for (const id of ids) await api.markRead(id); hooks.markedRead(m.id, ids); });
      }
      Object.assign(k, { code: m.stock_code, title: m.title, body: m.body, color: m.color, pinned: m.pinned, seen_at: m.seen_at }, linking.has(m.id) ? {} : { ai: m.ai });
    }
    for (const id of memos.keys()) {
      if (nextIds.has(id)) continue;
      later("m:" + id, () => {
        if (latest.memos.some((x) => x.id === id)) return;
        const k = memos.get(id); memos.delete(id);
        if (k) run(async () => { const sid = k.sid; if (sid) await api.deleteItem(sid); });
      });
    }

    /* ---- 체크리스트 (종목마다 하나) ---- */
    for (const [code, c] of Object.entries(next.checklists)) {
      cancel("c:" + code);
      const k = checks.get(code);
      const items = cleanItems(c);
      if (!k) {
        const entry: KnownCheck = { sid: null, title: c.title, items: c.items.map((i) => ({ id: "", t: i.t, d: i.d })) };
        checks.set(code, entry);
        run(async () => {
          const w = await api.createChecklist(code, { title: c.title.trim() || "체크리스트", items });
          entry.sid = w.id; entry.items = w.items.map((i) => ({ id: i.id, t: i.text, d: i.done }));
        });
        continue;
      }
      const same = k.title === c.title && k.items.length === c.items.length && k.items.every((x, i) => x.t === c.items[i].t);
      if (same) {
        c.items.forEach((it, i) => {
          if (k.items[i].d === it.d) return;
          k.items[i].d = it.d;
          const ref = k.items[i], done = it.d;
          run(async () => { if (!k.sid || !ref.id) throw new Error("체크리스트가 아직 서버에 저장되지 않았어요"); await api.patchChecklistItem(k.sid, ref.id, done); });
        });
      } else {
        k.title = c.title; k.items = c.items.map((i) => ({ id: "", t: i.t, d: i.d }));
        run(async () => {
          if (!k.sid) throw new Error("체크리스트가 아직 서버에 저장되지 않았어요");
          const w = await api.patchItem<ChecklistWire>(k.sid, { title: c.title.trim() || "체크리스트", items });
          k.items = w.items.map((i) => ({ id: i.id, t: i.text, d: i.done }));
        });
      }
    }
    for (const code of checks.keys()) {
      if (code in next.checklists) continue;
      later("c:" + code, () => {
        if (code in latest.checklists) return;
        const k = checks.get(code); checks.delete(code);
        if (k) run(async () => { if (k.sid) await api.deleteItem(k.sid); });
      });
    }
  }

  /* 페이지를 떠날 때 기다리던 삭제를 바로 보낸다 */
  function flush() {
    const keys = [...timers.keys()];
    keys.forEach((key) => cancel(key));
    for (const key of keys) {
      const ref = key.slice(2);
      if (key.startsWith("s:")) { if (!latest.stocks.some((x) => x.stock_code === ref)) { stocks.delete(ref); void api.removeStock(ref, true).catch(() => {}); } }
      else if (key.startsWith("c:")) { const k = checks.get(ref); if (k?.sid && !(ref in latest.checklists)) { checks.delete(ref); void api.deleteItem(k.sid, true).catch(() => {}); } }
      else { const id = Number(ref); const k = memos.get(id); if (k?.sid && !latest.memos.some((x) => x.id === id)) { memos.delete(id); void api.deleteItem(k.sid, true).catch(() => {}); } }
    }
  }

  /* AI 연결 창: 메모가 서버에 저장될 때까지 기다린 뒤 서버 id (새 메모를 저장하자마자 연결 창이 열리는 경우) */
  async function waitSid(id: number, ms = 8000): Promise<string> {
    const t0 = Date.now();
    for (;;) {
      await queue;
      const s = memos.get(id)?.sid;
      if (s) return s;
      if (Date.now() - t0 > ms) throw new Error("메모가 아직 서버에 저장되지 않았어요");
      await new Promise((r) => window.setTimeout(r, 150));
    }
  }
  /* 연결 창이 열려 있는 동안은 그 메모의 AI 연결을 창이 직접 보낸다(ai-link). 창이 닫히면 서버 값으로 known을 맞춘다 */
  const hold = (id: number) => linking.add(id);
  const release = (id: number, on: boolean) => { linking.delete(id); const k = memos.get(id); if (k) k.ai = on; };

  return { reset, apply, flush, waitSid, hold, release, memoSid: (id: number) => memos.get(id)?.sid ?? null, sids: () => new Map([...memos].flatMap(([id, k]) => (k.sid ? [[id, k.sid] as const] : []))) };
}
export type Sync = ReturnType<typeof createSync>;
