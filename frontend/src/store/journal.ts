import { create, type StateCreator } from 'zustand';
import { api } from '@/api';
import { env } from '@/config/env';
import { useAuth } from '@/store/auth';
import { useUI } from '@/store/ui';
import { mockJournal, mockJournalNow } from '@/ui/screens/journal/Journal.mock';
import type { JBlock, JournalEntry } from '@/ui/screens/journal/Journal.types';
import { byEdited, fromServer, journalDates, toServer } from '@/ui/screens/journal/journalApi';
import { isEmptyEntry, titleOf } from '@/ui/screens/journal/journalParts';

/** 기록 화면에서 목록으로 돌아올 때 목록이 보여 줄 것 (저장 알림 · 반짝임 · 휴지통 + 되돌리기) */
export type JournalFlashIn = { kind: 'saved'; id: string; isNew: boolean } | { kind: 'empty' } | { kind: 'trash'; id: string };
export type JournalFlash = JournalFlashIn & { key: number };

interface JournalState {
  entries: JournalEntry[];
  flash: JournalFlash | null;
  /** 서버 목록을 받았는지 (mock 은 처음부터 true) */
  loaded: boolean;
  /** 서버에서 목록 받기. 같은 계정으로 이미 받았으면 다시 안 받음 (force 면 받음) */
  load(force?: boolean): Promise<void>;
  /** __DEV__ 캡처용: 빈 목록으로 시작 */
  reset(empty: boolean): void;
  pin(ids: string[], on: boolean): void;
  trash(ids: string[]): void;
  restore(list: JournalEntry[]): void;
  /** 앱 기록 화면에서 나갈 때 (원본 saveCur): 새 기록은 맨 위에, 고친 기록은 '오늘'로 맨 위로 */
  saveApp(id: string | null, blocks: JBlock[]): { id: string; isNew: boolean } | null;
  /** 웹: 새 기록을 바로 맨 위에 만들고 고름 (원본 addJournal) */
  addWeb(): string;
  /** 웹: 쓰는 대로 바로 반영 (원본 updateJournal · 자리는 그대로) */
  updateWeb(id: string, p: Partial<JournalEntry>): void;
  /** 웹: 비어 있는 새 기록은 다른 기록으로 옮기면 지움 (원본 dropEmptyJournal) */
  dropEmpty(id: string): void;
  setFlash(f: JournalFlashIn | null): void;
}

let seq = 100;
const nid = () => `j${++seq}`;
const flashOf = (f: JournalFlashIn | null): JournalFlash | null => (f ? { ...f, key: ++seq } : null);

/* ───────────────────────── mock (USE_MOCK=true) — 앱을 켜 둔 동안만 · 예전 동작 그대로 ───────────────────────── */

const mockStore: StateCreator<JournalState> = (set, get) => ({
  entries: mockJournal,
  flash: null,
  loaded: true,
  load: async () => {},
  reset: (empty) => set({ entries: empty ? [] : mockJournal }),
  pin: (ids, on) => set((s) => ({ entries: s.entries.map((j) => (ids.includes(j.id) ? { ...j, pinned: on } : j)) })),
  trash: (ids) => set((s) => ({ entries: s.entries.filter((j) => !ids.includes(j.id)) })),
  restore: (list) => set({ entries: list }),
  saveApp: (id, blocks) => {
    const now = mockJournalNow;
    if (!id) {
      if (isEmptyEntry(blocks)) return null;
      const n: JournalEntry = { id: nid(), title: titleOf(blocks), date: now.date, web_date: now.web_date, full: now.full, group: now.group, pinned: false, blocks };
      set((s) => ({ entries: [n, ...s.entries] }));
      return { id: n.id, isNew: true };
    }
    const cur = get().entries.find((j) => j.id === id);
    if (!cur || JSON.stringify(cur.blocks) === JSON.stringify(blocks)) return null;
    const n: JournalEntry = { ...cur, blocks, html: undefined, title: titleOf(blocks), date: now.date, web_date: now.web_date, full: now.full, group: now.group };
    set((s) => ({ entries: [n, ...s.entries.filter((j) => j.id !== id)] }));
    return { id, isNew: false };
  },
  addWeb: () => {
    const now = mockJournalNow;
    const n: JournalEntry = { id: nid(), title: '', date: now.date, web_date: now.web_date, full: now.full, group: now.group, pinned: false, blocks: [{ s: 'title', text: '' }] };
    set((s) => ({ entries: [n, ...s.entries] }));
    return n.id;
  },
  updateWeb: (id, p) => set((s) => ({ entries: s.entries.map((j) => (j.id === id ? { ...j, ...p, ...(p.blocks ? { title: titleOf(p.blocks) } : null) } : j)) })),
  dropEmpty: (id) => set((s) => ({ entries: s.entries.filter((j) => !(j.id === id && isEmptyEntry(j.blocks))) })),
  setFlash: (f) => set({ flash: flashOf(f) }),
});

