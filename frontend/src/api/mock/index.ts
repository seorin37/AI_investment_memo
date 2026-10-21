/**
 * 메모리 기반 목업 API — 백엔드 없이 화면 개발(EXPO_PUBLIC_USE_MOCK=true).
 * 앱을 새로고침하면 시드 상태로 돌아갑니다.
 */
import { env } from '@/config/env';
import { uid, ymd } from '@/lib/format';
import type {
  AiUpdate,
  BoardItem,
  Candle,
  Checklist,
  HomeLayout,
  JournalEntry,
  Memo,
  MemoTimeline,
  MyStock,
  ReferenceBoard,
  Settings,
  StockProfile,
  TimelineEntry,
  TrashItem,
} from '@/types/models';
import type { Api, DeepPartial, PinnedMemo } from '../types';
import * as seed from './seed';

const clone = <T>(v: T): T => (v === undefined ? v : JSON.parse(JSON.stringify(v)));
const wait = <T>(v: T, ms = env.mockLatency): Promise<T> => new Promise((r) => setTimeout(() => r(clone(v)), ms));

// 가변 DB
const db = {
  user: clone(seed.user),
  stocks: clone(seed.myStocks),
  board: clone(seed.board),
  versions: clone(seed.memoVersions),
  aiUpdates: clone(seed.aiUpdates),
  updates: clone(seed.marketUpdates),
  readUpdates: new Set(seed.readUpdateIds),
  journal: clone(seed.journal),
  calendar: clone(seed.calendar),
  trash: clone(seed.trash),
  settings: clone(seed.settings),
  layout: { mode: 'unset', widgets: [] } as HomeLayout,
  trashPayload: new Map<string, { kind: TrashItem['kind']; data: unknown }>(),
  candles: new Map<string, Candle[]>(),
};

function candlesOf(code: string) {
  if (!db.candles.has(code)) db.candles.set(code, seed.genCandles(code));
  return db.candles.get(code)!;
}

const stockName = (code: string) =>
  db.stocks.find((s) => s.code === code)?.name ?? seed.stockMaster.find((s) => s.code === code)?.name ?? code;

function recountUnread() {
  for (const s of db.stocks) {
    s.unread_updates = db.aiUpdates.filter((u) => u.stock_code === s.code && !u.read).length;
  }
  for (const it of db.board) {
    if (it.kind === 'memo') it.unread_updates = db.aiUpdates.filter((u) => u.memo_id === it.id && !u.read).length;
  }
}

function deepMerge<T>(target: T, patch: DeepPartial<T>): T {
  const out = { ...target } as Record<string, unknown>;
  for (const [k, v] of Object.entries(patch as Record<string, unknown>)) {
    const cur = out[k];
    if (v && typeof v === 'object' && !Array.isArray(v) && cur && typeof cur === 'object' && !Array.isArray(cur)) {
      out[k] = deepMerge(cur, v as DeepPartial<typeof cur>);
    } else if (v !== undefined) out[k] = v;
  }
  return out as T;
}

function moveToTrash(kind: TrashItem['kind'], title: string, context: string, data: unknown) {
  const id = uid('t');
  db.trash.unshift({ id, kind, title, context, deleted_at: new Date().toISOString() });
  db.trashPayload.set(id, { kind, data });
}

/** 주가 조건 메모 감지 — 백엔드에선 정규식/코드로 처리 (LLM 미사용) */
function parsePriceCondition(text: string): Memo['price_conditions'] {
  const m = text.match(/(\d+(?:[.,]\d+)?)\s*(만\s*원|만원|원)\s*(밑|아래|미만|이하|위|이상|넘)/);
  if (!m) return [];
  const raw = Number(m[1].replace(',', ''));
  const price = m[2].includes('만') ? raw * 10_000 : raw;
  const direction = /위|이상|넘/.test(m[3]) ? 'above' : 'below';
  return [{ id: uid('pc'), direction, price, tracking: true, status: 'waiting', reached_at: null }];
}

