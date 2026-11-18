/** 체크리스트 예시 — 체험판 SK하이닉스 보드의 체크리스트(4개 중 1개 완료) */
import type { ChecklistDetailProps } from '@/features/board/ChecklistDetail.types';

const noop = () => {};

export const mockChecklistDetailProps: ChecklistDetailProps = {
  mode: 'edit',
  title: '체크리스트',
  date_full: '2026년 10월 8일 작성',
  pinned: false,
  items: [
    { id: 'c50-1', text: '실적 발표 전 확인', done: false },
    { id: 'c50-2', text: '관련 뉴스 다시 확인', done: true },
    { id: 'c50-3', text: '가격 떨어지면 다시 보기', done: false },
    { id: 'c50-4', text: '삼성전자랑 같이 비교해보기', done: false },
  ],
  onChangeTitle: noop,
  onToggleItem: noop,
  onDeleteItem: noop,
  onAddItem: noop,
};

/** + 버튼 → 체크리스트 (빈 새 체크리스트) */
export const mockChecklistNewProps: ChecklistDetailProps = { ...mockChecklistDetailProps, mode: 'new', date_full: '2026년 11월 12일 작성', items: [] };
