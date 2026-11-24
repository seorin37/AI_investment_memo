/**
 * 로그인 뒤 · 약관 동의 뒤 갈 곳 (2026-11-22). 순수 함수: tests/after-login.test.mjs
 *
 * 로그인 뒤: 필수 약관(GET /me/terms complete)을 다 동의하지 않았으면 /terms, 했으면 / (내 종목 0개여도 /).
 *   조회가 실패하면 / (안내가 잘못 뜨지 않는 쪽 — 한계: 그때는 미동의자도 홈으로 감).
 * 약관 동의 뒤: 저장(POST /me/terms)이 실패하면 이동하지 않음. 성공하면 내 종목 1개 이상이면 /, 0개면 /onboarding/pick.
 *   종목 조회가 실패하면 /.
 */
export type AfterLoginRoute = '/terms' | '/';
export type AfterTermsRoute = '/' | '/onboarding/pick';
export type AfterTermsResult = { ok: true; next: AfterTermsRoute } | { ok: false };

export async function routeAfterLogin(getTerms: () => Promise<{ complete: boolean }>): Promise<AfterLoginRoute> {
  try {
    const terms = await getTerms();
    return terms.complete ? '/' : '/terms';
  } catch {
    return '/';
  }
}

export async function routeAfterTerms(deps: {
  agree: () => Promise<{ complete: boolean }>;
  listMyStocks: () => Promise<readonly unknown[]>;
}): Promise<AfterTermsResult> {
  try {
    const saved = await deps.agree();
    if (!saved.complete) return { ok: false };
  } catch {
    return { ok: false };
  }
  try {
    const mine = await deps.listMyStocks();
    return { ok: true, next: mine.length > 0 ? '/' : '/onboarding/pick' };
  } catch {
    return { ok: true, next: '/' };
  }
}
