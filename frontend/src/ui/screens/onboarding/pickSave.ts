/**
 * 온보딩 종목 고르기 — 저장 · 목록 판단 (2026-11-22). 순수 함수: tests/onboarding-pick.test.mjs
 * ('@/' 별칭 · react-native 를 쓰지 않는다: node 테스트에서 바로 불러오려고)
 */
import type { OnboardingSelection, OnboardingStock, StockStatus } from './Onboarding.types';

/** 이미 담긴 종목 응답(서버가 409 를 주는 경우 대비) — 성공으로 본다. 지금 POST /stocks 는 이미 있으면 상태만 바꾸고 200 */
function alreadyAdded(err: unknown): boolean {
  return !!err && typeof err === 'object' && 'status' in err && (err as { status: unknown }).status === 409;
}

/**
 * 고른 종목을 차례대로 담는다 (POST /stocks · 한 번에 하나). 실패한 종목만 돌려준다 (선택 상태 그대로).
 * 전부 성공 → failed 비어 있음.
 */
export async function addSelectedStocks(
  selected: OnboardingSelection,
  add: (code: string, status: StockStatus) => Promise<unknown>,
): Promise<{ failed: OnboardingSelection; added: string[] }> {
  const failed: OnboardingSelection = {};
  const added: string[] = [];
  for (const [code, status] of Object.entries(selected)) {
    try {
      await add(code, status);
      added.push(code);
    } catch (err) {
      if (alreadyAdded(err)) added.push(code);
      else failed[code] = status;
    }
  }
  return { failed, added };
}

/**
 * 화면 목록 = 지금 목록(많이 찾는 종목 · 검색 결과) + 고른 종목 중 목록에 없는 것.
 * 보유·관심 확인 · 'N개 선택'이 목록 안의 종목만 세므로, 검색어를 바꿔도 고른 종목이 빠지지 않게 한다.
 */
export function withSelectedStocks(
  list: readonly OnboardingStock[],
  known: Readonly<Record<string, OnboardingStock>>,
  selected: OnboardingSelection,
): OnboardingStock[] {
  const out = [...list];
  const have = new Set(list.map((s) => s.stock_code));
  for (const code of Object.keys(selected)) {
    if (!have.has(code) && known[code]) {
      out.push(known[code]);
      have.add(code);
    }
  }
  return out;
}
