import type { Checklist, Memo, MemoColor } from '@/types/models';
import type { StockHeadProps } from '@/ui/shared/StockHead.types';

/**
 * 예시 데이터 — 웹 원본 예시 계정(src/api/mock/seed.ts) 기준 (11.18 종가 · 작성일은 11.19 기준 날짜)
 * 문구 규칙(7번)으로 바꾼 메모 본문은 보고서의 '바꾼 문구' 목록에.
 */
const memo = (id: string, color: MemoColor, created: string, title: string, body: string, o: { ai?: boolean; pinned?: boolean; unread?: number; edited?: string } = {}): Memo => ({
  id,
  kind: 'memo',
  stock_code: '000660',
  title,
  body,
  tags: [],
  color,
  pinned: !!o.pinned,
  ai_linked: !!o.ai,
  ai_linked_at: o.ai ? `${created}T09:00:00+09:00` : null,
  price_conditions: [],
  unread_updates: o.unread ?? 0,
  position: 0,
  created_at: `${created}T09:00:00+09:00`,
  updated_at: `${o.edited ?? created}T09:00:00+09:00`,
});

export const mockBoardStock: StockHeadProps = {
  stock_code: '000660',
  name: 'SK하이닉스',
  market: 'KOSPI',
  status: 'holding',
  logo: 'S',
  logo_bg: '#EA002C',
  price: 180500,
  change: 1700,
  change_pct: 0.95,
  as_of: '11.18',
  closes: [171200, 169800, 172500, 170900, 173400, 175200, 174100, 176800, 175900, 177300, 176200, 178900, 177600, 179400, 178800, 180500],
};

export const mockBoardMemos: Memo[] = [
  memo('m1', 'yellow', '2026-10-03', '실적 나오면 다시 보기', '다음 분기 실적 확인하고\n비중 다시 점검해보기.', { ai: true, pinned: true, unread: 1 }),
  memo('m2', 'blue', '2026-10-05', '요즘 반도체 분위기 좋아 보여', 'HBM 수요 이야기가 계속 나오는지\n지켜보기.', { ai: true, unread: 1 }),
  memo('m3', 'green', '2026-09-27', '15만원 밑으로 오면 다시 생각', '지지선 근처 오면\n비중 다시 점검해보기.', { ai: true, pinned: true, edited: '2026-10-08' }),
  memo('m4', 'purple', '2026-10-11', '삼성전자랑 같이 비교해보기', '두 종목 주가 흐름 비교해서\n판단하기.'),
  memo('m5', 'pink', '2026-10-07', '너무 급하게 판단하지 말기', '지금은 좀 지켜보고\n조금 더 확인한 뒤에 다시 보기.'),
];

export const mockBoardChecklist: Checklist = {
  id: 'cl-000660',
  kind: 'checklist',
  stock_code: '000660',
  title: '체크리스트',
  position: 0,
  created_at: '2026-10-09T09:00:00+09:00',
  /* 원본 앱 보드에서 '삼성전자랑 같이 비교해보기'(10.11) 다음 자리 */
  updated_at: '2026-10-09T09:00:00+09:00',
  items: [
    { id: 'c1', text: '실적 발표 전 확인', done: false },
    { id: 'c2', text: '관련 뉴스 다시 확인', done: true },
    { id: 'c3', text: '가격 떨어지면 다시 보기', done: false },
    { id: 'c4', text: '삼성전자랑 같이 비교해보기', done: false },
  ],
};

/** 웹 카드 순서 — 원본 예시 계정의 3칸 배치(체크리스트·노랑 | 보라·파랑 | 초록·분홍)를 왼쪽 → 오른쪽으로 읽은 것 */
export const mockBoardOrder = ['cl', 'm4', 'm3', 'm1', 'm2', 'm5'];

/** 메모가 없는 종목 (빈 보드) */
export const mockEmptyStock: StockHeadProps = { ...mockBoardStock, stock_code: '105560', name: 'KB금융', status: 'watching', logo: 'KB', logo_bg: '#FFB400', price: 78300, change: 900, change_pct: 1.16, closes: [76100, 76500, 75900, 76800, 77200, 76900, 77600, 78000, 77400, 78300] };