function buildTimeline(memo: Memo): MemoTimeline {
  const seeded = seed.seededTimeline(memo.id);
  const versions = db.versions[memo.id] ?? [{ version: 1, title: memo.title, body: memo.body, saved_at: memo.created_at }];
  let entries: TimelineEntry[];
  if (seeded) entries = seeded;
  else {
    entries = db.aiUpdates
      .filter((u) => u.memo_id === memo.id)
      .map((u) => ({
        kind: 'update' as const,
        at: u.published_at,
        update: u,
        memo_snapshot: versions.find((v) => v.version === u.memo_version) ?? versions[versions.length - 1],
      }));
    versions.slice(1).forEach((v) => entries.push({ kind: 'memo_edit', at: v.saved_at, version: v }));
    entries.push({ kind: 'memo_created', at: versions[0].saved_at, version: versions[0] });
    if (memo.ai_linked_at) entries.push({ kind: 'ai_linked', at: memo.ai_linked_at });
    entries.sort((a, b) => +new Date(b.at) - +new Date(a.at));
  }
  return { memo_id: memo.id, entries, price_condition_count: memo.price_conditions.length };
}

const memosOf = () => db.board.filter((b): b is Memo => b.kind === 'memo');
const currentPrice = (code: string) => candlesOf(code).at(-1)!.close;

