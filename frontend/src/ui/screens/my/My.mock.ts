import type { MyProfile, WithdrawProps } from './My.types';

/** 원본 my.html · overlays.tsx 예시 값 (사용량·한도는 팀 확정 전 예시) */
export const mockMyProfile: MyProfile = { name: '김나라', intro: '대학생', provider: 'kakao', email: 'nara@kakao.example' };
export const mockMyUsage = { usage_pct: 62, usage_renew: '11.30' };
export const mockMyVersion = "memo's v0.1.0 (베타)";
/** 웹 회원 탈퇴 창의 지워지는 것 (원본은 store 개수 · 여기선 웹 mock 과 같은 예시) */
export const mockWithdrawCounts: WithdrawProps['counts'] = { memo: 8, journal: 4, stock: 3, ai: 5 };
