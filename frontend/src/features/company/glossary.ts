/** 지표 설명 (시안 7.1 문구) */
export interface Term {
  title: string;
  desc: string;
  formula?: string;
  glance?: string;
}

export const glossary = {
  per: { title: 'PER · 주가수익비율', desc: '이익에 비해 주가가 얼마나 높은지 보여줘요.', formula: '주가 ÷ 주당순이익(EPS)' },
  eps: { title: 'EPS · 주당순이익', desc: '회사가 벌어들인 순이익 중 보통주 한 주에 해당하는 금액이에요.' },
  pbr: { title: 'PBR · 주가순자산비율', desc: '순자산에 비해 주가가 얼마나 높은지 보여줘요.', formula: '주가 ÷ 주당순자산(BPS)' },
  bps: { title: 'BPS · 주당순자산', desc: '자산에서 부채를 뺀 순자산 중 보통주 한 주에 해당하는 금액이에요.' },
  mcap: { title: '시가총액', desc: '주식시장에서 평가하는 기업의 전체 주식 가치예요.', formula: '현재 주가 × 상장주식수' },
  shares: { title: '상장주수', desc: '거래소에 상장된 주식의 총수예요. 실제 시장에서 거래 가능한 유통주식 수와는 다를 수 있어요.' },
  revenue: {
    title: '매출이란?',
    desc: '상품을 팔거나 서비스를 제공해 벌어들인 금액이에요. 아직 비용을 빼기 전의 금액으로, 기업의 사업 규모를 보여줘요.',
    glance: '한눈에 · 얼마나 팔았나요?',
  },
  operating: {
    title: '영업이익이란?',
    desc: '매출에서 제품을 만드는 비용과 판매·관리에 든 비용을 뺀 이익이에요. 본업으로 얼마나 벌었는지 보여주며, 금액이 음수라면 영업손실이에요.',
    glance: '한눈에 · 본업으로 얼마나 남겼나요?',
  },
  net: {
    title: '당기순이익이란?',
    desc: '모든 수익과 비용, 법인세까지 반영한 최종 이익이에요. 본업 외의 손익도 포함하며, 금액이 음수라면 당기순손실이에요.',
    glance: '한눈에 · 최종적으로 얼마나 남았나요?',
  },
  opm: { title: '영업이익률', desc: '매출 중 본업으로 남긴 이익의 비율이에요.', formula: '영업이익 ÷ 매출 × 100' },
  npm: { title: '순이익률', desc: '매출 중 모든 비용과 세금을 뺀 최종 이익의 비율이에요.', formula: '당기순이익 ÷ 매출 × 100' },
  roe: { title: 'ROE', desc: '주주의 자본으로 얼마나 이익을 냈는지 보여줘요.', formula: '당기순이익 ÷ 평균 자기자본 × 100' },
  debt: { title: '부채비율', desc: '자기자본 대비 부채가 얼마나 많은지 보여줘요. 낮을수록 재무 부담이 적어요.', formula: '부채총계 ÷ 자기자본 × 100' },
  current: { title: '유동비율', desc: '1년 안에 갚을 빚을 1년 안에 현금이 되는 자산으로 얼마나 덮는지예요.', formula: '유동자산 ÷ 유동부채 × 100 · 높을수록 단기 지급 여유가 커요.' },
  quick: { title: '당좌비율', desc: '재고자산을 빼고도 단기 부채를 갚을 수 있는지 보여줘요.', formula: '(유동자산 − 재고자산) ÷ 유동부채 × 100' },
  icr: { title: '이자보상비율', desc: '영업이익으로 이자비용을 몇 번 갚을 수 있는지 보여줘요.', formula: '영업이익 ÷ 이자비용 · 1배 미만이면 이자 부담이 커요.' },
  reserve: { title: '유보율', desc: '사업으로 번 돈을 회사 안에 얼마나 쌓아 두었는지 보여줘요.', formula: '(이익잉여금 + 자본잉여금) ÷ 납입자본금 × 100' },
} satisfies Record<string, Term>;

export type TermKey = keyof typeof glossary;
