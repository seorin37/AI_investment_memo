/**
 * 로그인 뒤 갈 곳 (2026-11-21). 신규면 약관(/terms) → 종목 고르기 → 홈(?onboarding=) → 사용법 안내, 아니면 홈(/).
 * 임시 기준 — 약관 기록으로 바꿀 것 (0022 약관 동의 저장 뒤). 지금은 '내 종목 0개 = 신규'.
 * 내 종목 조회(GET /stocks · mock 모드는 mock 값)가 실패하면 홈으로 (안내가 잘못 뜨지 않는 쪽).
 * 순수 함수: tests/after-login.test.mjs
 */
export type AfterLoginRoute = '/terms' | '/';

export async function routeAfterLogin(listMyStocks: () => Promise<readonly unknown[]>): Promise<AfterLoginRoute> {
  try {
    const mine = await listMyStocks();
    return mine.length === 0 ? '/terms' : '/';
  } catch {
    return '/';
  }
}
