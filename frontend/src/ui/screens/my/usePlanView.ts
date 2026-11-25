import { env } from '@/config/env';
import { usePlans } from '@/hooks/queries';
import { MOCK_PLAN_CATALOG, defaultPlanKey, toCreditPacks, toPlanCompare, toPlanInfos, toPlanNotes } from './planView';

/**
 * 요금제 · 충전 화면 값 (2026-11-25). 실제 모드: GET /plans (configs/credits.yaml). mock 모드 · 불러오기 전: 같은 값의 MOCK_PLAN_CATALOG.
 */
export function usePlanView() {
  const q = usePlans();
  const cat = !env.useMock && q.data ? q.data : MOCK_PLAN_CATALOG;
  const packs = toCreditPacks(cat);
  return {
    plans: toPlanInfos(cat),
    compare: toPlanCompare(cat),
    notes: toPlanNotes(cat),
    default_key: defaultPlanKey(cat),
    packs,
    default_credits: packs[0]?.credits ?? 50,
    /** 서버 값 (실제 모드) — 무료/유료별 문구에 씀 */
    catalog: cat,
  };
}
