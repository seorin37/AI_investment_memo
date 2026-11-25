import { useQueryClient } from '@tanstack/react-query';
import { create } from 'zustand';
import { api } from '@/api';
import { env } from '@/config/env';
import { qk } from '@/hooks/queries';
import { registerUserReset } from '@/lib/sessionReset';
import { useMockBoard } from '@/store/mockBoard';
import { useUI } from '@/store/ui';
import { mockBase, mockKey } from '@/ui/screens/board/useBoardCards';
import { useMarkWatchAdded } from './reportView';

/**
 * 앱 '메모에 추가' (주간보고서 · 투자 실험실 '앞으로 지켜볼 것'): 화면을 옮기지 않고 그 종목의 일반 메모로 바로 저장.
 * 저장은 웹 새 메모 창과 같은 API (POST /stocks/{code}/memos · 서버 항목이면 '추가됨' 기록), mock 모드는 앱 보드와 같은 store/mockBoard.
 * AI 연결은 켜지 않음 (웹은 연결 창에서 확인하고 켬 — 메모에서 켤 수 있음).
 */
interface AddedState {
  added: Record<string, 'saving' | 'added'>;
  reset(): void;
}
const useAdded = create<AddedState>((set) => ({ added: {}, reset: () => set({ added: {} }) }));
registerUserReset('studioAddedMemos', () => useAdded.getState().reset());

export function useAddMemo() {
  const qc = useQueryClient();
  const markWatch = useMarkWatchAdded();
  const added = useAdded((s) => s.added);
  const idOf = (itemId: string | undefined, key: string) => `${itemId ?? ''}|${key}`;
  const put = (id: string, v?: 'saving' | 'added') => useAdded.setState((s) => {
    const next = { ...s.added };
    if (v) next[id] = v;
    else delete next[id];
    return { added: next };
  });
  return {
    isAdded: (itemId: string | undefined, key: string) => added[idOf(itemId, key)] === 'added',
    /** server: 서버에 저장된 항목이면 '추가됨'도 서버에 남김 */
    add: (p: { code: string; title: string; body: string; itemId?: string; key: string; server?: boolean }) => {
      const id = idOf(p.itemId, p.key);
      if (useAdded.getState().added[id]) return;
      const toast = useUI.getState().showToast;
      if (env.useMock) {
        useMockBoard.getState().addMemo(mockKey(p.code), mockBase(p.code), { title: p.title, body: p.body, color: 'yellow' });
        put(id, 'added');
        return toast('메모를 저장했어요');
      }
      put(id, 'saving');
      void api.createMemo(p.code, { title: p.title, body: p.body, color: 'yellow', tags: [], ai_linked: false }).then(
        (m) => {
          put(id, 'added');
          void qc.invalidateQueries({ queryKey: qk.board(p.code) });
          if (p.server) markWatch(p.itemId, p.key, m.id);
          toast('메모를 저장했어요');
        },
        () => {
          put(id);
          toast('메모를 저장하지 못했어요 · 잠시 뒤 다시 해 주세요');
        },
      );
    },
  };
}
