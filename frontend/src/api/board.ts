import type { BoardItem, Checklist, Memo, ReferenceBoard } from '@/types/models';
import type { BoardItemPatch, ChecklistInput, MemoInput, ReferenceInput } from './types';

type Query = Record<string, string | number | boolean | undefined | null>;

export interface BoardHttp {
  get<T>(path: string, query?: Query): Promise<T>;
  post<T>(path: string, body?: unknown): Promise<T>;
  put<T>(path: string, body?: unknown): Promise<T>;
  patch<T>(path: string, body?: unknown): Promise<T>;
  del<T = void>(path: string): Promise<T>;
}

type RawBoardItem = Record<string, unknown>;

const text = (value: unknown) => (value == null ? '' : String(value));
const number = (value: unknown) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};
const strings = (value: unknown) => (Array.isArray(value) ? value.map(String) : []);

function common(row: RawBoardItem) {
  return {
    id: text(row.id),
    stock_code: text(row.stock_code).trim(),
    title: text(row.title),
    position: number(row.position),
    created_at: text(row.created_at),
    updated_at: text(row.updated_at),
  };
}

export function normalizeBoardItem(row: RawBoardItem): BoardItem {
  if (row.kind === 'memo') {
    const color = ['yellow', 'blue', 'pink', 'green', 'purple'].includes(text(row.color))
      ? (text(row.color) as Memo['color'])
      : 'yellow';
    return {
      ...common(row),
      kind: 'memo',
      body: text(row.body),
      tags: strings(row.tags),
      color,
      pinned: Boolean(row.pinned),
      ai_linked: Boolean(row.ai_linked),
      ai_linked_at: row.ai_linked_at == null ? null : text(row.ai_linked_at),
      price_conditions: Array.isArray(row.price_conditions) ? (row.price_conditions as Memo['price_conditions']) : [],
      unread_updates: number(row.unread_updates),
    };
  }
  if (row.kind === 'checklist') {
    return {
      ...common(row),
      kind: 'checklist',
      items: Array.isArray(row.items)
        ? row.items.map((item) => {
            const value = item as Record<string, unknown>;
            return { id: text(value.id), text: text(value.text), done: Boolean(value.done) };
          })
        : [],
    } satisfies Checklist;
  }
  if (row.kind === 'reference') {
    return {
      ...common(row),
      kind: 'reference',
      links: Array.isArray(row.links)
        ? row.links.map((link) => {
            const value = link as Record<string, unknown>;
            const refType = ['ir', 'news', 'report', 'disclosure', 'etc'].includes(text(value.ref_type))
              ? (text(value.ref_type) as ReferenceBoard['links'][number]['ref_type'])
              : 'etc';
            return {
              id: text(value.id),
              title: text(value.title),
              url: text(value.url),
              ref_type: refType,
              source: value.source === 'file' ? 'file' : 'link',
            };
          })
        : [],
    } satisfies ReferenceBoard;
  }
  throw new Error(`지원하지 않는 보드 유형입니다: ${text(row.kind) || 'unknown'}`);
}

function rejectUnsupportedPosition(patch: BoardItemPatch) {
  if ('position' in patch && patch.position !== undefined) {
    throw new Error('실제 메모 보드는 순서 변경 저장을 아직 지원하지 않습니다.');
  }
}

export function createRealBoardApi(http: BoardHttp) {
  return {
    async listBoard(code: string): Promise<BoardItem[]> {
      const rows = await http.get<RawBoardItem[]>(`/stocks/${code}/board`);
      return rows.map(normalizeBoardItem);
    },
    async getBoardItem(id: string): Promise<BoardItem> {
      return normalizeBoardItem(await http.get<RawBoardItem>(`/board-items/${id}`));
    },
    async createMemo(code: string, input: MemoInput): Promise<Memo> {
      return normalizeBoardItem(await http.post<RawBoardItem>(`/stocks/${code}/memos`, input)) as Memo;
    },
    async createChecklist(code: string, input: ChecklistInput): Promise<Checklist> {
      return normalizeBoardItem(await http.post<RawBoardItem>(`/stocks/${code}/checklists`, input)) as Checklist;
    },
    async createReference(code: string, input: ReferenceInput): Promise<ReferenceBoard> {
      return normalizeBoardItem(await http.post<RawBoardItem>(`/stocks/${code}/references`, input)) as ReferenceBoard;
    },
    async updateBoardItem(id: string, patch: BoardItemPatch): Promise<BoardItem> {
      rejectUnsupportedPosition(patch);
      return normalizeBoardItem(await http.patch<RawBoardItem>(`/board-items/${id}`, patch));
    },
    deleteBoardItem: (id: string) => http.del<void>(`/board-items/${id}`),
    async setAiLink(memoId: string, enabled: boolean): Promise<Memo> {
      return normalizeBoardItem(
        await http.put<RawBoardItem>(`/memos/${memoId}/ai-link`, { enabled }),
      ) as Memo;
    },
    async setBoardChecklistItem(checklistId: string, itemId: string, done: boolean): Promise<void> {
      await http.patch<RawBoardItem>(`/checklists/${checklistId}/items/${itemId}`, { done });
    },
  };
}
