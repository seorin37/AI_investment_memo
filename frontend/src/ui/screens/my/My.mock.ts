import type { MyProfile, WithdrawProps } from './My.types';

/**
 * MY · 설정 mock 값 — 한 곳에 모음 (원본 app/my.html · web overlays.tsx).
 * 요금제 이름·가격·한도·크레딧·사용량은 팀 확정 전 가안(원본 자리표시 그대로). 서버 값이 생기면 이 파일만 바꾼다.
 */
export const mockMyProfile: MyProfile = { name: '김나라', intro: '대학생', provider: 'kakao', email: 'nara@kakao.example' };

/** AI 사용량 (예시) — 90% 이상이면 주의, 100% 면 중단 안내 */
export const mockMyUsage = { usage_pct: 62, usage_renew: '11.30', usage_refill: '12월 1일', plan_name: '무료 플랜' };

/** 크레딧 충전 상품 (원본 studio.html pgCg · web ChargePopup) — 가격은 팀 확정 전이라 원본 자리표시 그대로 */
export interface CreditPack { credits: number; label: string; price: string; tag?: string }
export const mockCreditPacks: CreditPack[] = [
  { credits: 100, label: '100 크레딧', price: '[가격]' },
  { credits: 300, label: '300 크레딧', price: '[가격]', tag: '많이 쓰는 분께' },
  { credits: 1000, label: '1,000 크레딧', price: '[가격]' },
];
export const mockCreditDefault = 300;
/** 웹 충전 창 결제 수단 (원본 ChargePopup) */
export const mockPayMethods = ['카드', '간편결제', '계좌이체'];

/** 지워지는 것 · 데이터 개수 (원본 예시: 메모 8 · 투자 기록 4 · 종목 3 · AI 연결 5) */
export const mockWithdrawCounts: WithdrawProps['counts'] = { memo: 8, journal: 4, stock: 3, ai: 5 };

/** 종목별 추적 현황 (원본 TRK · 11.17 웹 통일: AI 연결된 메모 4개) */
export interface TrackedMemo { title: string; chips: string[]; /** 실제 모드: 메모 id (GET /ai/tracking) */ memo_id?: string }
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
/** first: 첫 달 가격 문구 ('첫 달 7,450원') · 2026-11-25 GET /plans 로 채움 (planView.ts) */
export interface PlanInfo { key: string; price: string; tag: '' | '현재 플랜' | '추천'; features: string[]; first?: string; /** 첫 달 할인가 '7,450원' · 할인율 50 (2026-11-25 강조 표시) */ first_price?: string; first_pct?: number }
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
export const mockPlanNotes = ['언제든 해지할 수 있고, 해지해도 쓴 기간까지는 그대로 써요.', '투자 권유·수익 보장 기능은 어떤 플랜에도 없어요.'];
export const mockPlanDefault = 'PLUS';

/* ---------- ⑨-3c ---------- */

/** 휴지통 (원본 my.html TR · 11.17 웹 통일: 웹 휴지통과 같은 4개) */
export interface TrashItem { id: string; kind: '메모' | '투자 기록' | '종목' | '스튜디오'; title: string; /** 어느 종목 · 무엇 */ sub: string; ago: string; stock_code?: string }
export const mockTrash: TrashItem[] = [
  { id: 't1', kind: '메모', title: '20만원 밑으로 오면 다시 생각', sub: 'SK하이닉스 · 메모', ago: '2시간 전', stock_code: '000660' },
  { id: 't2', kind: '투자 기록', title: '10/08 실적 발표 전 점검', sub: '투자 기록', ago: '어제' },
  { id: 't3', kind: '메모', title: '삼성전자랑 같이 비교해보기', sub: 'SK하이닉스 · 메모', ago: '3일 전', stock_code: '000660' },
  { id: 't4', kind: '종목', title: '현대차', sub: '종목', ago: '6일 전', stock_code: '005380' },
];

/**
 * 알림함 (원본 my.html INB · web x.tsx InboxPanel — 같은 5개, 앞의 3개 안 읽음).
 * 문구 규칙: 권유·호재/악재·전망 없음, 주가는 'MM.DD 종가 기준' (원본 '전일 확정 종가 기준'을 바꿈)
 */
