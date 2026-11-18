/* 화면 상태 ↔ 서버 동기화.
   화면 컴포넌트는 지금처럼 setStocks · setMemos 로 상태만 바꾼다. 여기서 '서버에 저장된 것으로 알고 있는 값(known)'과
   새 상태를 비교해 필요한 API만 순서대로 보낸다 (종목 추가가 그 종목의 메모 저장보다 먼저 가도록 한 줄로 처리).
   - 삭제는 6초 뒤에 보낸다: 화면의 '되돌리기'(5초) 안에 다시 나타나면 보내지 않는다.
   - 요청이 실패하면 onError → 화면이 서버 상태를 다시 불러온다(reload). 저장된 척하지 않기 위해서다.
   - 메모 순서(열 위치) · 고정 시각 · 종목 순서는 저장할 API가 없어 이 기기 화면에서만 바뀐다 (분류 C). */
import type { Hold, Memo, Stock } from "../data";
import { api, type ChecklistWire, type MemoColorWire } from "./client";
import { toStatus, type BoardChecklist } from "./map";

export type SyncSnapshot = { stocks: Stock[]; memos: Memo[]; checks: Record<string, BoardChecklist> };
export type ServerIds = { memos: Map<number, string>; checks: Map<string, ChecklistWire> };

type KnownMemo = { sid: string | null; code: string; title: string; body: string; color: string; pinned: boolean; ai: boolean; badge: number };
type KnownCheck = { sid: string | null; title: string; items: { id: string; t: string; d: boolean }[] };

const DELETE_DELAY = 6000;
const memoOf = (m: Memo, sid: string | null): KnownMemo => ({ sid, code: m.code, title: m.title, body: m.body, color: m.color, pinned: m.pinned, ai: m.ai, badge: m.badge });
const cleanItems = (c: BoardChecklist) => c.items.filter((i) => i.t.trim()).map((i) => ({ text: i.t.trim(), done: i.d }));

export function createSync(onError: (message: string) => void) {
  let gen = 0;
  let queue: Promise<void> = Promise.resolve();
  let latest: SyncSnapshot = { stocks: [], memos: [], checks: {} };
  const stocks = new Map<string, Hold>();
  const memos = new Map<number, KnownMemo>();
  const checks = new Map<string, KnownCheck>();
  const unread = new Map<number, string[]>();
  const timers = new Map<string, number>();

  /* 한 줄 대기열. 다시 불러오기(reset) 뒤에는 그 전에 쌓인 요청을 버린다. */
  const run = (fn: () => Promise<void>) => {
    const g = gen;
    queue = queue.then(async () => {
      if (g !== gen) return;
      try { await fn(); } catch (e) {
        if (g !== gen) return;
        gen++;
        onError(e instanceof Error ? e.message : "요청을 처리하지 못했어요");
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
    stocks.clear(); memos.clear(); checks.clear(); unread.clear();
    s.stocks.forEach((x) => stocks.set(x.code, x.hold));
    s.memos.forEach((m) => memos.set(m.id, memoOf(m, ids.memos.get(m.id) ?? null)));
    for (const [code, c] of Object.entries(s.checks)) {
      const w = ids.checks.get(code);
      checks.set(code, { sid: w?.id ?? null, title: c.title, items: (w?.items ?? []).map((i) => ({ id: i.id, t: i.text, d: i.done })) });
    }
    latest = s;
  }

  function apply(next: SyncSnapshot) {
    latest = next;
    /* ---- 종목 ---- */
    const nextCodes = new Set(next.stocks.map((x) => x.code));
    for (const s of next.stocks) {
      cancel("s:" + s.code);
      const known = stocks.get(s.code);
      if (known === undefined) { stocks.set(s.code, s.hold); run(async () => { await api.addStock(s.code, toStatus(s.hold)); }); }
      else if (known !== s.hold) { stocks.set(s.code, s.hold); run(async () => { await api.setStockStatus(s.code, toStatus(s.hold)); }); }
    }
    for (const code of stocks.keys()) {
      if (nextCodes.has(code)) continue;
      later("s:" + code, () => {
        if (latest.stocks.some((x) => x.code === code)) return;
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
        const entry = memoOf(m, null);
        memos.set(m.id, entry);
        run(async () => {
          const w = await api.createMemo(m.code, { title: m.title.trim() || "제목 없음", body: m.body, color: m.color as MemoColorWire, pinned: m.pinned, ai_linked: m.ai });
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
      if (k.ai !== m.ai) { const on = m.ai; run(async () => { await api.setAiLink(memoSid(m.id), on); }); }
      if (k.badge > 0 && m.badge === 0) {
        run(async () => {
          let ids = unread.get(m.id);
          if (!ids) { const t = await api.timeline(memoSid(m.id)); ids = t.entries.flatMap((e) => (e.kind === "update" && !e.update.read ? [e.update.id] : [])); }
          for (const id of ids) await api.markRead(id);
          unread.delete(m.id);
        });
      }
      Object.assign(k, { code: m.code, title: m.title, body: m.body, color: m.color, pinned: m.pinned, ai: m.ai, badge: m.badge });
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
    for (const [code, c] of Object.entries(next.checks)) {
      const k = checks.get(code);
      const items = cleanItems(c);
      if (!k) {
        const entry: KnownCheck = { sid: null, title: c.title, items: c.items.map((i) => ({ id: "", ...i })) };
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
        k.title = c.title; k.items = c.items.map((i) => ({ id: "", ...i }));
        run(async () => {
          if (!k.sid) throw new Error("체크리스트가 아직 서버에 저장되지 않았어요");
          const w = await api.patchItem<ChecklistWire>(k.sid, { title: c.title.trim() || "체크리스트", items });
          k.items = w.items.map((i) => ({ id: i.id, t: i.text, d: i.done }));
        });
      }
    }
  }

  /* 페이지를 떠날 때 기다리던 삭제를 바로 보낸다 */
  function flush() {
    const keys = [...timers.keys()];
    keys.forEach((key) => cancel(key));
    for (const key of keys) {
      if (key.startsWith("s:")) { const code = key.slice(2); if (!latest.stocks.some((x) => x.code === code)) { stocks.delete(code); void api.removeStock(code, true).catch(() => {}); } }
      else { const id = Number(key.slice(2)); const k = memos.get(id); if (k?.sid && !latest.memos.some((x) => x.id === id)) { memos.delete(id); void api.deleteItem(k.sid, true).catch(() => {}); } }
    }
  }

  return { reset, apply, flush, setUnread: (id: number, ids: string[]) => unread.set(id, ids), memoSid: (id: number) => memos.get(id)?.sid ?? null };
}
export type Sync = ReturnType<typeof createSync>;
