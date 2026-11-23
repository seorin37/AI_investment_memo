import type { MadeItem, StudioFeatureItem } from './Studio.types';

/**
 * 스튜디오 mock (원본 app/studio.html · web studio.tsx). 사용량·크레딧·갱신일·플랜은 My.mock 에서 읽는다.
 * 실제 결과는 서버가 만들어 돌려줄 값 — 지금은 화면 확인용.
 */
export const mockStudioFeatures: StudioFeatureItem[] = [
  { key: 'audio', title: 'AI 오디오', desc: '바쁠 땐 내 종목 소식을 라디오로' },
  { key: 'report', title: 'AI 주간보고서', desc: '공시 읽기 힘드셨죠? 한 주를 한 장으로' },
  { key: 'lab', title: 'AI 투자 실험실', desc: '금리·환율이 바뀌면 내 종목은?' },
  { key: 'quiz', title: '오늘의 퀴즈', desc: '하루 한 문제 주식 상식 · 무료' },
];

export const mockMade: MadeItem[] = [
  { id: 'm1', kind: 'audio', title: '11.06 내 종목 라디오', sub: '어제 소식과, 그때 내가 남긴 메모', meta: '오디오 · 3종목 · 전날 · 6:42', left: '27일 뒤 삭제', dur: '6:42', foot: '종목 3개 · 전날 기준' },
  { id: 'm2', kind: 'report', title: '10월 다섯째 주 돌아보기', sub: '주간보고서 · 종목 3개', meta: '주간보고서 · 3종목', left: '23일 뒤 삭제', codes: ['000660', '005930', '035420'], market: true },
  { id: 'm3', kind: 'lab', title: '삼성전자 · 환율 하락 실험', sub: '투자 실험실 · 삼성전자', meta: '투자 실험실 · 삼성전자', left: '25일 뒤 삭제', lab: { code: '005930', dirs: ['하락', '유지', '유지', '유지'] } },
];

/** 오디오 만들기 시트 종목 (원본 STK: 이름 · 새 소식 수 · 보유/관심) */
/** news: 기간별 새 소식 수 [전날, 최근 3일, 최근 7일] (앱 시트는 전날 값만 보여 줌) */
export interface AudioStock { stock_code: string; name: string; news: [number, number, number]; hold: '보유' | '관심' }
export const mockAudioStocks: AudioStock[] = [
  { stock_code: '000660', name: 'SK하이닉스', news: [3, 4, 6], hold: '보유' },
  { stock_code: '005930', name: '삼성전자', news: [2, 3, 5], hold: '관심' },
  { stock_code: '035420', name: '네이버', news: [0, 0, 1], hold: '관심' },
];
export const mockAudioPeriods = ['전날', '최근 3일', '최근 7일'] as const;
/** 직전 거래일 (웹 시트 '증시 요약' 아래 줄) */
export const mockLastClose = '11.18(화)';

/** 만들기 단계 · 결과 이름 (원본 GK.audio) */
export const mockAudioGen = {
  steps: ['업데이트 모으기', '두 진행자 대본 쓰기', '목소리 입히기'],
  result_title: '오늘의 내 종목 라디오',
};

/**
 * 오디오 한 편 (원본 09 플레이어 CH · SC). 길이·시각은 초. 실제 소리는 없음 (mock 타이머).
 * 금지 문구 규칙: 매수·매도 권유 · 호재/악재 · 가격 전망 · 장중 · 기대감류 없음, 시세는 'MM.DD 종가 기준'
 */
