import { env } from '@/config/env';
import { useUsage } from '@/hooks/queries';
import { mockMyUsage } from './My.mock';
import { planName } from './planLabel';
import { useMyProfile } from './useMyProfile';
import { toUsageView, USAGE_UNKNOWN, type UsageView } from './usageView';

/**
 * 설정 · MY · 스튜디오의 AI 사용량 (2026-11-22).
 * - 실제 모드: GET /me/usage → toUsageView. 불러오는 중 · 실패는 USAGE_UNKNOWN ('—', 0%) — 숫자를 지어내지 않음
 * - mock 모드: 지금처럼 My.mock (mockMyUsage)
 * - plan_name: 로그인 사용자 plan (planName)
 */
export function useUsageView(): UsageView & { plan_name: string; ready: boolean; failed: boolean } {
  const real = !env.useMock;
  const q = useUsage();
  const { plan } = useMyProfile();
  const plan_name = planName(plan);
  if (!real) return { ...mockMyUsage, paused: mockMyUsage.usage_pct >= 100, plan_name, ready: true, failed: false };
  const view = q.data ? toUsageView(q.data) : USAGE_UNKNOWN;
  return { ...view, plan_name, ready: !!q.data, failed: q.isError && !q.data };
}
