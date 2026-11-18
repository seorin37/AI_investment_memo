/** 메모 보드 예시 데이터 — 체험판(웹 v2와 같은 SK하이닉스 메모 5개 + 체크리스트 1개) */
import type { StockSummary } from '@/components/mobile/StockSummaryCard';
import type { BoardEntry, MemoBoardProps } from '@/features/board/MemoBoard.types';

export const mockStockSk: StockSummary = {
  stock_code: '000660',
  name: 'SK하이닉스',
  market: 'KOSPI',
  logo_text: 'S',
  logo_bg: '#EA002C',
  status: 'holding',
  close: 180500,
  change_amount: 4200,
  change_rate: 2.38,
  close_date: '11.12',
  spark: [162000, 160800, 164500, 163900, 168200, 170100, 168900, 172400, 171800, 175600, 174400, 178900, 180500],
};

export const mockBoardItems: BoardEntry[] = [
  { kind: 'memo', id: 'm1', title: '실적 나오면 다시 보기', body: '다음 분기 실적 확인하고\n추가 매수 생각해보기.', color: 'yellow', pinned: true, ai_linked: true, unread_updates: 2, created_at: '2026-10-01T09:00:00+09:00', updated_at: '2026-10-01T09:00:00+09:00' },
  { kind: 'memo', id: 'm2', title: '요즘 반도체 분위기 좋아 보여', body: 'AI 수요 이야기 계속 나와서\n기대감 있는 것 같음.', color: 'blue', pinned: false, ai_linked: true, unread_updates: 1, created_at: '2026-10-03T09:00:00+09:00', updated_at: '2026-10-03T09:00:00+09:00' },
  { kind: 'memo', id: 'm3', title: '15만원 밑으로 오면 다시 생각', body: '지지선 근처 오면\n분할 매수 고민해보기.', color: 'green', pinned: true, ai_linked: true, unread_updates: 0, created_at: '2026-09-25T09:00:00+09:00', updated_at: '2026-10-06T21:14:00+09:00' },
  { kind: 'memo', id: 'm4', title: '삼성전자랑 같이 비교해보기', body: '두 종목 주가 흐름 비교해서\n판단하기.', color: 'purple', pinned: false, ai_linked: false, unread_updates: 0, created_at: '2026-10-09T09:00:00+09:00', updated_at: '2026-10-09T09:00:00+09:00' },
  { kind: 'memo', id: 'm5', title: '너무 급하게 따라 사지 말기', body: '지금은 좀 지켜보고\n조금 더 확인한 뒤에 들어가기.', color: 'pink', pinned: false, ai_linked: false, unread_updates: 0, created_at: '2026-10-05T09:00:00+09:00', updated_at: '2026-10-05T09:00:00+09:00' },
  {
    kind: 'checklist', id: 'c50', title: '체크리스트', pinned: false, created_at: '2026-10-08T09:00:00+09:00', updated_at: '2026-10-08T09:00:00+09:00',
    items: [
      { id: 'c50-1', text: '실적 발표 전 확인', done: false },
      { id: 'c50-2', text: '관련 뉴스 다시 확인', done: true },
      { id: 'c50-3', text: '가격 떨어지면 다시 보기', done: false },
      { id: 'c50-4', text: '삼성전자랑 같이 비교해보기', done: false },
    ],
  },
];

/** 빈 보드 예시 칩 (웹과 같은 문장) */
export const mockBoardExamples = ['실적 나오면 다시 보기', '많이 빠지면 다시 생각해 보기', '요즘 분위기 좋아 보여'];

const noop = () => {};

/** 바로 띄워 볼 수 있는 props 묶음 (화면 확인용) */
export const mockMemoBoardProps: MemoBoardProps = {
  stock: mockStockSk,
  items: mockBoardItems,
  examples: mockBoardExamples,
  onChangeTab: noop,
  onOpenMemo: noop,
  onOpenChecklist: noop,
  onToggleChecklistItem: noop,
  onCreate: noop,
  onPin: noop,
  onDelete: noop,
  onCopy: noop,
  onChangeColor: noop,
  onToggleAi: noop,
};

/** 메모가 없는 종목 (빈 보드 확인용) */
export const mockMemoBoardEmptyProps: MemoBoardProps = {
  ...mockMemoBoardProps,
  stock: { ...mockStockSk, stock_code: '000270', name: '기아', logo_text: '기', logo_bg: '#05141F', status: 'watching', close: 101300, change_amount: 300, change_rate: 0.3 },
  items: [],
};