/* ───────────────────────── 실제 서버 (2026-11-22) ─────────────────────────
 * 화면은 그대로 두고 이 저장소만 서버와 맞춘다. 화면에는 먼저 반영하고 서버 저장은 뒤에서.
 * - 화면 id(로컬): 서버에서 받은 기록은 서버 id 그대로, 새로 만든 기록은 임시 id → 만들기가 끝나면 serverId 에 서버 id
 * - 같은 기록의 요청은 차례대로 (만들기 → 고치기 → 휴지통 → 되돌리기 순서가 꼬이지 않게)
 * - 웹은 쓰는 동안 SAVE_MS 쉬면 저장. 웹 '새 기록'은 글자가 생길 때 서버에 만든다 (빈 기록이 휴지통에 쌓이지 않게)
 * - 실패하면 안내 후 서버 목록으로 다시 맞춘다
 */

const SAVE_MS = 600;
const serverId = new Map<string, string>();
const chains = new Map<string, Promise<unknown>>();
const timers = new Map<string, ReturnType<typeof setTimeout>>();
let loadedFor: string | null = null;
let loading: Promise<void> | null = null;

/** 같은 기록 요청을 차례대로. 실패하면 안내하고 서버 목록으로 다시 맞춤 */
function queue(id: string, job: () => Promise<unknown>, fail: string) {
  const prev = chains.get(id) ?? Promise.resolve();
  const next = prev.then(job).catch((e: unknown) => {
    useUI.getState().showToast(e instanceof Error && e.message ? `${fail} · ${e.message}` : fail);
    void useJournal.getState().load(true);
  });
  chains.set(id, next);
  return next;
}

const sid = (id: string) => serverId.get(id) ?? null;
const nowDates = () => journalDates(new Date().toISOString());

