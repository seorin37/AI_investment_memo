import type { Checklist, Memo } from '@/types/models';

/**
 * 메모 보드 카드 묶음 (앱·웹 · mock·실제 공통 규칙, 순수 함수 — tests/board-cards.test.mjs)
 * order = 메모 id + 체크리스트 id 순서. 고정한 카드는 늘 앞(고정 구역), 나머지는 그 뒤(일반 구역).
 * 서버 규칙(be/app/board/service.py _place)과 같음: 새 카드 · 고정을 푼 카드는 일반 구역 맨 위, 고정한 카드는 고정 구역 맨 위.
 */
export interface BoardCards {
  memos: Memo[];
  checklists: Checklist[];
  order: string[];
}

export const EMPTY_CARDS: BoardCards = { memos: [], checklists: [], order: [] };

/** 휴지통으로 보낸 카드 (되돌리기용: 카드와 있던 자리) */
export interface RemovedCard {
  id: string;
  index: number;
  memo?: Memo;
  checklist?: Checklist;
}

export function pinnedIds(b: Pick<BoardCards, 'memos' | 'checklists'>): Set<string> {
  return new Set([...b.memos, ...b.checklists].filter((c) => c.pinned).map((c) => c.id));
}

/** 화면 순서: 고정 먼저 (구역 안은 order 순). order 에 없는 카드는 자기 구역 맨 위 */
export function arrange(b: BoardCards): string[] {
  const all = [...b.checklists, ...b.memos].map((c) => c.id);
  const has = new Set(all);
  const placed = b.order.filter((id) => has.has(id));
  const seen = new Set(placed);
  const list = [...all.filter((id) => !seen.has(id)), ...placed];
  const pins = pinnedIds(b);
  return [...list.filter((id) => pins.has(id)), ...list.filter((id) => !pins.has(id))];
}

/** 새 카드: 일반 구역 맨 위 (order 에 없으면 arrange 가 구역 맨 위로) */
export function addMemo(b: BoardCards, memo: Memo): BoardCards {
  const next = { ...b, memos: [...b.memos, memo] };
  return { ...next, order: arrange(next) };
}
export function addChecklist(b: BoardCards, checklist: Checklist): BoardCards {
  const next = { ...b, checklists: [...b.checklists, checklist] };
  return { ...next, order: arrange(next) };
}

export function patchMemo(b: BoardCards, id: string, f: (m: Memo) => Memo): BoardCards {
  return { ...b, memos: b.memos.map((m) => (m.id === id ? f(m) : m)) };
}
export function patchChecklist(b: BoardCards, id: string, f: (c: Checklist) => Checklist): BoardCards {
  return { ...b, checklists: b.checklists.map((c) => (c.id === id ? f(c) : c)) };
}

/** 고정 · 고정 해제 → 그 구역 맨 위로 */
export function setPinned(b: BoardCards, ids: string[], pinned: boolean): BoardCards {
  const on = new Set(ids);
  const rest = arrange(b).filter((id) => !on.has(id));
  const next: BoardCards = {
    memos: b.memos.map((m) => (on.has(m.id) ? { ...m, pinned } : m)),
    checklists: b.checklists.map((c) => (on.has(c.id) ? { ...c, pinned } : c)),
    order: [...ids, ...rest],
  };
  return { ...next, order: arrange(next) };
}

export function removeCards(b: BoardCards, ids: string[]): { cards: BoardCards; removed: RemovedCard[] } {
  const on = new Set(ids);
  const order = arrange(b);
  const removed = order.flatMap((id, index) =>
    on.has(id) ? [{ id, index, memo: b.memos.find((m) => m.id === id), checklist: b.checklists.find((c) => c.id === id) }] : [],
  );
  return {
    cards: { memos: b.memos.filter((m) => !on.has(m.id)), checklists: b.checklists.filter((c) => !on.has(c.id)), order: order.filter((id) => !on.has(id)) },
    removed,
  };
}

/** 되돌리기: 있던 자리로 */
export function restoreCards(b: BoardCards, removed: RemovedCard[]): BoardCards {
  const have = new Set([...b.memos, ...b.checklists].map((c) => c.id));
  const back = removed.filter((r) => !have.has(r.id)).sort((x, y) => x.index - y.index);
  const order = arrange(b);
  back.forEach((r) => order.splice(Math.min(r.index, order.length), 0, r.id));
  return {
    memos: [...b.memos, ...back.flatMap((r) => (r.memo ? [r.memo] : []))],
    checklists: [...b.checklists, ...back.flatMap((r) => (r.checklist ? [r.checklist] : []))],
    order,
  };
}
