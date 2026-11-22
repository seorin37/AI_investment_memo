import { env } from '@/config/env';
import { useAiStats, useMyStocks, useUsage } from '@/hooks/queries';
import { mockStudioHead } from '@/ui/layout/web/WebShell.mock';
import { mockMyUsage } from '@/ui/screens/my/My.mock';
import { mockStudioCounts } from './Studio.mock';
import { toStudioHead, type StudioHead } from './studioHead';

/**
 * 스튜디오 숫자 (앱 스튜디오 홈 · 웹 사이드바 스튜디오 머리 · 웹 사용량 창 · 다 씀 판단).
 * 실제 모드: GET /me/usage · GET /stocks · GET /ai/stats. mock 모드: 예전 예시 값.
 * MY · 설정의 사용량은 이 훅을 쓰지 않음 (MY 묶음 담당) — 같은 숫자로 맞추려면 이 훅을 쓰면 됨.
 */
export function useStudioHead(): StudioHead {
  const usage = useUsage();
  const stocks = useMyStocks();
  const ai = useAiStats();
  if (env.useMock) {
    return {
      usage_pct: mockMyUsage.usage_pct,
      usage_refill: mockMyUsage.usage_refill,
      stock_count: mockStudioCounts.stock_count ?? mockStudioHead.stockCount,
      ai_memo_count: mockStudioCounts.ai_memo_count ?? mockStudioHead.aiMemoCount,
      spent: mockMyUsage.usage_pct >= 100,
    };
  }
  return toStudioHead(usage.data, stocks.data?.length, ai.data);
}