export const mockAudioEpisode = {
  hosts: ['진행자 A · 메인', '진행자 B · 해설'],
  dur: 402,
  chapters: [[0, '어제 증시 요약'], [28, 'SK하이닉스'], [70, '삼성전자'], [108, '네이버 · 새 소식 없음'], [122, '마무리']] as [number, string][],
  script: [
    [0, 'A', '오늘은 고른 종목 3곳의 소식을 살펴볼게요. 먼저 어제 증시부터요.'],
    [12, 'B', '11.06 종가 기준으로 코스피는 1.2% 올랐고, 원/달러 환율은 조금 내렸어요.'],
    [28, 'A', 'SK하이닉스로 가 볼까요? 전에 HBM 수요 메모를 남기셨는데, 관련 소식이 있다고요?'],
    [44, 'B', '네. 10월 30일 신규 시설투자 공시가 나왔고, 추적 중인 HBM 항목과 연결됐어요.'],
    [58, 'A', '그럼 메모와는 어떤 관계로 보면 될까요?'],
    [63, 'B', '공시에는 투자 대상과 기간이 나와 있어요. 메모의 "HBM 생산 능력" 항목과 같은 주제라 연결했어요.'],
    [70, 'A', '다음은 삼성전자예요.'],
    [76, 'B', '삼성전자는 11월 5일 자기주식 취득 결정 공시가 있었어요. 취득 기간과 수량은 원문에 있어요.'],
    [108, 'A', '네이버는 이번 기간에 새 소식이 없었어요.'],
    [122, 'B', '오늘은 여기까지예요. 판단은 메모와 원문을 보고 직접 해 주세요.'],
  ] as [number, 'A' | 'B', string][],
  sources: [
    { kind: '공시', text: 'SK하이닉스 · 신규 시설투자 · DART · 10.30', memo: '메모 “HBM 수요 계속 확인”와 연결' },
    { kind: '공시', text: '삼성전자 · 자기주식 취득 결정 · DART · 11.05', memo: '' },
    { kind: '뉴스', text: 'HBM4 공급 확대 보도 · 한국경제 · 11.06', memo: '' },
  ],
  market_source: '11.06 코스피·코스닥·원/달러 종가',
  memo_link: {
    head: 'SK하이닉스 · AI 연결',
    title: 'HBM 수요 계속 확인',
    body: '10월 30일 신규 시설투자 공시가 이 메모의 추적 항목 "HBM 생산 능력"과 연결됐어요. 오디오에서는 공시 내용과 메모의 관계를 설명했어요.',
    seek: 51,
    count: '공시 1건',
  },
};

/* ───────── 8c 주간보고서 (원본 app R3 · web ReportSummary/ReportDetail) ─────────
 * 금지 문구 규칙: 가격 변화는 사실(종가·등락률)만, 해석 없음. 주가는 'MM.DD 종가 기준'.
 * 원본의 '기대감'·'강세' 표현과 '숫자는 시안용 예시' 문구는 사실 문장으로 바꾸거나 뺌.
 */
