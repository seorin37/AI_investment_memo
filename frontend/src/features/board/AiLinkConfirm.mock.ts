/** AI 연결 예시 — 체험판 '실적 나오면 다시 보기'에서 찾은 항목 */
import type { AiLinkConfirmProps } from '@/features/board/AiLinkConfirm.types';

const noop = () => {};

export const mockAiLinkConfirmProps: AiLinkConfirmProps = {
  step: 'select',
  stock_name: 'SK하이닉스',
  memo: { title: '15만원 밑으로 오면 다시 생각', body: '지지선 근처 오면\n분할 매수 고민해보기.\n다음 분기 실적도 확인하기.', color: 'green' },
  candidates: [
    { id: 'k1', kind: 'disclosure_news', label: '실적 발표 내용', quote: '다음 분기 실적도 확인하기.', selected: true },
    { id: 'k2', kind: 'price', label: '15만원 이하가 되면 알려드려요', quote: '15만원 밑으로 오면 다시 생각', price: { condition: 150000, direction: '이하' }, selected: true },
  ],
  onToggleCandidate: noop,
  onConnect: noop,
  onLater: noop,
  onEditMemo: noop,
};

export const mockAiLinkNoneProps: AiLinkConfirmProps = { ...mockAiLinkConfirmProps, step: 'none', memo: { title: '너무 급하게 따라 사지 말기', body: '지금은 좀 지켜보고\n조금 더 확인한 뒤에 들어가기.', color: 'pink' }, candidates: [] };
