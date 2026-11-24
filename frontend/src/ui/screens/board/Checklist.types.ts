import type { ChecklistItem } from '@/types/models';

/** 앱 체크리스트 페이지 (원본 app/memo.html .ckp) */
export interface AppChecklistProps {
  /** 'edit' = 보드에서 열기 (밀려 들어옴 · 뒤로 · 고정) / 'new' = + 버튼 (아래에서 올라옴 · 취소 · 완료) */
  mode: 'edit' | 'new';
  /** 새 체크리스트 머리 '{종목} · 새 체크리스트' */
  stock_name: string;
  title: string;
  /** '2026년 10월 9일 작성' */
  date_full: string;
  items: ChecklistItem[];
  pinned: boolean;
  onChangeTitle: (title: string) => void;
  onToggleItem: (id: string) => void;
  onDeleteItem: (id: string) => void;
  onAddItem: (text: string) => void;
  onTogglePin: () => void;
  onBack: () => void;
  onCancel: () => void;
  onDone: () => void;
}
