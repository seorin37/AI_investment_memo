import { useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/api';
import { env } from '@/config/env';
import { qk } from '@/hooks/queries';
import { useAuth } from '@/store/auth';
import { useMockBoard } from '@/store/mockBoard';
import { useUI } from '@/store/ui';
import { useWatchAdded } from '@/store/watchAdded';
import { mockBase, mockKey } from '@/ui/screens/board/useBoardCards';

const FROM = { report: '주간보고서 「앞으로 지켜볼 것」', lab: '투자 실험실 「추가로 확인할 것」' };

/**
 * [메모에 추가]: 그 종목 보드에 일반 메모(AI 연결 꺼짐)로. 실제 모드는 POST /stocks/{code}/memos, mock 은 store/mockBoard.
 * itemId = 만든 항목 id. 추가한 항목은 store/watchAdded 에 남겨 새로고침해도 '✓ 추가됨'
 */
export function useAddWatch(kind: 'report' | 'lab', itemId: string) {
  const qc = useQueryClient();
  const toast = useUI((s) => s.showToast);
  const userId = useAuth((s) => s.user?.id) ?? '';
  const added = useWatchAdded((s) => s.added);
  const mark = useWatchAdded((s) => s.mark);
  const busy = useRef(new Set<string>());
  const keyOf = (code: string, title: string) => [userId, kind, itemId, code, title].join('|');
  return {
    isAdded: (code: string, title: string) => !!added[keyOf(code, title)],
    add: (stock: { stock_code: string; name: string }, title: string, why: string) => {
      const code = stock.stock_code;
      const key = keyOf(code, title);
      if (busy.current.has(key) || useWatchAdded.getState().added[key]) return;
      const body = `${FROM[kind]}에서 추가했어요\n근거 · ${why}`;
      const ok = () => {
        mark(key, true);
        toast(`${stock.name} 메모 보드에 추가했어요`);
      };
      if (env.useMock) {
        useMockBoard.getState().addMemo(mockKey(code), mockBase(code), { title, body, color: 'yellow' });
        return ok();
      }
      busy.current.add(key);
      api
        .createMemo(code, { title, body, color: 'yellow', tags: [], ai_linked: false })
        .then(
          () => {
            void qc.invalidateQueries({ queryKey: qk.board(code) });
            void qc.invalidateQueries({ queryKey: qk.stocks });
            ok();
          },
          () => toast('메모에 추가하지 못했어요 · 잠시 뒤 다시 해 주세요'),
        )
        .finally(() => busy.current.delete(key));
    },
  };
}
