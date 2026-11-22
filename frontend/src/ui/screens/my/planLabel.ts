/**
 * 요금제 표시 (2026-11-22). 순수 함수 — tests/plan-label.test.mjs
 * users.plan(free·plus·pro) → 화면 문구 · My.mock mockPlans 의 key('무료' · 'PLUS' · 'PRO').
 * 모르는 값이나 없음(mock 사용자 등)은 무료로 본다.
 */
type PlanCode = 'free' | 'plus' | 'pro';

const NAME: Record<PlanCode, string> = { free: '무료 플랜', plus: 'PLUS 플랜', pro: 'PRO 플랜' };
const KEY: Record<PlanCode, string> = { free: '무료', plus: 'PLUS', pro: 'PRO' };

function code(plan: string | null | undefined): PlanCode {
  return plan === 'plus' || plan === 'pro' ? plan : 'free';
}

/** 사용량 카드 등의 플랜 이름 */
export function planName(plan: string | null | undefined): string {
  return NAME[code(plan)];
}

/** 플랜 카드 key (mockPlans[].key 와 같은 값) */
export function planKey(plan: string | null | undefined): string {
  return KEY[code(plan)];
}

/**
 * 플랜 카드 목록에서 '현재 플랜' 태그를 실제 플랜 카드로 옮긴다.
 * 다른 카드의 '현재 플랜'은 지우고, '추천' 은 현재 플랜 카드가 아니면 그대로 둔다.
 */
export function withCurrentPlan<T extends { key: string; tag: string }>(plans: readonly T[], currentKey: string): T[] {
  return plans.map((p) => {
    if (p.key === currentKey) return { ...p, tag: '현재 플랜' };
    if (p.tag === '현재 플랜') return { ...p, tag: '' };
    return p;
  });
}
