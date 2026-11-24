import { useRef, useState } from 'react';
import { env } from '@/config/env';
import { SEED_CARDS, useMockBoard } from '@/store/mockBoard';
import { EMPTY_CARDS, patchChecklist, removeCards, restoreCards, setPinned, type BoardCards, type RemovedCard } from './boardCards';
import { mockEmptyStock } from './MemoBoard.mock';
import { useBoardData } from './useBoardData';

/** mock 보드의 처음 값 (KB금융 · 첫 메모 흐름은 빈 보드) */
export const mockBase = (code: string, first = false): BoardCards => (first || code === mockEmptyStock.stock_code ? EMPTY_CARDS : SEED_CARDS);
export const mockKey = (code: string, first = false) => (first ? `first:${code}` : code);

/**
 * 메모 보드 카드 상태 (앱·웹 같이 씀): 화면을 먼저 바꾸고, 실제 모드면 서버(useBoardData), mock 이면 기기 저장(store/mockBoard).
 */
export function useBoardCards(code: string, openId: string | null, first = false) {
  const real = !env.useMock;
  const bd = useBoardData(code, openId);
  const base = mockBase(code, first);
  const key = mockKey(code, first);
  const mock = useMockBoard((s) => s.boards[key]) ?? base;
  const [local, setLocal] = useState<BoardCards>(EMPTY_CARDS);
  /* 실제 모드: 서버 보드를 새로 받으면 화면 상태를 서버 값으로 */
  const [seen, setSeen] = useState(0);
  if (bd.data && bd.version !== seen) {
    setSeen(bd.version);
    setLocal(bd.data);
  }
  const cards = real ? local : mock;
  const removed = useRef<RemovedCard[]>([]);
  const update = (f: (b: BoardCards) => BoardCards) => (real ? setLocal(f) : useMockBoard.getState().update(key, base, f));
  const actions = {
    update,
    pin: (ids: string[], pinned: boolean) => {
      bd.ops.pin(ids, pinned);
      update((b) => setPinned(b, ids, pinned));
    },
    remove: (ids: string[]) => {
      if (!real) return useMockBoard.getState().remove(key, base, ids);
      bd.ops.remove(ids);
      const r = removeCards(cards, ids);
      removed.current = [...removed.current, ...r.removed];
      setLocal((b) => removeCards(b, ids).cards);
    },
    undoRemove: (ids: string[]) => {
      if (!real) return useMockBoard.getState().undoRemove(key, base, ids);
      bd.ops.undoRemove(ids);
      const back = removed.current.filter((r) => ids.includes(r.id));
      removed.current = removed.current.filter((r) => !ids.includes(r.id));
      setLocal((b) => restoreCards(b, back));
    },
    toggleItem: (id: string, itemId: string) => {
      const it = cards.checklists.find((c) => c.id === id)?.items.find((i) => i.id === itemId);
      if (it) bd.ops.checkItem(id, itemId, !it.done);
      update((b) => patchChecklist(b, id, (c) => ({ ...c, items: c.items.map((i) => (i.id === itemId ? { ...i, done: !i.done } : i)) })));
    },
    reorder: (order: string[]) => {
      bd.ops.reorder(order);
      update((b) => ({ ...b, order }));
    },
    /* mock 전용 새 카드 (실제 모드는 서버가 만든 카드를 update 로 넣음) */
    mockAddMemo: (input: Parameters<ReturnType<typeof useMockBoard.getState>['addMemo']>[2]) => useMockBoard.getState().addMemo(key, base, input),
    mockAddChecklist: (input: Parameters<ReturnType<typeof useMockBoard.getState>['addChecklist']>[2]) => useMockBoard.getState().addChecklist(key, base, input),
  };
  return { real, cards, bd, ...actions };
}
