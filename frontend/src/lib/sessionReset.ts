/**
 * 로그아웃 · 계정 전환 때 사용자별 상태 비우기 (2026-11-22). 순수 모듈 — tests/session-reset.test.mjs
 * (react-native · SecureStore · '@/' 별칭을 쓰지 않는다: node 테스트에서 바로 불러오려고)
 */

/** react-query QueryClient 중 여기서 쓰는 부분 */
export interface ClearableCache {
  clear(): void;
}

export interface ResetDeps {
  queryClient: ClearableCache;
  /** store 마다 '처음 만들어졌을 때 상태'로 되돌리는 함수 */
  resets: readonly (() => void)[];
}

/**
 * 캐시를 한 번 비우고 reset 을 전부 부른다. 하나가 throw 해도 나머지는 계속 부른다.
 * 실패한 것의 오류 목록을 돌려준다 (부른 쪽은 로그아웃을 막지 않는다).
 */
export function resetUserState({ queryClient, resets }: ResetDeps): unknown[] {
  const errors: unknown[] = [];
  try {
    queryClient.clear();
  } catch (e) {
    errors.push(e);
  }
  for (const reset of resets) {
    try {
      reset();
    } catch (e) {
      errors.push(e);
    }
  }
  return errors;
}

/** 마지막으로 본 사용자와 다른 사용자(또는 로그아웃 = null)가 오면 비운다. 처음 로그인(마지막 = null)은 비우지 않는다 */
export function shouldReset(lastUserId: string | null, nextUserId: string | null): boolean {
  return lastUserId != null && lastUserId !== nextUserId;
}

/**
 * 마지막 사용자 id 를 들고 있는 작은 추적기 (store/auth.ts 가 씀).
 * - switchUser(id): 새 사용자를 set 하기 전에 부름. 다른 사용자거나 세션이 끝났으면(null) 먼저 비움
 * - signOut(): 늘 비우고 마지막 id = null
 */
export function createSessionTracker(deps: ResetDeps) {
  let last: string | null = null;
  return {
    switchUser(nextUserId: string | null) {
      if (shouldReset(last, nextUserId)) resetUserState(deps);
      last = nextUserId;
    },
    signOut() {
      resetUserState(deps);
      last = null;
    },
    lastUserId: () => last,
  };
}
