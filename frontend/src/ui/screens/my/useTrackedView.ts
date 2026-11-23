import { env } from '@/config/env';
import { useAiTracking } from '@/hooks/queries';
import { BRAND_LOGOS } from '@/lib/brandLogos';
import type { AiTrackingStock } from '@/types/models';
import { mockTracked, type TrackedStock } from './My.mock';

/** 서버 추적 현황 → 화면 줄. 로고는 대표색 표(lib/brandLogos), 없으면 이름 첫 글자 + 회색 */
export function fromServerTracking(rows: AiTrackingStock[]): TrackedStock[] {
  return rows.map((r) => {
    const b = BRAND_LOGOS[r.stock_code];
    return {
      stock_code: r.stock_code,
      name: r.name,
      logo: b?.logo ?? r.name.slice(0, 1),
      logo_bg: b?.logo_bg ?? '#575B63',
      memos: r.memos.map((m) => ({ memo_id: m.memo_id, title: m.title, chips: m.chips })),
    };
  });
}

/** 설정 사용량 탭 '종목별 추적 현황'. 실제 모드는 GET /ai/tracking, mock 모드는 My.mock 예시 (2026-11-23) */
export function useTrackedView(enabled = true): TrackedStock[] {
  const q = useAiTracking(!env.useMock && enabled);
  if (env.useMock) return mockTracked;
  return fromServerTracking(q.data ?? []);
}
