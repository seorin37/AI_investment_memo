/**
 * 사용법 안내(웹) 단계별로 갈 곳 (2026-11-22). 순수 함수 — tests/coach-target.test.mjs
 * - mock 모드: 지금처럼 SK하이닉스(000660) 보드 (mock 보드에 예시 메모 m1 이 있음)
 * - 실제 모드: 내 첫 종목(사이드바 · GET /stocks 순서 = position 첫 번째) 보드. 내 종목이 없으면 홈에 머묾 → 대상이 없어 가운데 카드
 * 단계: -1 첫 카드 · 끝(null) = 홈 / 0 ① + 버튼 · 1 ② 새 메모 창 AI 칸 · 2 ③ 메모 창 소식 = 보드 / 3 ④ = 홈 + 스튜디오 열
 */
export const MOCK_COACH_CODE = '000660';

export type CoachPlace = { kind: 'home' } | { kind: 'board'; code: string } | { kind: 'studio' };

export function coachBoardCode(real: boolean, myCodes: readonly string[]): string | null {
  if (!real) return MOCK_COACH_CODE;
  return myCodes[0] ?? null;
}

/**
 * 실제 모드에서 메모 단계(웹 ③ · 앱 ②③)에 실제 AI 메모 창을 열 수 있게 되면 true.
 * 지금은 웹 보드((main)/stocks/[code].tsx)가 ③에서 mock 'm1' 을, 앱 CoachDriver 가 /memo/m1 을 열어
 * 실제 모드에서는 빈 화면 → 예시 메모를 대신 보여 준다. B 수정 뒤 실제 메모를 열면 이 값을 true 로 (또는 메모가 있을 때만 true)
 */
export const REAL_COACH_MEMO_READY = false;

/** 사용법 안내 메모 단계에서 예시 메모 창을 띄울지 — mock 모드는 늘 실제(mock m1) 창이라 false */
export function coachExample(step: number | null, real: boolean, web: boolean, realMemoReady: boolean = REAL_COACH_MEMO_READY): boolean {
  if (!real || realMemoReady || step == null) return false;
  return web ? step === 2 : step === 1 || step === 2;
}

export function coachPlace(step: number | null, real: boolean, myCodes: readonly string[]): CoachPlace {
  if (step == null || step < 0) return { kind: 'home' };
  if (step >= 3) return { kind: 'studio' };
  const code = coachBoardCode(real, myCodes);
  return code ? { kind: 'board', code } : { kind: 'home' };
}
