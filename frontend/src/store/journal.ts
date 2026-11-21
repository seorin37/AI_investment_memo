import { create } from 'zustand';
import { mockJournal, mockJournalNow } from '@/ui/screens/journal/Journal.mock';
import type { JBlock, JournalEntry } from '@/ui/screens/journal/Journal.types';
import { isEmptyEntry, titleOf } from '@/ui/screens/journal/journalParts';

/** 기록 화면에서 목록으로 돌아올 때 목록이 보여 줄 것 (저장 알림 · 반짝임 · 휴지통 + 되돌리기) */
export type JournalFlashIn = { kind: 'saved'; id: string; isNew: boolean } | { kind: 'empty' } | { kind: 'trash'; id: string };
export type JournalFlash = JournalFlashIn & { key: number };

interface JournalState {
  entries: JournalEntry[];
  flash: JournalFlash | null;
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

/**
 * 투자 기록 mock 저장소 — 앱을 켜 둔 동안만 (서버·기기 저장 없음). 목록 · 기록 화면 · 웹이 같이 씀.
 * 연결 단계: 이 자리를 서버 API (목록 · 만들기 · 고치기 · 고정 · 휴지통 · 되돌리기)로 바꿈.
 */
export const useJournal = create<JournalState>((set, get) => ({
  entries: mockJournal,
  flash: null,
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
  setFlash: (f) => set({ flash: f ? { ...f, key: ++seq } : null }),
}));
