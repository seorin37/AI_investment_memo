/** 메모 상세 예시 — 체험판 '15만원 밑으로 오면 다시 생각'(소식 3개)과 '실적 나오면 다시 보기'(소식 2개) */
import type { MemoDetailProps } from '@/features/board/MemoDetail.types';

const noop = () => {};

export const mockMemoDetailProps: MemoDetailProps = {
  memo: {
    id: 'm3',
    title: '15만원 밑으로 오면 다시 생각',
    body: '지지선 근처 오면\n분할 매수 고민해보기.',
    color: 'green',
    pinned: true,
    ai_linked: true,
    date_full: '2026년 10월 6일 수정',
    ai_linked_on: '09.25',
    created_on: '09.25',
    tracking_items: [{ id: 't1', kind: 'price', label: '15만원 이하가 되면 알려드려요' }],
  },
  updates: [
    { id: 'u1', kind: 'news', date: '10.15', is_new: false, headline: 'HBM4 공급 확대 소식이 나왔어요', summary: '메모에서 확인하려던 "15만원 조건가" 관련 뉴스예요.', source: '네이버 뉴스 · 2026. 10. 15. 08:40', article_title: 'SK하이닉스, HBM4 공급 확대 관련 보도' },
    { id: 'u2', kind: 'price', date: '10.11', is_new: false, headline: '15만원 조건가에서 멀어졌어요', summary: '10.11 종가 180,500원 · 조건가보다 30,500원(20.3%) 높아요. 아직 설정한 15만원 조건에 도달하지 않았어요.', source: '전일 확정 종가 · 2026. 10. 11.', price: { close: 180500, condition: 150000, gap_text: '+30,500원 (+20.3%)', tone: 'far' } },
    { id: 'u3', kind: 'disclosure', date: '09.29', is_new: false, headline: '3분기 실적 발표가 예정돼 있어요', summary: '10월 24일 실적 발표 예정 소식이에요. 가격 조건과 함께 살펴볼 일정으로 연결했어요.', source: 'DART · 2026. 09. 29. 17:05' },
  ],
  tab: 'ai',
  onChangeTab: noop,
  editing: false,
  draft: '15만원 밑으로 오면 다시 생각\n지지선 근처 오면\n분할 매수 고민해보기.',
  onStartEdit: noop,
  onChangeDraft: noop,
  onOpenEvidence: noop,
  onOpenOriginal: noop,
  onToggleAi: noop,
  onOpenHistory: noop,
};

/** AI 연결은 켰지만 아직 소식이 없는 메모 (네이버 'AI 검색 반응 보기') */
export const mockMemoDetailNoUpdates: MemoDetailProps = {
  ...mockMemoDetailProps,
  memo: { id: 'm208', title: 'AI 검색 반응 보기', body: '서비스 개편 후 이용자 반응 확인.', color: 'green', pinned: false, ai_linked: true, date_full: '2026년 10월 18일 작성', ai_linked_on: '10.18', created_on: '10.18', tracking_items: [{ id: 't9', kind: 'disclosure_news', label: 'AI 검색 서비스 반응' }] },
  updates: [],
};