export interface ReportItem { no: number; kind: '공시' | '뉴스'; date: string; title: string; src: string }
export interface ReportStock {
  stock_code: string; name: string; logo: string; logo_bg: string; logo_ink?: string; own: '보유' | '관심';
  /** 카드 위 줄 · 머리 바탕 */
  sc: string; st: string;
  /** 주간 등락률 % · 금요일 종가 · 지난주 종가 · 월~금 종가 */
  pct: number; close: number; prev: number; closes: [number, number, number, number, number];
  /** 차트 세로 범위 */
  yr: [number, number];
  hi: string; lo: string; vol: string;
  /** 차트 위 표시 [요일 칸, 소식 번호, 공시 g | 뉴스 n] */
  events: [number, number, 'g' | 'n'][];
  /** 시트 · 줄 요약 */
  counts: { 공시: number; 뉴스: number };
  story: string;
  items: ReportItem[];
  /** linked_count: 메모 추적 항목에 그 주 붙은 소식 수 (서버 보고서, 없으면 종목 소식 전체 수) */
  memo?: { bg: string; ink: string; title: string; meta: string; body: string; memo_id?: string; linked_count?: number };
  watch: { text: string; why: string }[];
  /** 서버 보고서 (2026-11-23): 이번 주 이슈 정리 7~8문장 (문단은 빈 줄로 나뉨) */
  issues?: string;
  /** PER·PBR·EPS·시가총액·52주 위치 (stock_fundamentals_snapshot) */
  valuation?: { basis: string; per: number | null; pbr: number | null; eps: number | null; market_cap: string; w52_high: number | null; w52_low: number | null; w52_pos: number | null } | null;
  /** 최근 분기 실적 (financials_quarterly, 연결 우선) */
  quarter?: { label: string; basis: string; revenue: string; operating_income: string; net_income: string; revenue_yoy: number | null; op_yoy: number | null } | null;
}
export const mockReportStocks: ReportStock[] = [
  {
    stock_code: '000660', name: 'SK하이닉스', logo: 'S', logo_bg: '#EA002C', own: '보유', sc: '#E5323B', st: '#FFF0F0',
    pct: 6.2, close: 180500, prev: 170000, closes: [170000, 172500, 177800, 179300, 180500], yr: [165000, 185000],
    hi: '182,000', lo: '168,500', vol: '+18%', events: [[1, 1, 'g'], [3, 3, 'n'], [4, 4, 'n']], counts: { 공시: 1, 뉴스: 2 },
    story: '화요일(11.04) 신규 시설투자 공시[1]가 나왔고, 다음 날(11.05) 종가는 전날보다 3.1% 높았어요. 거래량은 이날이 이번 주 가장 많았어요. 목요일에는 HBM4 공급 확대 보도[3]가 있었고, 11.07 종가 기준 180,500원이에요.',
    items: [
      { no: 1, kind: '공시', date: '11.04', title: '신규 시설투자 결정', src: 'DART' },
      { no: 3, kind: '뉴스', date: '11.06', title: 'HBM4 공급 확대 보도', src: '한국경제' },
      { no: 4, kind: '뉴스', date: '11.07', title: '반도체 장비 발주 증가', src: '매일경제' },
    ],
    memo: { bg: '#FCEAAA', ink: '#3F3A2A', title: 'HBM 수요 계속 확인', meta: '9.25 작성 · AI 연결 중', body: "메모의 추적 항목 'HBM 생산 능력'과 관련된 소식 2건([1], [3])이 이번 주에 붙었어요." },
    watch: [
      { text: '11월 말 분기보고서에 HBM 매출이 따로 나오는지', why: '정기 공시 일정' },
      { text: '메모의 가격 조건 15만 원과 11.07 종가의 차이 (20.3% 위)', why: '내 메모 가격 조건' },
    ],
  },
  {
    stock_code: '005930', name: '삼성전자', logo: '삼', logo_bg: '#1428A0', own: '관심', sc: '#1428A0', st: '#EEF1FB',
    pct: 1.4, close: 71400, prev: 70400, closes: [70400, 69800, 71900, 72000, 71400], yr: [69000, 73000],
    hi: '72,100', lo: '69,800', vol: '-4%', events: [[2, 2, 'g']], counts: { 공시: 1, 뉴스: 0 },
    story: '수요일(11.05) 자기주식 취득 결정 공시[2]가 나온 날 종가는 전날보다 3.0% 높았어요. 11.07 종가 기준 71,400원이고, 거래량은 지난주보다 4% 적었어요.',
    items: [{ no: 2, kind: '공시', date: '11.05', title: '자기주식 취득 결정', src: 'DART' }],
    memo: { bg: '#D9E4FF', ink: '#1E2A4A', title: '자사주 매입 나오면 다시 보기', meta: '10.02 작성 · AI 연결 꺼짐', body: '메모에 적어 둔 자사주 매입이 이번 주 공시[2]로 나왔어요.' },
    watch: [{ text: '취득 기간 동안 나오는 자기주식 취득 결과 보고', why: '이번 주 공시[2]의 취득 기간 · 추가하면 AI 연결도 켜져요' }],
  },
  {
    stock_code: '035420', name: '네이버', logo: '네', logo_bg: '#03C75A', own: '관심', sc: '#03C75A', st: '#EDFAF2',
    pct: -0.8, close: 212300, prev: 214000, closes: [214000, 216000, 213800, 212000, 212300], yr: [210000, 218000],
    hi: '216,000', lo: '211,500', vol: '-9%', events: [], counts: { 공시: 0, 뉴스: 0 },
    story: '이번 주 새 공시·뉴스는 없었어요. 화요일(11.04) 종가 216,000원이 이번 주 가장 높았고, 11.07 종가 기준 212,300원이에요.',
    items: [],
    watch: [{ text: '다음 주 새 공시·뉴스가 나오는지', why: '이번 주 소식 0건 · 추가하면 새 메모로 남겨요' }],
  },
];
export const mockReport = {
  week: '2026년 11월 2주',
  title: '11월 2주 주간 보고서',
  range: '11.03(월) ~ 11.07(금)',
  period: '최근 7일 · 11.03 ~ 11.09 (거래일 5일)',
  web_period: '최근 5거래일(11.03 – 11.07) 보고서에 넣을 종목',
  made_at: '11.09 14:02',
  /** 만드는 중 화면 조건 줄 */
  gen_range: '11.03~11.09',
  made_label: '11.09',
  days: ['11.03 월', '11.04 화', '11.05 수', '11.06 목', '11.07 금'],
  days_short: ['월', '화', '수', '목', '금'],
  market: [
    { name: '코스피', value: '2,650.35', pct: 2.0 },
    { name: '코스닥', value: '862.10', pct: 0.6 },
    { name: '원/달러', value: '1,350.20', pct: -1.6 },
  ],
  flow: [
    { day: '11.04 화', text: '미국 반도체 지수 상승 다음 날 국내 반도체주도 상승 마감', src: '[5]' },
    { day: '11.05 수', text: '외국인, 사흘 연속 코스피 순매수', src: '[6]' },
    { day: '11.07 금', text: '원/달러 환율 1,350원대로 하락', src: '[7]' },
  ],
  /** 서버 보고서: 국내 증시 시황 정리 7~8문장 (mock 은 비움) */
  market_summary: '',
  /** 기본 3종목일 때 '이번 주 한눈에' (다른 조합은 화면에서 숫자로 만듦) */
  summary_default: '내 종목 3곳 중 2곳이 올랐어요. SK하이닉스는 화요일 신규 시설투자 공시[1]가 나왔고 한 주 동안 6.2% 올라 가장 크게 움직였어요. 삼성전자는 메모에 적어 둔 자기주식 취득 공시[2]가 나왔어요. 네이버는 새 공시·뉴스 없이 0.8% 내렸어요.',
  sources: [
    { text: '[1] DART · SK하이닉스 신규시설투자 · 2026.11.04', code: '000660' },
    { text: '[2] DART · 삼성전자 자기주식취득결정 · 2026.11.05', code: '005930' },
    { text: '[3] 한국경제 · HBM4 공급 확대 보도 · 2026.11.06', code: '000660' },
    { text: '[4] 매일경제 · 반도체 장비 발주 증가 · 2026.11.07', code: '000660' },
    { text: '[5] 연합뉴스 · 국내 반도체주 상승 마감 · 2026.11.04', code: '' },
    { text: '[6] 연합뉴스 · 외국인 코스피 순매수 · 2026.11.05', code: '' },
    { text: '[7] 연합뉴스 · 원/달러 환율 하락 · 2026.11.07', code: '' },
  ],
  source_note: '시세는 KIS, 공시는 DART 원문을 바탕으로 정리했어요. 뉴스는 제목·언론사·날짜만 쓰고 원문 링크로 연결해요.',
  steps: ['시세·공시·재무 모으기', '종목별 분석 쓰기', '보고서 정리 · 출처 달기'],
  /** 웹 만드는 중 단계 (원본 studio.tsx STEPS.report) */
  web_steps: ['업데이트 모으기', '종목별 흐름 정리하기', '보고서 다듬기'],
};

