import { useQuery } from '@tanstack/react-query';
import { api } from '@/api';
import { env } from '@/config/env';
import { qk } from '@/hooks/queries';
import type { BoardItem, Memo } from '@/types/models';
import { mockBoardMemos } from '@/ui/screens/board/MemoBoard.mock';

export type LabMemo = { id: string; title: string };

/** 그 종목의 메모 1개: 체크리스트 빼고 · AI 연결된 메모 먼저 · 그다음 최근 수정(작성)순 */
function pick(items: BoardItem[], code: string): LabMemo | null {
  const memos = items.filter((b): b is Memo => b.kind === 'memo' && b.stock_code === code);
  memos.sort((a, b) => Number(b.ai_linked) - Number(a.ai_linked) || b.updated_at.localeCompare(a.updated_at));
  const m = memos[0];
  return m ? { id: m.id, title: m.title } : null;
}

/**
 * 웹 실험 결과의 '내 메모와 연결' 칸 (엑셀 웹 #11 · 원본 studio.tsx LabResult 626줄)
 * 실제 모드: 종목 보드와 같은 GET /stocks/{code}/board (같은 query key 라 보드로 넘어가면 다시 받지 않음) · 실험 결과 화면일 때만 읽음
 * mock 모드: 종목 보드 화면과 같은 예시 메모 (mockBoardMemos)
 */
export function useLabMemo(code: string | undefined, on: boolean): LabMemo | null {
  const real = !env.useMock;
  const board = useQuery({ queryKey: qk.board(code ?? ''), queryFn: () => api.listBoard(code ?? ''), enabled: real && on && !!code });
  if (!code) return null;
  if (!real) return pick(mockBoardMemos, code);
  return board.data ? pick(board.data, code) : null;
}
