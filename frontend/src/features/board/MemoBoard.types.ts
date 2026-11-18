import type { MemoColor } from '@/types/models';
import type { StockSummary, StockTab } from '@/components/mobile/StockSummaryCard';

/** 보드의 메모 카드 1장 */
export interface BoardMemo {
  kind: 'memo';
  id: string;
  title: string;
  body: string;
  color: MemoColor;
  pinned: boolean;
  ai_linked: boolean;
  /** 읽지 않은 AI 업데이트 수 (빨간 배지) */
  unread_updates: number;
  created_at: string; // ISO
  updated_at: string; // ISO
}

export interface BoardChecklistItem {
  id: string;
  text: string;
  done: boolean;
}

/** 보드의 체크리스트 카드 1장 (AI 연결 없음) */
export interface BoardChecklist {
  kind: 'checklist';
  id: string;
  title: string;
  items: BoardChecklistItem[];
  pinned: boolean;
  created_at: string;
  updated_at: string;
}

export type BoardEntry = BoardMemo | BoardChecklist;
export type BoardFilter = 'all' | 'ai' | 'new';
export type BoardViewMode = 'grid' | 'list';
export type BoardCreateKind = 'memo' | 'checklist';

export interface MemoBoardProps {
  /** 위쪽 종목 요약 카드 */
  stock: StockSummary;
  /** 보드 항목 (메모 + 체크리스트). 순서는 화면이 정함: 고정 먼저 → 최근에 쓰거나 고친 순 */
  items: BoardEntry[];
  /** 처음 불러오는 중이면 회색 뼈대 카드 */
  loading?: boolean;
  /** 메모가 하나도 없을 때 보여 줄 예시 문장 칩 */
  examples: string[];
  onChangeTab: (tab: StockTab) => void;
  /** 메모 카드를 누름. 새 소식이 있고 AI 연결된 메모는 'ai' 탭으로 */
  onOpenMemo: (id: string, tab: 'memo' | 'ai') => void;
  onOpenChecklist: (id: string) => void;
  /** 2열 보드 카드 안의 항목 줄을 눌러 바로 체크 */
  onToggleChecklistItem: (checklist_id: string, item_id: string) => void;
  /** + 버튼(메모·체크리스트) 또는 빈 보드 예시 칩. first_line 은 칩 문장 */
  onCreate: (kind: BoardCreateKind, first_line?: string) => void;
  onPin: (ids: string[], pinned: boolean) => void;
  onDelete: (ids: string[]) => void;
  onCopy: (id: string) => void;
  onChangeColor: (ids: string[], color: MemoColor) => void;
  /** 메모 1개의 AI 연결 켜기/끄기 (켜기는 AiLinkConfirm 화면으로) */
  onToggleAi: (id: string) => void;
  /** 꾹 눌러 고르기 상태가 바뀔 때 (0 = 끝). 고르는 동안 하단 탭바를 숨기는 데 씀 */
  onSelectionChange?: (count: number) => void;
  /** 휴지통으로 보낸 뒤 알림의 [되돌리기] (없으면 버튼 없이 알림만) */
  onUndoDelete?: (ids: string[]) => void;
  /** 당겨서 새로고침 (Lucian #085) */
  refreshing?: boolean;
  onRefresh?: () => void;
  /** 방금 들어온 메모(예: 주간보고서 「메모에 추가」)를 1.4초 동안 테두리로 반짝 */
  flash_id?: string | null;
}
