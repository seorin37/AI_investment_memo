/** 투자 기록 예시 — 체험판/웹 v2와 같은 4개. 사용자가 쓴 글 예시라 '매수·손절' 같은 말이 들어 있음(앱 문구 아님) */
import type { JournalListProps } from '@/features/journal/JournalList.types';

export const mockJournalListProps: JournalListProps = {
  notes: [
    { id: 'j1', title: '10/13 투자 복기', date_label: '2026. 10. 13.', group: '지난 30일', pinned: false, preview: '오늘 반도체 업종이 강세를 보였다. SK하이닉스는 HBM4 공급 확대 기대감에 상승했고, 삼성전자는 장 초반 약세 뒤 회복했다.' },
    { id: 'j2', title: '10/08 실적 발표 전 점검', date_label: '2026. 10. 8.', group: '지난 30일', pinned: false, preview: '발표일 확인하고 체크리스트 정리. 컨센서스 대비 가이던스 문구를 꼭 볼 것.' },
    { id: 'j3', title: '10/01 매수 전략 메모', date_label: '2026. 10. 1.', group: '10월', pinned: false, preview: '급하게 따라 사지 않기. 15만원 근처에서만 분할로 접근.' },
    { id: 'j4', title: '09/25 손절 기준 정리', date_label: '2026. 9. 25.', group: '9월', pinned: false, preview: '지지선 근처에서 분할 매수 고민. -10%면 이유를 다시 적고 판단하기.' },
  ],
  onOpen: () => {},
  onNew: () => {},
  onDictate: () => {},
};
