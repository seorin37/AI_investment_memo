import type { BoardChecklistItem } from '@/features/board/MemoBoard.types';

/**
 * 체크리스트 한 페이지. 새로 만들 때(mode 'new')는 상단 바가 취소 · 'SK하이닉스 · 새 체크리스트' · 완료,
 * 저장된 것을 열 때(mode 'edit')는 ‹ 메모 보드 · [고정] (상단 바는 TopBar 로 따로, 고정 버튼은 TopBar actions 'pill').
 */
export interface ChecklistDetailProps {
  mode: 'new' | 'edit';
  title: string;
  /** '2026년 10월 8일 작성' */
  date_full: string;
  items: BoardChecklistItem[];
  pinned: boolean;
  onChangeTitle: (title: string) => void;
  onToggleItem: (item_id: string) => void;
  onDeleteItem: (item_id: string) => void;
  onAddItem: (text: string) => void;
  /** 마지막 항목을 체크해 모두 끝냈을 때 (호스트가 축하 효과·진동을 붙일 자리) */
  onAllDone?: () => void;
}
