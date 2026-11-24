import type { Financials } from '@/types/models';
import { finKB, finSK } from '@/ui/screens/company/companyData.mock';

/* 기업정보 재무 mock (2026-11-21): UI v2 예시 값(SK하이닉스 · KB금융)을 실제 API 모양으로. 105560 = 금융사 예시, 나머지는 SK하이닉스 값 */
const END: Record<string, string> = { '1': '03-31', '2': '06-30', '3': '09-30', '4': '12-31' };
const endOf = (q: string) => `20${q.slice(0, 2)}-${END[q.slice(3, 4)]}`;

export function mockFinancials(code: string): Financials {
  const financial = code === '105560';
  const src = financial ? finKB : finSK;
  return {
    code,
    source_code: code,
    sector: financial ? 'financial' : 'general',
    fin_type: financial ? 'holding' : null,
    financial,
    preparing: false,
    basis: `${src.as_of.slice(0, 4)}년 ${src.as_of.slice(5, 7)}월 기준 · 연결재무제표`,
    quarters: src.quarters.map((x) => ({
      period_end: endOf(x.q),
      q: x.q,
      label: x.label,
      revenue: x.revenue,
      op: x.op,
      net: x.net,
      op_margin: x.op_margin,
      net_margin: x.net_margin,
      roe: x.roe,
    })),
    health: { debt: src.health.debt, current: src.health.current, quick: src.health.quick, interest: src.health.interest, reserve: src.health.reserve },
    health_as_of: src.as_of,
    interest_coverage_basis: financial ? null : 'cf_paid',
  };
}
