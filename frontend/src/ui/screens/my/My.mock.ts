import type { MyProfile, WithdrawProps } from './My.types';

/**
 * MY · 설정 mock 값 — 한 곳에 모음 (원본 app/my.html · web overlays.tsx).
 * 요금제 이름·가격·한도·크레딧·사용량은 팀 확정 전 가안(원본 자리표시 그대로). 서버 값이 생기면 이 파일만 바꾼다.
 */
export const mockMyProfile: MyProfile = { name: '김나라', intro: '대학생', provider: 'kakao', email: 'nara@kakao.example' };

/** AI 사용량 (예시) — 90% 이상이면 주의, 100% 면 중단 안내 */
export const mockMyUsage = { usage_pct: 62, usage_renew: '11.30', plan_name: '무료 플랜' };

/** 지워지는 것 · 데이터 개수 (원본 예시: 메모 8 · 투자 기록 4 · 종목 3 · AI 연결 5) */
export const mockWithdrawCounts: WithdrawProps['counts'] = { memo: 8, journal: 4, stock: 3, ai: 5 };

/** 종목별 추적 현황 (원본 TRK · 11.17 웹 통일: AI 연결된 메모 4개) */
export interface TrackedMemo { title: string; chips: string[] }
export interface TrackedStock { stock_code: string; name: string; logo: string; logo_bg: string; memos: TrackedMemo[] }
export const mockTracked: TrackedStock[] = [
  {
    stock_code: '000660', name: 'SK하이닉스', logo: 'S', logo_bg: '#EA002C',
    memos: [
      { title: '실적 나오면 다시 보기', chips: ['공시·뉴스 · 실적 발표 내용'] },
      { title: '요즘 반도체 분위기 좋아 보여', chips: ['공시·뉴스 · AI 수요'] },
      { title: '15만원 밑으로 오면 다시 생각', chips: ['가격 조건 · 종가 150,000원 이하'] },
    ],
  },
  { stock_code: '005930', name: '삼성전자', logo: '삼', logo_bg: '#1428A0', memos: [] },
  { stock_code: '035420', name: '네이버', logo: '네', logo_bg: '#03C75A', memos: [{ title: 'AI 검색 반응 보기', chips: ['공시·뉴스 · AI 검색 서비스 반응'] }] },
];

/** 플랜 (원본 PL · PLANS) — 가격·한도는 자리표시 */
export interface PlanInfo { key: string; price: string; tag: '' | '현재 플랜' | '추천'; features: string[] }
export const mockPlans: PlanInfo[] = [
  { key: '무료', price: '0원', tag: '현재 플랜', features: ['메모·투자 기록 무제한', 'AI 업데이트 · 기본 사용량', '스튜디오 크레딧 · 매달 기본 제공'] },
  { key: 'PLUS', price: '[가격]', tag: '추천', features: ['무료 플랜의 모든 기능', 'AI 업데이트 · 더 많은 사용량', '스튜디오 크레딧 · 매달 더 많이'] },
  { key: 'PRO', price: '[가격]', tag: '', features: ['PLUS의 모든 기능', 'AI 업데이트 · 가장 많은 사용량', '스튜디오 크레딧 · 매달 가장 많이'] },
];
/** 한눈에 비교 — true 는 ✓ */
export const mockPlanCompare: [string, (string | true)[]][] = [
  ['메모·투자 기록', [true, true, true]],
  ['AI 업데이트 사용량', ['기본', '[미정]', '[미정]']],
  ['스튜디오 크레딧(월)', ['[미정]', '[미정]', '[미정]']],
  ['추가 크레딧 충전', [true, true, true]],
];
export const mockPlanNotes = ['가격·사용량·크레딧은 팀 확정 전 자리표시예요.', '언제든 해지할 수 있고, 해지해도 쓴 기간까지는 그대로 써요.', '투자 권유·수익 보장 기능은 어떤 플랜에도 없어요.'];
export const mockPlanDefault = 'PLUS';

/** 데이터 출처 (원본 정보 화면) */
export const mockDataSources: [string, string][] = [['공시', 'DART'], ['뉴스', '서울경제 · 매일경제 · 한국경제 · 연합뉴스'], ['주가', 'KIS · KRX · ECOS · FRED']];

/**
 * 오픈소스 라이선스 — 원본 웹 목록(React · Vite · Tailwind …)은 원본 시안의 기술이라,
 * 이 앱이 실제로 쓰는 패키지로 바꿈 (frontend/package.json 기준).
 */
export const mockOss: [string, string, string][] = [
  ['React', 'MIT', 'Meta'],
  ['React Native', 'MIT', 'Meta'],
  ['React Native Web', 'MIT', 'Nicolas Gallagher'],
  ['Expo · Expo Router', 'MIT', '650 Industries'],
  ['react-native-svg', 'MIT', 'Software Mansion'],
  ['react-native-safe-area-context', 'MIT', 'Th3rd Wave'],
  ['TanStack Query', 'MIT', 'Tanner Linsley'],
  ['Zustand', 'MIT', 'Poimandres'],
  ['Pretendard', 'OFL-1.1', 'Kil Hyung-jin'],
];