/* ───────── 8d 오늘의 퀴즈 (원본 app pgQz · web Quiz) ─────────
 * 사실 확인형만 (시장 데이터 · 공시 · 용어). '오를 종목'·'살 때' 같은 판단형 문제 없음. 원본 '화면 예시' 표기는 뺌
 */
export const mockQuiz = {
  label: '어제(11.06 금) 증시 퀴즈',
  day: '11.06',
  type: '4지선다',
  q: '어제 코스피에서 거래대금이\n가장 많았던 종목은?',
  options: ['삼성전자', 'SK하이닉스', '현대차', 'LG에너지솔루션'],
  answer: 1,
  exp: 'SK하이닉스가 약 2조 1,000억 원으로 거래대금 1위였어요.',
  concept: '거래대금은 거래량에 가격을 곱한 값이라, 비싼 종목이 많이 거래될수록 커져요.',
  src: '출처 · 한국거래소 (11.06 기준)',
  streak: 3,
  /** 이번 주 참여 [월~일] 1 참여 · 0 안 함 · 2 오늘 · 3 아직 */
  week: [['월', 1], ['화', 0], ['수', 1], ['목', 1], ['금', 1], ['오늘', 2], ['일', 3]] as [string, number][],
};

/* ───────── 8d 투자 실험실 (원본 app pgLab/pgLr · web Lab/LabResultBody) ─────────
 * 가정에 따른 '영향 경로'만 보여 줌 (실적·주가 예측 아님). 원본 '원화 강세/약세'는 '원화 가치 상승/하락'으로,
 * '(예시)'·'약 ○○억 원' 같은 자리표시는 뺌. 원본 웹의 '종합 방향 · 긍정/부정'은 해석이라 넣지 않음
 */
