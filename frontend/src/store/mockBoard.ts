import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { env } from '@/config/env';
import type { ChecklistItem, Memo } from '@/types/models';
import { addChecklist, addMemo, patchMemo, removeCards, restoreCards, setPinned, type BoardCards, type RemovedCard } from '@/ui/screens/board/boardCards';
import { mockBoardChecklist, mockBoardMemos, mockBoardOrder } from '@/ui/screens/board/MemoBoard.mock';

/**
 * mock 모드 메모 보드 (종목별 메모 · 체크리스트 · 순서). 실제 모드에서는 쓰지 않음(서버가 저장).
 * 서버처럼 새로고침 · 다시 로그인해도 남도록 기기에 저장 — 그래서 로그아웃 때 비우지 않음 (mock 사용자는 한 명).
 */
export const SEED_CARDS: BoardCards = { memos: mockBoardMemos, checklists: [mockBoardChecklist], order: mockBoardOrder };
const HOME_CODE = '000660';
/** 예시 '오늘' (MemoDetail.mock mockToday 와 같은 날) */
const TODAY = '2026-11-19T09:00:00+09:00';

let seq = 0;
const newId = (p: string) => `${p}${Date.now()}${(seq += 1)}`;

interface MockBoardState {
  boards: Record<string, BoardCards>;
  removed: Record<string, RemovedCard>;
  update: (key: string, base: BoardCards, f: (b: BoardCards) => BoardCards) => void;
  remove: (key: string, base: BoardCards, ids: string[]) => void;
  undoRemove: (key: string, base: BoardCards, ids: string[]) => void;
  addMemo: (key: string, base: BoardCards, input: Pick<Memo, 'title' | 'body' | 'color'>) => string;
  addChecklist: (key: string, base: BoardCards, input: { title: string; items: { text: string; done: boolean }[]; pinned?: boolean }) => string;
  /** 종목을 모르는 메모 화면용: 그 메모가 있는 보드에서 고침 */
  patchMemoAnywhere: (id: string, f: (m: Memo) => Memo) => void;
}

export const mockItems = (items: { id?: string; text: string; done: boolean }[]): ChecklistItem[] => items.map((i) => ({ id: i.id ?? newId('ci'), text: i.text, done: i.done }));

export const useMockBoard = create<MockBoardState>()(
  persist(
    (set, get) => ({
      boards: { [HOME_CODE]: SEED_CARDS },
      removed: {},
      update: (key, base, f) => set((s) => ({ boards: { ...s.boards, [key]: f(s.boards[key] ?? base) } })),
      remove: (key, base, ids) =>
        set((s) => {
          const { cards, removed } = removeCards(s.boards[key] ?? base, ids);
          return { boards: { ...s.boards, [key]: cards }, removed: { ...s.removed, ...Object.fromEntries(removed.map((r) => [r.id, r])) } };
        }),
      undoRemove: (key, base, ids) =>
        set((s) => {
          const back = ids.flatMap((id) => (s.removed[id] ? [s.removed[id]] : []));
          const left = Object.fromEntries(Object.entries(s.removed).filter(([id]) => !ids.includes(id)));
          return { boards: { ...s.boards, [key]: restoreCards(s.boards[key] ?? base, back) }, removed: left };
        }),
      addMemo: (key, base, input) => {
        const id = newId('n');
        get().update(key, base, (b) =>
          addMemo(b, { ...mockBoardMemos[0], ...input, id, stock_code: key, pinned: false, ai_linked: false, ai_linked_at: null, unread_updates: 0, created_at: TODAY, updated_at: TODAY }),
        );
        return id;
      },
      addChecklist: (key, base, input) => {
        const id = newId('cl');
        get().update(key, base, (b) =>
          addChecklist(b, { ...mockBoardChecklist, id, stock_code: key, title: input.title, items: mockItems(input.items), pinned: !!input.pinned, created_at: TODAY, updated_at: TODAY }),
        );
        return id;
      },
      patchMemoAnywhere: (id, f) =>
        set((s) => ({
          boards: Object.fromEntries(
            Object.entries(s.boards).map(([key, b]) => {
              const was = b.memos.find((m) => m.id === id);
              if (!was) return [key, b];
              const next = f(was);
              const patched = patchMemo(b, id, () => next);
              return [key, next.pinned === was.pinned ? patched : setPinned(patched, [id], next.pinned)];
            }),
          ),
        })),
    }),
    {
      name: 'memos.mock_board',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (s) => ({ boards: s.boards }),
      /* 실제 모드에서는 기기에 쓰지도 읽지도 않게 (쓰기는 set 할 때만 일어나는데 실제 모드는 set 을 부르지 않음) */
      skipHydration: !env.useMock,
    },
  ),
);

export const findMockMemo = (boards: Record<string, BoardCards>, id: string): Memo | undefined =>
  Object.values(boards).flatMap((b) => b.memos).find((m) => m.id === id);
