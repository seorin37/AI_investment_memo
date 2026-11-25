/**
 * 요금제 카탈로그(GET /plans) → 요금제 · 충전 화면 값 (2026-11-25). 순수 함수 — tests/plan-view.test.mjs
 * 숫자는 서버 configs/credits.yaml 한 곳. MOCK_PLAN_CATALOG 는 mock 모드·불러오기 전 값으로, 설정 파일과 같은 값을 둔다.
 */
import type { PlanCatalog, PlanCatalogPlan } from '@/types/models';
import type { CreditPack, PlanInfo } from './My.mock';

/* planLabel.planKey 와 같은 값 (node --test 가 확장자 없는 상대 import 를 못 읽어 여기 둠) */
const KEY: Record<string, string> = { free: '무료', plus: 'PLUS', pro: 'PRO' };
const planKey = (code: string) => KEY[code] ?? '무료';

export const MOCK_PLAN_CATALOG: Omit<PlanCatalog, 'current_plan' | 'tracking_used'> = {
  plans: [
    { code: 'free', name: '무료', price: 0, first_month_price: null, monthly_credits: 20, tracking_items: 5, summary: '메모 몇 개로 AI 추적을 시작해요', recommended: false },
    { code: 'plus', name: 'PLUS', price: 14900, first_month_price: 7450, monthly_credits: 80, tracking_items: 30, summary: '메모를 꾸준히 쓰고 주간보고서도 보는 분께', recommended: true },
    { code: 'pro', name: 'PRO', price: 29900, first_month_price: 14950, monthly_credits: 160, tracking_items: 100, summary: '종목이 많고 스튜디오를 자주 쓰는 분께', recommended: false },
  ],
  credit_packs: [{ credits: 50, price: 9900 }],
  costs: { card: 1, answer: 1, answer_unverified: 0, price_condition: 0, report: 3, audio: 5, lab: 1 },
};

export const won = (n: number) => `${Math.round(n).toLocaleString('ko-KR')}원`;

function features(p: PlanCatalogPlan): string[] {
  return [`매달 ${p.monthly_credits} 크레딧`, `AI 추적 항목 최대 ${p.tracking_items}개`, '메모·투자 기록 · 가격 알림 무제한', '모든 AI 기능 · 같은 AI 품질'];
}

/** 플랜 카드 3장. tag: 추천(설정 recommended) — 현재 플랜 표시는 planLabel.withCurrentPlan 으로 */
export function toPlanInfos(cat: Pick<PlanCatalog, 'plans'>): PlanInfo[] {
  return cat.plans.map((p) => ({
    key: planKey(p.code),
    price: won(p.price),
    tag: p.recommended ? '추천' : '',
    features: features(p),
    first: p.first_month_price != null && p.first_month_price < p.price ? `첫 달 ${won(p.first_month_price)}` : undefined,
  }));
}

/** 한눈에 비교 (true 는 ✓) */
export function toPlanCompare(cat: Pick<PlanCatalog, 'plans' | 'credit_packs'>): [string, (string | true)[]][] {
  const pack = cat.credit_packs[0];
  return [
    ['월 크레딧', cat.plans.map((p) => String(p.monthly_credits))],
    ['AI 추적 항목', cat.plans.map((p) => `${p.tracking_items}개`)],
    ['첫 달 가격', cat.plans.map((p) => (p.first_month_price != null && p.first_month_price < p.price ? won(p.first_month_price) : '—'))],
    ['메모·투자 기록', cat.plans.map(() => true as const)],
    ['가격 알림', cat.plans.map(() => true as const)],
    ...(pack ? ([[`추가 크레딧 ${pack.credits}개`, cat.plans.map(() => won(pack.price))]] as [string, string[]][]) : []),
  ];
}

/** 안내 줄 (기능별 크레딧은 설정의 costs) */
export function toPlanNotes(cat: Pick<PlanCatalog, 'costs'>): string[] {
  const c = cat.costs;
  return [
    '가격은 부가세 포함이고, 앱과 웹이 같아요.',
    `크레딧은 AI 카드·질문 답 ${c.card ?? 1}, 주간보고서 ${c.report ?? 3}, AI 오디오 ${c.audio ?? 5}, 투자 실험실 ${c.lab ?? 1}개를 써요. 가격 알림과 답을 찾지 못한 질문은 쓰지 않아요.`,
    '언제든 해지할 수 있고, 해지해도 쓴 기간까지는 그대로 써요.',
    '투자 권유·수익 보장 기능은 어떤 플랜에도 없어요.',
  ];
}

/** 추가 크레딧 상품 (충전 창) */
export function toCreditPacks(cat: Pick<PlanCatalog, 'credit_packs'>): CreditPack[] {
  return cat.credit_packs.map((p) => ({ credits: p.credits, label: `${p.credits} 크레딧`, price: won(p.price) }));
}

/** 처음 고를 카드 = 추천 플랜 (없으면 첫 유료) */
export function defaultPlanKey(cat: Pick<PlanCatalog, 'plans'>): string {
  const rec = cat.plans.find((p) => p.recommended) ?? cat.plans.find((p) => p.price > 0) ?? cat.plans[0];
  return rec ? planKey(rec.code) : 'PLUS';
}
