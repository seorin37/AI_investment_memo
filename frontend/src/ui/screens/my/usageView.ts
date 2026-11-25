/**
 * GET /me/usage → 화면 사용량 값 (2026-11-22). 순수 함수 — tests/usage-view.test.mjs
 * 주기는 서버(backend/app/credits/ledger.py)가 정함: 사용자 시작점 기준 한 달 고정 주기, renews_at = 다음 주기 시작(한국 시간 0시).
 * 화면 문구는 모두 '갱신되는 날'(다음 갱신 12.20 · 12.20 갱신 · 12월 20일에 새로 채워져요)이라 두 값이 같은 날을 가리킨다:
 * - usage_renew  '12.20'     = renews_at 의 한국 날짜 (MM.DD)
 * - usage_refill '12월 20일' = 같은 날 (M월 D일)
 * renews_at 이 +09:00 이든 Z(UTC)이든 한국 시간으로 바꿔서 날짜를 뽑는다 (기기 시간대와 무관)
 */
export interface UsageWire {
  usage_percent: number;
  renews_at: string;
  paused: boolean;
  ai_memo_count?: number;
  auto_off_count?: number;
  used?: number;
  balance?: number;
}

export interface UsageView {
  usage_pct: number;
  usage_renew: string;
  usage_refill: string;
  paused: boolean;
  /** 지금 AI 연결이 켜진 메모 수 (선택 창 N) */
  ai_count: number;
  /** 갱신일에 자동으로 꺼진 메모 수 (안내 N) */
  auto_off: number;
  /** 이번 기간 쓴 크레딧 · 남은 크레딧 (2026-11-25 사용량 화면 'n / m 크레딧'). 모르면 null */
  credits_used: number | null;
  credits_left: number | null;
}

/** 불러오지 못했을 때 (확인용 읽기 전용 서버에서 GET 이 쓰기를 못 해 실패 등) — 숫자를 지어내지 않음 */
export const USAGE_UNKNOWN: UsageView = { usage_pct: 0, usage_renew: '—', usage_refill: '—', paused: false, ai_count: 0, auto_off: 0, credits_used: null, credits_left: null };

const KST_MS = 9 * 60 * 60 * 1000;

/** ISO 시각 → 한국 날짜 [월, 일]. 시간대가 없는 날짜만 있는 값('2026-12-20')은 그 날짜 그대로 */
export function kstMonthDay(iso: string): [number, number] | null {
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (dateOnly) return [Number(dateOnly[2]), Number(dateOnly[3])];
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  const k = new Date(t + KST_MS);                 // UTC 필드 = 한국 시각
  return [k.getUTCMonth() + 1, k.getUTCDate()];
}

export function toUsageView(u: UsageWire): UsageView {
  const pct = clampPct(u.usage_percent);
  const md = kstMonthDay(u.renews_at);
  const ai_count = Math.max(0, Number(u.ai_memo_count) || 0);
  const auto_off = Math.max(0, Number(u.auto_off_count) || 0);
  const credits_used = Number.isFinite(u.used) ? Math.max(0, Number(u.used)) : null;
  const credits_left = Number.isFinite(u.balance) ? Math.max(0, Number(u.balance)) : null;
  if (!md) return { ...USAGE_UNKNOWN, usage_pct: pct, paused: !!u.paused, ai_count, auto_off, credits_used, credits_left };
  const [m, d] = md;
  return { usage_pct: pct, usage_renew: `${String(m).padStart(2, '0')}.${String(d).padStart(2, '0')}`, usage_refill: `${m}월 ${d}일`, paused: !!u.paused, ai_count, auto_off, credits_used, credits_left };
}

function clampPct(n: number): number {
  return Number.isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : 0;
}