const realStore: StateCreator<JournalState> = (set, get) => {
  /** 서버 응답(고친 시각)을 화면 기록에 반영 — 글은 화면 것을 그대로 둠 (쓰는 중일 수 있어서) */
  const touch = (id: string, updatedAt: string) =>
    set((s) => ({ entries: s.entries.map((j) => (j.id === id ? { ...j, updated_at: updatedAt, ...journalDates(updatedAt) } : j)) }));

  /** 지금 화면 내용으로 서버 저장 (없으면 만들기, 있으면 고치기). 빈 새 기록은 만들지 않음 */
  const push = (id: string) =>
    queue(id, async () => {
      const cur = get().entries.find((j) => j.id === id);
      if (!cur) return;
      const body = toServer(cur.blocks, cur.extra);
      const known = sid(id);
      if (!known) {
        if (isEmptyEntry(cur.blocks)) return;
        const made = await api.createJournal({ ...body, stock_code: null, pinned: cur.pinned });
        serverId.set(id, made.id);
        touch(id, made.updated_at);
        return;
      }
      const saved = await api.updateJournal(known, body);
      touch(id, saved.updated_at);
    }, '투자 기록을 저장하지 못했어요');

  const later = (id: string) => {
    clearTimeout(timers.get(id));
    timers.set(id, setTimeout(() => { timers.delete(id); void push(id); }, SAVE_MS));
  };
  /** 기다리는 저장이 있으면 바로 보냄 (휴지통 · 다른 기록으로 옮기기 전에) */
  const flush = (id: string) => {
    if (!timers.has(id)) return;
    clearTimeout(timers.get(id));
    timers.delete(id);
    void push(id);
  };

  return {
    entries: [],
    flash: null,
    loaded: false,
    load: async (force = false) => {
      const who = useAuth.getState().user?.id ?? null;
      if (!who) return;
      if (!force && loadedFor === who && get().loaded) return;
      if (loading && !force) return loading;
      loading = (async () => {
        try {
          const list = await api.listJournal();
          serverId.clear();
          list.forEach((e) => serverId.set(e.id, e.id));
          loadedFor = who;
          set({ entries: list.map((e) => fromServer(e)).sort(byEdited), loaded: true });
        } catch (e) {
          useUI.getState().showToast(e instanceof Error && e.message ? `투자 기록을 불러오지 못했어요 · ${e.message}` : '투자 기록을 불러오지 못했어요');
          set({ loaded: true });
        } finally {
          loading = null;
        }
      })();
      return loading;
    },
    reset: (empty) => {
      if (empty) set({ entries: [] });
    },
    pin: (ids, on) => {
      set((s) => ({ entries: s.entries.map((j) => (ids.includes(j.id) ? { ...j, pinned: on } : j)) }));
      ids.forEach((id) =>
        queue(id, async () => {
          const known = sid(id);
          if (known) await api.updateJournal(known, { pinned: on });     // 아직 서버에 없는 새 기록은 만들 때 같이 보냄
        }, '고정을 저장하지 못했어요'),
      );
    },
    trash: (ids) => {
      set((s) => ({ entries: s.entries.filter((j) => !ids.includes(j.id)) }));
      ids.forEach((id) => {
        flush(id);
        queue(id, async () => {
          const known = sid(id);
          if (known) await api.deleteJournal(known);
        }, '휴지통으로 옮기지 못했어요');
      });
    },
    restore: (list) => {
      const shown = new Set(get().entries.map((j) => j.id));
      set({ entries: list });
      list.filter((j) => !shown.has(j.id)).forEach((j) =>
        queue(j.id, async () => {
          const known = sid(j.id);
          if (known) await api.restoreTrash(`journal-${known}`);
        }, '되돌리지 못했어요'),
      );
    },
    saveApp: (id, blocks) => {
      const now = nowDates();
      const stamp = new Date().toISOString();
      if (!id) {
        if (isEmptyEntry(blocks)) return null;
        const n: JournalEntry = { id: nid(), title: titleOf(blocks), ...now, pinned: false, blocks, updated_at: stamp };
        set((s) => ({ entries: [n, ...s.entries] }));
        void push(n.id);
        return { id: n.id, isNew: true };
      }
      const cur = get().entries.find((j) => j.id === id);
      if (!cur || JSON.stringify(cur.blocks) === JSON.stringify(blocks)) return null;
      const n: JournalEntry = { ...cur, blocks, html: undefined, title: titleOf(blocks), ...now, updated_at: stamp };
      set((s) => ({ entries: [n, ...s.entries.filter((j) => j.id !== id)] }));
      void push(id);
      return { id, isNew: false };
    },
    addWeb: () => {
      const n: JournalEntry = { id: nid(), title: '', ...nowDates(), pinned: false, blocks: [{ s: 'title', text: '' }], updated_at: new Date().toISOString() };
      set((s) => ({ entries: [n, ...s.entries] }));
      return n.id;                                            // 서버에는 글자가 생길 때 만든다 (push 가 빈 기록은 건너뜀)
    },
    updateWeb: (id, p) => {
      set((s) => ({ entries: s.entries.map((j) => (j.id === id ? { ...j, ...p, ...(p.blocks ? { title: titleOf(p.blocks) } : null) } : j)) }));
      if (p.blocks) later(id);
    },
    dropEmpty: (id) => {
      const cur = get().entries.find((j) => j.id === id);
      if (!cur || !isEmptyEntry(cur.blocks)) {
        flush(id);
        return;
      }
      clearTimeout(timers.get(id));
      timers.delete(id);
      set((s) => ({ entries: s.entries.filter((j) => j.id !== id) }));
      /* 글을 다 지워 빈 기록이 됐는데 이미 서버에 있으면: 휴지통으로 보낸 뒤 바로 영구 삭제 (휴지통에 빈 기록이 남지 않게) */
      queue(id, async () => {
        const known = sid(id);
        if (!known) return;
        await api.deleteJournal(known);
        await api.purgeTrash(`journal-${known}`);
        serverId.delete(id);
      }, '빈 기록을 지우지 못했어요');
    },
    setFlash: (f) => set({ flash: flashOf(f) }),
  };
};

/**
 * 투자 기록 저장소 — 목록 · 기록 화면 · 웹이 같이 씀.
 * USE_MOCK=true 면 예전처럼 메모리(mock), 아니면 서버 (GET·POST /journal · PATCH·DELETE /journal/{id} · /trash 복원·영구 삭제).
 */
export const useJournal = create<JournalState>()(env.useMock ? mockStore : realStore);

/* 다른 계정으로 바뀌거나 로그아웃하면 목록을 비움. 로그인이 확인되면(새로고침 직후 포함) 그 계정 목록을 받음 */
useAuth.subscribe((s, prev) => {
  if (env.useMock || s.user?.id === prev.user?.id) return;
  serverId.clear();
  chains.clear();
  timers.forEach((t) => clearTimeout(t));
  timers.clear();
  loadedFor = null;
  useJournal.setState({ entries: [], loaded: false });
  if (s.user) void useJournal.getState().load();
});