export type LabDir = '상승' | '유지' | '하락';
export const mockLabDirs: LabDir[] = ['상승', '유지', '하락'];
export const mockLabVars = [
  { name: '원/달러 환율', now: '11.18 종가 기준 1,350.20원', def: '하락' as LabDir, mid: '원화 가치\n변화' },
  { name: '국제유가(WTI)', now: '11.18 기준 배럴당 71.2달러', def: '유지' as LabDir, mid: '원가·물류비\n변화' },
  { name: '한국 기준금리', now: '현재 2.50%', def: '유지' as LabDir, mid: '국내 금리\n변화' },
  { name: '미국 10년물 국채금리', now: '11.18 기준 4.32%', def: '상승' as LabDir, mid: '장기금리\n변화' },
];
export const mockLabNote = '지금은 환율·유가·기준금리·미국 10년물 금리 4가지만 바꿀 수 있어요. 실제 주가는 이 밖의 많은 요인으로 움직여요. 예측이 아니라 영향 경로만 보여 드려요.';
/** 경로 끝 항목 — t 제목 · ev 공시 근거 있음 · why 설명 · base 근거 줄 · note 함께 볼 점 · check 확인할 것 · check_why */
export interface LabLeaf { t: string; ev: boolean; why: string; base: string; note?: string; check?: string; check_why?: string }
const fxLeaves = (strong: boolean): LabLeaf[] => [
  strong
    ? { t: '달러 매출의 원화 환산액', ev: true, why: '매출 대부분이 달러로 들어와, 환율이 바뀌면 원화로 바꾼 매출 금액도 달라질 수 있어요.', base: '2025 사업보고서 · 환율 변동 시 세전이익 민감도 공시', note: '판매 가격과 물량이 함께 바뀌면 환율 효과만 따로 떼어 보기 어려워요.', check: '다음 분기보고서의 환율 영향 설명', check_why: '공시 민감도의 최신 값' }
    : { t: '달러 매출의 원화 환산액', ev: false, why: '해외 매출 비중이 크지 않아 이 경로의 영향은 제한적일 수 있어요.', base: '일반적인 경로 · 회사 공시 없음', note: '판매 가격과 물량이 함께 바뀌면 환율 효과만 따로 떼어 보기 어려워요.', check: '해외 매출 비중', check_why: '사업보고서 지역별 매출' },
  { t: '달러로 사는 원가·장비', ev: false, why: '장비·원재료를 달러로 사는 만큼 원화 비용도 함께 달라져, 앞 항목과 일부 상쇄될 수 있어요.', base: '일반적인 경로 · 달러 매입 비중은 공시로 확인이 필요해요', check: '달러로 사는 원가·장비 비중', check_why: '상쇄 정도를 가늠하려면 필요해요' },
];
/** 변수 칸 i · 종목(달러 매출 비중이 큰 종목이면 fxStrong) → 경로 끝 항목 */
export const mockLabLeaves = (i: number, fxStrong: boolean): LabLeaf[] =>
  i === 0 ? fxLeaves(fxStrong)
    : i === 1 ? [{ t: '원재료·물류 비용', ev: false, why: '유가가 바뀌면 원재료와 운송에 드는 비용이 따라 움직일 수 있어요.', base: '일반적인 경로 · 회사 공시 없음', note: '계약 방식에 따라 비용에 반영되는 시점이 늦을 수 있어요.', check: '원가에서 에너지·물류가 차지하는 비중', check_why: '사업보고서 원가 항목' }]
      : i === 2 ? [{ t: '차입 이자 비용', ev: false, why: '기준금리가 바뀌면 국내에서 빌린 돈의 이자 부담도 달라질 수 있어요.', base: '일반적인 경로 · 회사 공시 없음', note: '고정금리 차입이 많으면 체감이 늦어요.', check: '차입금 만기와 금리 구조', check_why: '사업보고서 차입금 주석' }]
        : [
          { t: '설비투자 자금 조달', ev: false, why: '장기금리가 바뀌면 새로 빌리는 돈의 이자 조건도 달라질 수 있어요.', base: '일반적인 경로 · 회사 공시 없음', note: '현금 보유와 차입 구조에 따라 체감 정도가 달라요.', check: '설비투자 계획과 자금 조달 공시', check_why: '차입 구조 확인' },
          { t: '주식 가치 평가의 할인율', ev: false, why: '장기금리는 미래 이익을 지금 가치로 바꿀 때 쓰는 할인율에 반영되곤 해요.', base: '일반적인 경로 · 이론', note: '실제 주가는 이것 말고도 많은 요인으로 움직여요.' },
        ];
