import type { AiStats, CreditUsage } from '@/types/models';

/** 스튜디오 홈 · 웹 사이드바 스튜디오 머리에 쓰는 숫자 (화면 모양) */
export interface StudioHead {
  /** AI 사용량 % (0~100) */
  usage_pct: number;
  /** 다시 채워지는 날 '12월 1일' */
  usage_refill: string;
  /** 내 종목 수 */
  stock_count: number;
  /** AI 연결 메모 수 */
  ai_memo_count: number;
  /** 다 씀 → 만들기 막기 (퀴즈 제외) */
  spent: boolean;
}

/** renews_at(다음 기간 시작, ISO) → 한국 날짜 '12월 1일' */
export function refillLabel(renewsAt: string): string {
  const d = new Date(+new Date(renewsAt) + 9 * 3600_000);
  return `${d.getUTCMonth() + 1}월 ${d.getUTCDate()}일`;
}

/**
 * GET /me/usage · GET /stocks 길이 · GET /ai/stats → 스튜디오 숫자 (2026-11-22).
 * 아직 받는 중이면 0 · 빈 글자 (화면은 그대로 그려짐). paused(남은 크레딧 0)도 다 쓴 것으로.
 */
export function toStudioHead(usage: CreditUsage | undefined, stockCount: number | undefined, ai: AiStats | undefined): StudioHead {
  const pct = Math.max(0, Math.min(100, Math.round(usage?.usage_percent ?? 0)));
  return {
    usage_pct: pct,
    usage_refill: usage?.renews_at ? refillLabel(usage.renews_at) : '',
    stock_count: stockCount ?? 0,
    ai_memo_count: ai?.linked_memos ?? 0,
    spent: pct >= 100 || !!usage?.paused,
  };
}
