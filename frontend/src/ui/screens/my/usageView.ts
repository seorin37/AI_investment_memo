/**
 * GET /me/usage → 화면 사용량 값 (2026-11-22). 순수 함수 — tests/usage-view.test.mjs
 * 주기는 서버(backend/app/credits/ledger.py)가 정함: 사용자 시작점 기준 한 달 고정 주기, renews_at = 다음 주기 시작(한국 시간 0시).
 * - usage_renew '12.19'  = 이번 주기 마지막 날 (renews_at 하루 전, 서버 renew_label 과 같은 날)
 * - usage_refill '12월 20일' = 다음 주기 시작일 (새로 채워지는 날)
 * 날짜는 renews_at 문자열의 날짜 부분(서버가 +09:00 로 줌)을 그대로 써서 기기 시간대와 무관
 */
export interface UsageWire {
  usage_percent: number;
  renews_at: string;
  paused: boolean;
}

export interface UsageView {
  usage_pct: number;
  usage_renew: string;
  usage_refill: string;
  paused: boolean;
}

/** 불러오지 못했을 때 (확인용 읽기 전용 서버에서 GET 이 쓰기를 못 해 실패 등) — 숫자를 지어내지 않음 */
export const USAGE_UNKNOWN: UsageView = { usage_pct: 0, usage_renew: '—', usage_refill: '—', paused: false };

function ymd(iso: string): [number, number, number] | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}

export function toUsageView(u: UsageWire): UsageView {
  const d = ymd(u.renews_at);
  if (!d) return { ...USAGE_UNKNOWN, usage_pct: clampPct(u.usage_percent), paused: !!u.paused };
  const [y, m, day] = d;
  const last = new Date(Date.UTC(y, m - 1, day - 1));                 // 하루 전 (달 · 해 넘김 포함)
  const mm = String(last.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(last.getUTCDate()).padStart(2, '0');
  return { usage_pct: clampPct(u.usage_percent), usage_renew: `${mm}.${dd}`, usage_refill: `${m}월 ${day}일`, paused: !!u.paused };
}

function clampPct(n: number): number {
  return Number.isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : 0;
}
