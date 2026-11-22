import { mockDetailStockName, mockLastChecked, mockTrackItems } from './MemoDetail.mock';
import type { MemoDetailProps } from './MemoDetail.types';
import { feedOf, findMemo, mockUpdateStocks, versionsOf } from '@/ui/screens/updates/Updates.mock';

/** 사용법 안내 예시 메모 = mock 'm1' (2026-11-22). useMemoScreen 의 mock 경로와 같은 출처 — 새 문구 · 수치 없음 */
export const COACH_EXAMPLE_MEMO_ID = 'm1';

export function coachExampleMemo(): Pick<MemoDetailProps, 'memo' | 'stockName' | 'versions' | 'feed' | 'trackItems' | 'lastChecked'> {
  const memo = findMemo(COACH_EXAMPLE_MEMO_ID);
  return {
    memo,
    stockName: mockUpdateStocks.find((s) => s.stock_code === memo.stock_code)?.name ?? mockDetailStockName,
    versions: versionsOf(memo.id),
    feed: feedOf(memo.id),
    trackItems: mockTrackItems[memo.id] ?? [],
    lastChecked: mockLastChecked,
  };
}

/** 예시 화면은 읽기만: 모든 동작은 아무것도 하지 않음 (서버 호출 · 저장 없음) */
const noop = () => {};
export const COACH_EXAMPLE_HANDLERS: Pick<
  MemoDetailProps,
  'onBack' | 'onSave' | 'onChangeColor' | 'onTogglePin' | 'onDelete' | 'onCopy' | 'onConnectAi' | 'onDisconnectAi'
> = { onBack: noop, onSave: noop, onChangeColor: noop, onTogglePin: noop, onDelete: noop, onCopy: noop, onConnectAi: noop, onDisconnectAi: noop };
