import { env } from '@/config/env';
import { useMacro } from '@/hooks/queries';
import type { MacroIndicator, MacroOverview } from '@/types/models';
import { mockLabVars } from './Studio.mock';

/**
 * 투자 실험실 변수 4개의 '지금 값' (2026-11-21, 기업정보 useCompanyInfo 와 같은 틀).
 * - GET /market/macro (ECOS 환율·기준금리, FRED 미국 10년물·WTI) → mockLabVars 의 now 문장만 바꾼다 (이름·기본 방향·경로는 그대로)
 * - 문장은 관측값과 관측일만 ('MM.DD 기준 …'). 전망·장중 문구 없음
 * - USE_MOCK=true 면 지금처럼 mock 문장. 실제 모드에서 값이 없으면 미연결 안내
 */
export type LabVar = (typeof mockLabVars)[number];

export const LAB_NOT_CONNECTED = '데이터가 아직 연결되지 않았어요';

const mmdd = (d: string) => `${d.slice(5, 7)}.${d.slice(8, 10)}`;
const n2 = (v: number) => v.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** mockLabVars 순서와 같은 지표 · 문장 */
const LAB_SOURCES: [string, (i: MacroIndicator) => string][] = [
  ['USD_KRW', (i) => `${mmdd(i.observed_date)} 기준 ${n2(i.value)}원`],
  ['WTI_SPOT', (i) => `${mmdd(i.observed_date)} 기준 배럴당 ${i.value.toFixed(1)}달러`],
  ['KR_POLICY_RATE', (i) => `${mmdd(i.observed_date)} 기준 ${i.value.toFixed(2)}%`],
  ['US_TREASURY_10Y', (i) => `${mmdd(i.observed_date)} 기준 ${i.value.toFixed(2)}%`],
];

export function toLabVars(m: MacroOverview | undefined): LabVar[] {
  const by = new Map((m?.indicators ?? []).map((i) => [i.key, i]));
  return mockLabVars.map((v, idx) => {
    const [key, text] = LAB_SOURCES[idx];
    const i = by.get(key);
    return { ...v, now: i ? text(i) : LAB_NOT_CONNECTED };
  });
}

export function useLabVars(): LabVar[] {
  const real = !env.useMock;
  const q = useMacro(real);
  if (!real) return mockLabVars;
  return toLabVars(q.data);
}