/** day '이전' = 그저께보다 오래된 것 (실제 모드 알림함, useInboxData). memo_id: 누르면 그 메모를 열 때 씀 */
export interface InboxItem { id: string; kind: 'ai' | 'studio'; day: '오늘' | '어제' | '이전'; title: string; sub: string; when: string; stock_code?: string; memo_id?: string }
export const mockInbox: InboxItem[] = [
  { id: 'n1', kind: 'ai', day: '오늘', title: 'SK하이닉스 · 실적 나오면 다시 보기', sub: '메모에 새 소식이 연결됐어요 · HBM4 공급 확대', when: '10분 전', stock_code: '000660' },
  { id: 'n2', kind: 'studio', day: '오늘', title: '내 종목 라디오가 다 만들어졌어요', sub: '오디오 · 6:42 · 눌러서 듣기', when: '1시간 전' },
  { id: 'n3', kind: 'ai', day: '오늘', title: 'SK하이닉스 · 15만원 밑으로 오면 다시 생각', sub: '가격 조건 소식이 연결됐어요 · 11.18 종가 기준', when: '장 마감 후', stock_code: '000660' },
  { id: 'n4', kind: 'ai', day: '어제', title: '삼성전자 · 자사주 매입 나오면 다시 보기', sub: '메모에 새 공시가 연결됐어요 · 자기주식 취득 결정', when: '어제', stock_code: '005930' },
  { id: 'n5', kind: 'studio', day: '어제', title: '이번 주 내 종목 보고서가 다 만들어졌어요', sub: '주간보고서 · 3종목', when: '11.02' },
];
export const mockInboxUnread = ['n1', 'n2', 'n3'];

/** 피드백 · 오류 신고 (원본 my.html openFb · web Feedback) */
export const mockReportKinds = ['기능 작동 오류', '화면·표시 오류', '데이터·연결 오류', '속도·접속 문제', '기타'];
export const mockStarLabels = ['별점을 선택해 주세요', '아쉬워요', '조금 아쉬워요', '보통이에요', '좋아요', '아주 좋아요'];

/** 도움말 자주 묻는 질문 (원본 web overlays.tsx FAQ) */
export const mockFaq: [string, string][] = [
  ['메모는 어떻게 쓰나요?', '사이드바에서 종목을 고르고 보드 오른쪽 아래 + 를 눌러요. 첫 줄은 제목이 되고, 나머지는 본문이에요. 메모 색은 보기 칸과 같은 색으로 저장돼요.'],
  ['AI 연결을 켜면 무엇이 달라지나요?', "메모에서 확인할 항목(실적, 배당, 가격 조건 등)을 찾아 그와 관련된 공시·뉴스·종가 변화만 메모 아래 'AI 업데이트'에 모아 드려요. 켤 때 최근 7거래일 소식도 함께 찾아봐요."],
  ['가격 조건은 언제 알려 주나요?', "'15만원 밑이면' 처럼 적으면 장이 끝난 뒤 확정된 종가로 계산해요. 조건에 가까워지거나 닿으면 소식으로 붙여 드려요. 실시간 알림은 아니에요."],
  ['체크리스트는 어디에 저장되나요?', '종목마다 하나씩 보드 맨 위에 있어요. 홈의 체크리스트 위젯에서도 종목을 골라 바로 체크할 수 있어요. 항목을 모두 지우고 저장하면 휴지통으로 옮겨져요.'],
  ['스튜디오 결과는 얼마나 보관되나요?', "오디오·주간보고서·실험 결과는 만든 날부터 30일 동안 '만든 항목'에서 다시 볼 수 있어요. 다시 보기는 사용량을 쓰지 않아요."],
  ['지운 메모를 되살릴 수 있나요?', '사이드바 휴지통에서 복원할 수 있어요. 종목을 빼도 그 종목의 메모는 남아 있다가, 종목을 다시 추가하면 함께 돌아와요.'],
  ['투자 권유를 하나요?', "아니요. MEMO'S는 공시·뉴스·시세를 모아 보여 줄 뿐 매수·매도를 권하거나 주가를 예측하지 않아요."],
];

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
