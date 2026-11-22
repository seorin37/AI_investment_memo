import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/api';
import { env } from '@/config/env';
import { usePurgeTrash, useRestoreTrash, useTrash } from '@/hooks/queries';
import type { TrashItem as ApiTrashItem } from '@/types/models';
import { useMyMock } from '@/store/myMock';
import { ago } from '@/ui/screens/updates/updatesFormat';
import type { TrashItem } from './My.mock';

/**
 * 휴지통 (웹 설정 창 · 앱 MY › 휴지통) 데이터 (2026-11-22).
 * - 실제 모드: GET /trash · 복원 POST /trash/{id}/restore · 영구 삭제 DELETE /trash/{id} (비우기 = 하나씩)
 *   복원 되돌리기 = 다시 지우기 (메모 DELETE board-items · 투자 기록 DELETE journal · 종목 DELETE stocks)
 * - USE_MOCK=true 면 지금처럼 store/myMock (영구 삭제는 안내만)
 */
const KIND: Record<ApiTrashItem['kind'], TrashItem['kind']> = { memo: '메모', checklist: '메모', reference: '메모', journal: '투자 기록', stock: '종목' };

export function toTrashItem(t: ApiTrashItem, now = new Date().toISOString()): TrashItem {
  const stock = /^stock-(\w{6})$/.exec(t.id)?.[1];
  return { id: t.id, kind: KIND[t.kind] ?? '메모', title: t.title, sub: t.context.replace(' / ', ' · '), ago: ago(t.deleted_at, now), stock_code: stock };
}

export function useTrashData(onPurgeMock: () => void) {
  const real = !env.useMock;
  const qc = useQueryClient();
  const trash = useTrash(real);
  const restore = useRestoreTrash();
  const purge = usePurgeTrash();
  const mockItems = useMyMock((s) => s.trash);
  const mockRestore = useMyMock((s) => s.restore);
  const mockUndo = useMyMock((s) => s.undoRestore);

  if (!real) return { items: mockItems, restore: (t: TrashItem) => mockRestore(t.id), undo: mockUndo, purge: (_t: TrashItem | null) => onPurgeMock() };

  const items = (trash.data ?? []).map((t) => toTrashItem(t));
  return {
    items,
    restore: (t: TrashItem) => {
      restore.mutate(t.id);
      return t;
    },
    undo: (t: TrashItem) => {
      const [kind, key] = [t.id.slice(0, t.id.indexOf('-')), t.id.slice(t.id.indexOf('-') + 1)];
      const again = kind === 'journal' ? api.deleteJournal(key) : kind === 'stock' ? api.removeStock(key) : api.deleteBoardItem(key);
      void again.finally(() => qc.invalidateQueries());
    },
    purge: (t: TrashItem | null) => (t ? [t] : items).forEach((x) => purge.mutate(x.id)),
  };
}
