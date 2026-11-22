import { env } from '@/config/env';
import { useUsage } from '@/hooks/queries';
import type { CreditUsage } from '@/types/models';
import { mockMyUsage } from './My.mock';

/**
 * AI 사용량 표시 (스튜디오 머리 · 사용량 창 · 설정 사용량 · 앱 MY · 앱 사용량) — 2026-11-22.
 * 실제 모드: GET /me/usage (실험실 등 크레딧을 쓰면 useRunLab 이 이 캐시를 새로 받게 함). 받기 전·실패면 0%
 * mock 모드: 지금처럼 My.mock 예시 값. 플랜 이름은 아직 서버 칸이 없어 예시 그대로
 */
export type MyUsageView = typeof mockMyUsage;

export function toMyUsage(u: CreditUsage | undefined): MyUsageView {
  if (!u) return { ...mockMyUsage, usage_pct: 0, usage_renew: '', usage_refill: '' };
  const [, m, d] = u.renews_at.slice(0, 10).split('-').map(Number);
  return {
    ...mockMyUsage,
    usage_pct: Math.round(u.usage_percent),
    usage_renew: u.renew_label.replace(/\s*갱신$/, ''),
    usage_refill: `${m}월 ${d}일`,
  };
}

export function useMyUsage(): MyUsageView {
  const usage = useUsage();
  return env.useMock ? mockMyUsage : toMyUsage(usage.data);
}
