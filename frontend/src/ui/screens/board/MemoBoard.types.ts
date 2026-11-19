import type { Checklist, Memo, MemoColor } from '@/types/models';
import type { StockHeadProps } from '@/ui/shared/StockHead.types';

/** 보드 거르기 (원본: 전체 · AI 연결 · 새 소식) */
export type BoardFilter = 'all' | 'ai' | 'new';

/** 웹 보드 카드 순서의 키: 메모 id 또는 체크리스트 'cl' */
export type BoardKey = string;

/** 메모 보드 (웹·앱 같은 props) */
export interface MemoBoardProps {
  stock: StockHeadProps;
  /** 이 종목의 메모 */
  memos: Memo[];
  /** 이 종목의 체크리스트 (원본: 종목마다 하나) */
  checklist: Checklist | null;
  /** 웹: 카드 순서 (왼쪽 → 오른쪽 · 위 → 아래). 없으면 체크리스트 → 고정 → 최신 순 */
  order?: BoardKey[];
  /** 웹: 사용자가 끌어서 순서를 바꾼 적이 있는지 (없으면 '꾹 눌러 끌면…' 안내를 보여 줌) */
  orderCustomized?: boolean;
  /** AI 사용량을 다 씀 (원본 '.spent' · 웹 SpentBox) */
  aiSpent?: boolean;

  /** 메모 열기 — 상세는 ④에서. 새 소식이 있고 AI 연결이면 'ai' 탭으로 */
  onOpenMemo: (id: string, tab: 'memo' | 'ai') => void;
  onOpenChecklist: () => void;
  /** 새 메모 (빈 보드 예시 칩을 누르면 그 문장이 첫 줄) */
  onNewMemo: (firstLine?: string) => void;
  onNewChecklist: () => void;
  onToggleChecklistItem: (itemId: string) => void;
  onPin: (ids: string[], pinned: boolean) => void;
  /** 체크리스트 고정 (원본 앱: 꾹 눌러 고른 뒤 고정 · 체크리스트 화면 [고정]). 저장 연결은 API 단계 */
  onTogglePin?: (pinned: boolean) => void;
  /** AI 연결 켜기·끄기 (켜기는 ④ AI 연결 창, 끄기는 확인) */
  onToggleAi: (id: string) => void;
  onDelete: (ids: string[]) => void;
  onUndoDelete: (ids: string[]) => void;
  onCopy: (ids: string[]) => void;
  onChangeColor: (ids: string[], color: MemoColor) => void;
  /** 웹: 끌어서 바꾼 순서 */
  onReorder: (order: BoardKey[]) => void;
  /** 메모 보드 ↔ 기업정보 */
  onChangeTab: (tab: 'board' | 'company') => void;
  /** 앱: 고르기 중이면 탭바를 숨김 (고른 개수) */
  onSelectionChange?: (count: number) => void;
  /** 사용량 소진 안내의 버튼 (크레딧 구매 · 플랜 변경) */
  onSpentAction?: (a: 'credit' | 'plan') => void;
}