export const mockApi: Api = {
  // ─── 인증
  loginEmail: async () => wait({ access_token: 'mock-token', token_type: 'bearer' as const, user: db.user }),
  signupEmail: async (name) => {
    db.user.name = name || db.user.name;
    return wait({ access_token: 'mock-token', token_type: 'bearer' as const, user: db.user });
  },
  me: async () => wait(db.user),
  updateMe: async (patch) => {
    Object.assign(db.user, patch);
    return wait(db.user);
  },
  logout: async () => wait(undefined),

  // ─── 종목
  listMyStocks: async () => {
    recountUnread();
    return wait(db.stocks);
  },
  searchStocks: async (q) => {
    const k = q.trim().toLowerCase();
    if (!k) return wait([]);
    return wait(seed.stockMaster.filter((s) => s.name.toLowerCase().includes(k) || s.code.includes(k)).slice(0, 8));
  },
  addStock: async (code, status) => {
    const master = seed.stockMaster.find((s) => s.code === code);
    if (!master) throw new Error('종목을 찾을 수 없어요');
    const existing = db.stocks.find((s) => s.code === code);
    if (existing) {
      existing.status = status;
      return wait(existing);
    }
    const created: MyStock = { ...master, status, tags: [], unread_updates: 0, added_at: new Date().toISOString() };
    db.stocks.push(created);
    return wait(created);
  },
  updateStock: async (code, patch) => {
    const s = db.stocks.find((x) => x.code === code);
    if (!s) throw new Error('종목을 찾을 수 없어요');
    Object.assign(s, patch);
    return wait(s);
  },
  removeStock: async (code) => {
    const s = db.stocks.find((x) => x.code === code);
    if (s) {
      db.stocks = db.stocks.filter((x) => x.code !== code);
      moveToTrash('stock', s.name, '종목', s);
    }
    return wait(undefined);
  },
  getQuote: async (code) => {
    const c = candlesOf(code);
    const last = c[c.length - 1];
    const prev = c[c.length - 2];
    const asOf = new Date(last.date + 'T15:30:00+09:00');
    return wait({
      code,
      price: last.close,
      change: last.close - prev.close,
      change_pct: Math.round(((last.close - prev.close) / prev.close) * 10000) / 100,
      as_of: asOf.toISOString(),
      spark: c.slice(-24).map((x) => x.close),
    });
  },
  getCandles: async (code, range) => {
    const n = { '1W': 5, '1M': 22, '3M': 64, '1Y': 250 }[range];
    return wait(candlesOf(code).slice(-n));
  },
  getProfile: async (code) => {
    const c = candlesOf(code);
    const last = c[c.length - 1];
    const prev = c[c.length - 2];
    const base = seed.profiles[code] ?? {
      code, name: stockName(code), market: 'KOSPI' as const, overview: '기업 개요를 준비 중이에요.',
      per: null, pbr: null, eps: null, bps: null, shares_outstanding: 100_000_000,
    };
    const year = c.slice(-250);
    const profile: StockProfile = {
      ...base,
      prev_close: prev.close,
      open: last.open,
      high: last.high,
      low: last.low,
      volume: last.volume,
      trading_value: last.volume * last.close,
      market_cap: last.close * base.shares_outstanding,
      week52_low: Math.min(...year.map((x) => x.low)),
      week52_high: Math.max(...year.map((x) => x.high)),
    };
    return wait(profile);
  },
  getFinancials: async (code) => wait(seed.financials[code] ?? seed.financials['000660']),

  // ─── 메모 보드
  listBoard: async (code) => {
    recountUnread();
    return wait(db.board.filter((b) => b.stock_code === code).sort((a, b) => a.position - b.position));
  },
  createMemo: async (code, input) => {
    const now = new Date().toISOString();
    const pos = Math.max(0, ...db.board.filter((b) => b.stock_code === code).map((b) => b.position)) + 1;
    const memo: Memo = {
      id: uid('m'), kind: 'memo', stock_code: code, position: pos, title: input.title, body: input.body,
      tags: input.tags, color: input.color, pinned: input.pinned ?? false, ai_linked: input.ai_linked,
      ai_linked_at: input.ai_linked ? now : null, price_conditions: parsePriceCondition(`${input.title} ${input.body}`),
      unread_updates: 0, created_at: now, updated_at: now,
    };
    db.board.push(memo);
    db.versions[memo.id] = [{ version: 1, title: memo.title, body: memo.body, saved_at: now }];
    return wait(memo);
  },
  createChecklist: async (code, input) => {
    const now = new Date().toISOString();
    const pos = Math.max(0, ...db.board.filter((b) => b.stock_code === code).map((b) => b.position)) + 1;
    const item: Checklist = {
      id: uid('c'), kind: 'checklist', stock_code: code, position: pos, title: input.title || '체크리스트',
      items: input.items.map((i) => ({ id: 'id' in i ? i.id : uid('ci'), text: i.text, done: i.done })),
      created_at: now, updated_at: now,
    };
    db.board.push(item);
    return wait(item);
  },
  createReference: async (code, input) => {
    const now = new Date().toISOString();
    const pos = Math.max(0, ...db.board.filter((b) => b.stock_code === code).map((b) => b.position)) + 1;
    const item: ReferenceBoard = {
      id: uid('r'), kind: 'reference', stock_code: code, position: pos, title: input.title || '참고 자료',
      links: input.links.map((l) => ({ ...l, id: 'id' in l ? l.id : uid('rl') })),
      created_at: now, updated_at: now,
    };
    db.board.push(item);
    return wait(item);
  },
  updateBoardItem: async (id, patch) => {
    const item = db.board.find((b) => b.id === id);
    if (!item) throw new Error('항목을 찾을 수 없어요');
    const now = new Date().toISOString();
    if (item.kind === 'memo' && ('title' in patch || 'body' in patch)) {
      const p = patch as Partial<Memo>;
      const changed = (p.title !== undefined && p.title !== item.title) || (p.body !== undefined && p.body !== item.body);
      if (changed) {
        const list = (db.versions[item.id] ??= [{ version: 1, title: item.title, body: item.body, saved_at: item.created_at }]);
        list.push({ version: list.length + 1, title: p.title ?? item.title, body: p.body ?? item.body, saved_at: now });
        item.price_conditions = parsePriceCondition(`${p.title ?? item.title} ${p.body ?? item.body}`).map((c) => {
          const old = item.price_conditions.find((o) => o.price === c.price && o.direction === c.direction);
          return old ?? c;
        });
      }
    }
    Object.assign(item, patch, { updated_at: now });
    return wait(item);
  },
  deleteBoardItem: async (id) => {
    const item = db.board.find((b) => b.id === id);
    if (item) {
      db.board = db.board.filter((b) => b.id !== id);
      const label = { memo: '메모', checklist: '체크리스트', reference: '참고자료' }[item.kind];
      moveToTrash(item.kind, item.title, `${stockName(item.stock_code)} / ${label}`, item);
    }
    return wait(undefined);
  },
  setAiLink: async (memoId, enabled) => {
    const m = memosOf().find((x) => x.id === memoId);
    if (!m) throw new Error('메모를 찾을 수 없어요');
    m.ai_linked = enabled;
    if (enabled && !m.ai_linked_at) m.ai_linked_at = new Date().toISOString();
    return wait(m);
  },
  getMemoTimeline: async (memoId) => {
    const m = memosOf().find((x) => x.id === memoId);
    if (!m) throw new Error('메모를 찾을 수 없어요');
    return wait(buildTimeline(m));
  },
  listStockAiUpdates: async (code) => {
    const linked = new Set(memosOf().filter((m) => m.ai_linked).map((m) => m.id));
    // 보드 패널: m4(시안 타임라인 전용) 과거 항목은 제외하고 최근 소식만
    const list = db.aiUpdates
      .filter((u) => u.stock_code === code && linked.has(u.memo_id) && !['a6', 'a7', 'a8', 'a9'].includes(u.id))
      .sort((a, b) => +new Date(b.published_at) - +new Date(a.published_at));
    return wait(list);
  },
  markAiUpdateRead: async (id) => {
    const u = db.aiUpdates.find((x) => x.id === id);
    if (u) u.read = true;
    recountUnread();
    return wait(undefined);
  },
  uploadFile: async (file) => wait({ url: file.uri, name: file.name }),

  // ─── 최신 업데이트
  listUpdates: async (params) => {
    let list = db.updates.filter((u) => db.stocks.some((s) => s.code === u.stock_code));
    if (params?.stock_code) list = list.filter((u) => u.stock_code === params.stock_code);
    list = list.sort((a, b) => +new Date(b.published_at) - +new Date(a.published_at));
    return wait(params?.limit ? list.slice(0, params.limit) : list);
  },

  // ─── 투자 기록
  listJournal: async () => wait([...db.journal].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))),
  createJournal: async (input) => {
    const now = new Date().toISOString();
    const entry: JournalEntry = { id: uid('j'), ...input, stock_name: input.stock_code ? stockName(input.stock_code) : null, created_at: now, updated_at: now };
    db.journal.unshift(entry);
    return wait(entry);
  },
  updateJournal: async (id, patch) => {
    const j = db.journal.find((x) => x.id === id);
    if (!j) throw new Error('기록을 찾을 수 없어요');
    Object.assign(j, patch, { updated_at: new Date().toISOString() });
    if (patch.stock_code !== undefined) j.stock_name = patch.stock_code ? stockName(patch.stock_code) : null;
    return wait(j);
  },
  deleteJournal: async (id) => {
    const j = db.journal.find((x) => x.id === id);
    if (j) {
      db.journal = db.journal.filter((x) => x.id !== id);
      moveToTrash('journal', j.title || '제목 없는 기록', '투자 기록', j);
    }
    return wait(undefined);
  },

  // ─── 홈
  getHomeLayout: async () => wait(db.layout),
  saveHomeLayout: async (layout) => {
    db.layout = layout;
    return wait(layout);
  },
  getMarketOverview: async () => wait(seed.marketOverview),
  listCalendar: async (month) => wait(db.calendar.filter((e) => e.date.startsWith(month))),
  createCalendarEvent: async (input) => {
    const e = { id: uid('e'), date: input.date, title: input.title, category: 'mine' as const, stock_code: null };
    db.calendar.push(e);
    return wait(e);
  },
  listNews: async () => wait(seed.news),
  listPinnedMemos: async () =>
    wait(
      memosOf()
        .filter((m) => m.pinned && db.stocks.some((s) => s.code === m.stock_code))
        .map((m): PinnedMemo => ({ ...m, stock_name: stockName(m.stock_code) })),
    ),
  listHomeChecklist: async () =>
    wait(
      db.board
        .filter((b): b is Checklist => b.kind === 'checklist' && db.stocks.some((s) => s.code === b.stock_code))
        .flatMap((c) => c.items.map((i) => ({ id: i.id, checklist_id: c.id, text: i.text, done: i.done, stock_code: c.stock_code, stock_name: stockName(c.stock_code) }))),
    ),
  setChecklistItem: async (checklistId, itemId, done) => {
    const c = db.board.find((b): b is Checklist => b.id === checklistId && b.kind === 'checklist');
    const it = c?.items.find((i) => i.id === itemId);
    if (it) it.done = done;
    return wait(undefined);
  },
  addChecklistItem: async (stockCode, text) => {
    let c = db.board.find((b): b is Checklist => b.kind === 'checklist' && b.stock_code === stockCode);
    if (!c) {
      const created = await mockApi.createChecklist(stockCode, { title: '체크리스트', items: [] });
      c = db.board.find((b): b is Checklist => b.id === created.id && b.kind === 'checklist')!;
    }
    const item = { id: uid('ci'), text, done: false };
    c.items.push(item);
    return wait({ ...item, checklist_id: c.id, stock_code: stockCode, stock_name: stockName(stockCode) });
  },
  listPriceConditions: async () =>
    wait(
      memosOf()
        .filter((m) => db.stocks.some((s) => s.code === m.stock_code))
        .flatMap((m) =>
          m.price_conditions.map((c) => ({
            memo_id: m.id, memo_title: m.title, stock_code: m.stock_code, stock_name: stockName(m.stock_code),
            condition: c, current_price: currentPrice(m.stock_code),
          })),
        ),
    ),
  setPriceConditionTracking: async (memoId, conditionId, tracking) => {
    const m = memosOf().find((x) => x.id === memoId);
    const c = m?.price_conditions.find((x) => x.id === conditionId);
    if (c) {
      c.tracking = tracking;
      if (!tracking) c.status = 'paused';
      else c.status = c.reached_at ? 'reached' : 'waiting';
    }
    return wait(undefined);
  },
  listMemoUpdateSummary: async () => {
    const out = db.stocks
      .map((s) => {
        const memos = memosOf()
          .filter((m) => m.stock_code === s.code && m.ai_linked)
          .map((m) => ({
            memo_id: m.id, title: m.title, color: m.color,
            updates: db.aiUpdates.filter((u) => u.memo_id === m.id && !u.read) as AiUpdate[],
          }))
          .filter((m) => m.updates.length > 0);
        return { stock_code: s.code, stock_name: s.name, new_count: memos.reduce((n, m) => n + m.updates.length, 0), memos };
      })
      .filter((s) => s.new_count > 0);
    return wait(out);
  },
  listMemoBacktests: async () =>
    wait(
      memosOf()
        .filter((m) => db.stocks.some((s) => s.code === m.stock_code))
        .flatMap((m) =>
          m.price_conditions.map((c) => {
            const price = currentPrice(m.stock_code);
            const c2 = candlesOf(m.stock_code);
            const hit = c.reached_at ? c2.find((x) => x.date >= ymd(new Date(c.reached_at!))) : undefined;
            const triggerPrice = hit ? (c.direction === 'below' ? Math.min(hit.close, c.price) : Math.max(hit.close, c.price)) : null;
            return {
              memo_id: m.id, memo_title: m.title, stock_code: m.stock_code, stock_name: stockName(m.stock_code), condition: c,
              triggered_at: c.reached_at, trigger_price: triggerPrice, current_price: price,
              return_pct: triggerPrice ? Math.round(((price - triggerPrice) / triggerPrice) * 1000) / 10 : null,
            };
          }),
        ),
    ),
  listCompareMemos: async () => wait(seed.compareCards().filter((c) => memosOf().some((m) => m.id === c.memo_id))),
  listConcludeCandidates: async () => {
    const m6 = memosOf().find((m) => m.id === 'm6');
    const m7 = memosOf().find((m) => m.id === 'm7');
    const list = [
      m6 && { memo_id: m6.id, memo_title: m6.title, memo_body: m6.body, stock_code: m6.stock_code, stock_name: stockName(m6.stock_code), color: m6.color, premise_event: '배당 관련 공시가 도착했어요', occurred_at: seed.aiUpdates.find((u) => u.id === 'a10')!.published_at },
      m7 && { memo_id: m7.id, memo_title: m7.title, memo_body: m7.body, stock_code: m7.stock_code, stock_name: stockName(m7.stock_code), color: m7.color, premise_event: '설정한 7만원 조건에 도달했어요', occurred_at: '2026-10-16T15:30:00+09:00' },
    ].filter(Boolean);
    return wait(list as NonNullable<(typeof list)[number]>[]);
  },
  concludeMemo: async (memoId, conclusion) => {
    const m = memosOf().find((x) => x.id === memoId);
    if (!m) throw new Error('메모를 찾을 수 없어요');
    const entry = await mockApi.createJournal({
      title: `결론 · ${m.title}`,
      stock_code: m.stock_code,
      blocks: [
        { id: uid('b'), type: 'heading', text: '처음 메모' },
        { id: uid('b'), type: 'paragraph', text: `${m.title}\n${m.body}` },
        { id: uid('b'), type: 'heading', text: '내 결론' },
        { id: uid('b'), type: 'paragraph', text: conclusion },
      ],
    });
    db.board = db.board.filter((b) => b.id !== memoId);
    return entry;
  },

  // ─── 휴지통 · 설정
  listTrash: async () => wait(db.trash),
  restoreTrash: async (id) => {
    const t = db.trash.find((x) => x.id === id);
    const payload = db.trashPayload.get(id);
    if (t && payload) {
      if (t.kind === 'journal') db.journal.unshift(payload.data as JournalEntry);
      else if (t.kind === 'stock') db.stocks.push(payload.data as MyStock);
      else db.board.push(payload.data as BoardItem);
    }
    db.trash = db.trash.filter((x) => x.id !== id);
    db.trashPayload.delete(id);
    return wait(undefined);
  },
  purgeTrash: async (id) => {
    db.trash = db.trash.filter((x) => x.id !== id);
    db.trashPayload.delete(id);
    return wait(undefined);
  },
  getSettings: async () => wait(db.settings),
  updateSettings: async (patch) => {
    db.settings = deepMerge<Settings>(db.settings, patch);
    return wait(db.settings);
  },
  disconnectMcpApp: async (appId) => {
    db.settings.mcp.apps = db.settings.mcp.apps.filter((a) => a.id !== appId);
    return wait(db.settings);
  },
  getAiStats: async () => {
    const linked = memosOf().filter((m) => m.ai_linked);
    return wait({
      linked_memos: linked.length,
      updates_this_month: db.aiUpdates.filter((u) => new Date(u.published_at).getMonth() === new Date().getMonth()).length,
      linked_stocks: new Set(linked.map((m) => m.stock_code)).size,
    });
  },
  getDataStats: async () => wait({ memos: memosOf().length, journals: db.journal.length, stocks: db.stocks.length }),
  exportData: async (format) => wait({ url: `data:text/${format === 'csv' ? 'csv' : 'json'};charset=utf-8,` }),
  deleteAllData: async () => {
    db.board = [];
    db.journal = [];
    db.stocks = [];
    return wait(undefined);
  },
  sendFeedback: async () => wait(undefined, 400),
};