/** 실험 종목 (내 종목) · 달러 매출 비중 큰 종목 · 연결 메모 */
export const mockLabStocks = [
  { stock_code: '000660', name: 'SK하이닉스', logo: 'S', logo_bg: '#EA002C', hold: '보유' as const, fx_strong: true, memo: 'HBM 점유율 유지되는지 계속 보기', memo_text: '이번 실험의 ①은 실적 숫자에 닿는 경로예요. 메모에서 중요하게 본 HBM 수요·점유율과는 다른 요인이라, 둘을 나눠서 보면 좋아요.' },
  { stock_code: '005930', name: '삼성전자', logo: '삼', logo_bg: '#1428A0', hold: '관심' as const, fx_strong: true, memo: '자사주 매입 나오면 다시 보기', memo_text: '이번 실험의 경로는 메모에서 중요하게 본 요인과 다른 쪽이에요. 메모의 조건과 나눠서 보면 좋아요.' },
  { stock_code: '035420', name: '네이버', logo: '네', logo_bg: '#03C75A', hold: '관심' as const, fx_strong: false, memo: '', memo_text: '' },
];
export const mockLabDisclaimer = 'AI가 가정을 바탕으로 정리한 결과예요. 실제와 다를 수 있으니 공시와 함께 확인해 주세요.';

/** 웹 스튜디오 머리 (내 종목 N · AI 연결 메모 N) */
export const mockStudioCounts = { stock_count: 3, ai_memo_count: 5 };
