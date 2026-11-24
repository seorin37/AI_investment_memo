import type { TodayQuiz } from '@/types/models';
import type { mockQuiz } from './Studio.mock';

/**
 * 오늘의 퀴즈 문제 은행 (2026-11-22) — 상규 님 시연용 주식 상식 30문제(data/seed/quiz/quiz_questions_demo.jsonl, demo_order 순).
 * 실제 모드는 DB(quiz_questions, 0023)의 문제를 GET /quiz/today 로 읽고(useTodayQuiz), 이 목록은 mock 모드와
 * 서버에 문제가 없거나 못 읽을 때 대신 쓴다. 날짜와 상관없는 상식이라 '어제 증시' 문구 없음.
 * 바꿀 때는 jsonl 을 고치고 이 파일과 시드 SQL 을 다시 만든다 (scripts/build_quiz_seed.py 와 같은 원본).
 */
export interface QuizItem {
  slug: string;
  /** 머리 칩: 차트 기초 · 거래 기초 · 재무 기초 · 공시 기초 */
  label: string;
  type: '4지선다' | 'OX';
  q: string;
  options: string[];
  answer: number;
  exp: string;
  concept: string;
  src: string;
}

export const QUIZ_BANK: QuizItem[] = [
  { slug: "chart_bullish_candle", label: "차트 기초", type: "4지선다", q: "국내 증권 앱에서 빨간색 캔들(양봉)은 무엇을 뜻할까요?", options: ["종가가 시가보다 높게 끝났다", "외국인이 주식을 샀다", "거래량이 평소보다 많았다", "종가가 시가보다 낮게 끝났다"], answer: 0, exp: "양봉은 시작 가격보다 끝 가격이 높을 때 그려져요. 국내 앱은 보통 양봉을 빨간색, 음봉을 파란색으로 보여 줘요.", concept: "캔들 하나에는 시가·고가·저가·종가가 모두 담겨 있어요.", src: "투자 기초 상식" },
  { slug: "trd_ask_price", label: "거래 기초", type: "4지선다", q: "호가창의 매도호가는 무엇일까요?", options: ["팔려는 사람들이 내놓은 가격과 수량", "증권사가 정한 추천 가격", "어제 마지막으로 거래된 가격", "사려는 사람들이 내놓은 가격과 수량"], answer: 0, exp: "매도호가는 팔겠다는 주문, 매수호가는 사겠다는 주문이에요. 두 가격이 맞으면 거래가 이뤄져요.", concept: "호가창을 보면 지금 어떤 가격에 주문이 쌓여 있는지 알 수 있어요.", src: "투자 기초 상식" },
  { slug: "fin_roe_from_per_pbr", label: "재무 기초", type: "4지선다", q: "PER이 10배, PBR이 2배인 기업의 ROE는 약 얼마일까요?", options: ["12%", "20%", "50%", "5%"], answer: 1, exp: "ROE는 PBR을 PER로 나눈 값과 같아서 2 ÷ 10 = 20%예요.", concept: "PBR = PER × ROE 관계를 알면 세 지표를 함께 읽을 수 있어요.", src: "투자 기초 상식" },
  { slug: "dis_periodic", label: "공시 기초", type: "4지선다", q: "상장사의 정기보고서는 1년에 몇 번 나올까요?", options: ["4번", "2번", "1번", "12번"], answer: 0, exp: "사업보고서 1번, 반기보고서 1번, 분기보고서 2번으로 1년에 4번이에요.", concept: "정기보고서는 회사의 사업과 재무 상태를 정해진 시기마다 알리는 공시예요.", src: "투자 기초 상식" },
  { slug: "chart_upper_wick", label: "차트 기초", type: "4지선다", q: "캔들의 위꼬리 끝은 무엇을 나타낼까요?", options: ["그 기간의 종가", "그 기간의 고가", "그 기간의 시가", "전날 종가"], answer: 1, exp: "위꼬리 끝은 고가, 아래꼬리 끝은 저가예요. 몸통은 시가와 종가 사이를 나타내요.", concept: "위꼬리가 길면 장중에 올랐던 가격이 다시 밀렸다는 뜻이에요.", src: "투자 기초 상식" },
  { slug: "trd_market_order", label: "거래 기초", type: "4지선다", q: "시장가 주문의 특징은 무엇일까요?", options: ["다음 거래일 시가로만 체결된다", "내가 정한 가격에만 체결된다", "장이 끝난 뒤 종가로만 체결된다", "가격을 정하지 않고 지금 나와 있는 호가로 체결된다"], answer: 3, exp: "시장가 주문은 빨리 체결되는 대신 가격을 정하지 않아요. 거래가 적은 종목은 예상보다 불리한 가격에 체결될 수 있어요.", concept: "빠른 체결이 중요하면 시장가, 가격이 중요하면 지정가를 써요.", src: "투자 기초 상식" },
  { slug: "fin_dilution", label: "재무 기초", type: "4지선다", q: "1,000만 주 회사의 지분 10%를 가진 주주가 250만 주 유상증자에 불참하면 지분율은?", options: ["7.5%", "12.5%", "8%", "10%"], answer: 2, exp: "보유 100만 주는 그대로인데 전체가 1,250만 주가 되어 100 ÷ 1,250 = 8%예요.", concept: "새 주식이 늘어 기존 주주의 몫이 줄어드는 것을 희석이라고 해요.", src: "투자 기초 상식" },
  { slug: "dis_provisional", label: "공시 기초", type: "4지선다", q: "'영업(잠정)실적' 공시의 특징은 무엇일까요?", options: ["감사가 끝난 확정 실적이다", "증권사가 낸 실적 예상치다", "다음 해 목표 실적이다", "정식 보고서 전에 알리는 숫자라 나중에 달라질 수 있다"], answer: 3, exp: "잠정실적은 감사나 검토가 끝나기 전의 숫자라 정식 보고서에서 달라질 수 있어요.", concept: "실적 발표 시즌에 가장 먼저 확인하게 되는 공시예요.", src: "투자 기초 상식" },
  { slug: "chart_ma20", label: "차트 기초", type: "4지선다", q: "20일 이동평균선은 어떻게 만들까요?", options: ["20일 동안의 최고가를 이은 선", "최근 20거래일 종가의 평균을 이은 선", "20일 동안의 거래량을 더한 선", "20일 뒤 예상 가격을 이은 선"], answer: 1, exp: "이동평균선은 정해진 기간의 종가 평균을 날마다 다시 계산해 이은 선이에요.", concept: "기간이 짧을수록 주가에 민감하고, 길수록 큰 흐름을 보여 줘요.", src: "투자 기초 상식" },
  { slug: "trd_limit_order", label: "거래 기초", type: "4지선다", q: "지정가 주문의 특징은 무엇일까요?", options: ["항상 바로 체결된다", "정한 가격이나 그보다 유리한 가격에서만 체결된다", "가장 불리한 가격으로 체결된다", "하루가 지나면 시장가로 바뀐다"], answer: 1, exp: "지정가 주문은 원하는 가격을 정해 두는 주문이에요. 그 가격까지 오지 않으면 체결되지 않을 수 있어요.", concept: "주문을 넣은 것과 체결된 것은 달라요.", src: "투자 기초 상식" },
  { slug: "fin_retire_eps", label: "재무 기초", type: "4지선다", q: "순이익 100억 원, 1,000만 주 회사가 200만 주를 소각하면 EPS는?", options: ["800원", "1,000원", "1,250원", "1,200원"], answer: 2, exp: "주식이 800만 주로 줄어 100억 원 ÷ 800만 주 = 1,250원이에요. 이익이 같아도 1주 몫은 커져요.", concept: "EPS는 순이익을 주식 수로 나눈 값이에요.", src: "투자 기초 상식" },
  { slug: "dis_correction", label: "공시 기초", type: "4지선다", q: "공시 제목 앞의 [기재정정]은 무슨 뜻일까요?", options: ["이미 낸 공시의 내용을 고쳐 다시 냈다", "공시가 취소됐다", "실적이 시장 예상을 넘었다", "거래가 정지됐다"], answer: 0, exp: "기재정정은 앞서 제출한 공시에서 바뀌거나 잘못된 내용을 고친 거예요. 무엇이 달라졌는지 비교해 보는 게 좋아요.", concept: "정정 공시는 변경 전과 변경 후를 나란히 보여 주는 경우가 많아요.", src: "투자 기초 상식" },
  { slug: "chart_doji", label: "차트 기초", type: "4지선다", q: "시가와 종가가 거의 같아 몸통이 가로줄처럼 보이는 캔들은?", options: ["장대양봉", "갭", "장대음봉", "도지"], answer: 3, exp: "도지는 시작 가격과 끝 가격이 거의 같을 때 나타나요. 위아래 꼬리 길이는 그날 움직임에 따라 달라요.", concept: "도지는 사려는 힘과 팔려는 힘이 비슷했던 구간에서 자주 보여요.", src: "투자 기초 상식" },
  { slug: "trd_market_cap", label: "거래 기초", type: "4지선다", q: "시가총액은 어떻게 계산할까요?", options: ["주가 × 발행주식 수", "순이익 ÷ 주식 수", "매출 × 영업이익률", "주가 × 하루 거래량"], answer: 0, exp: "시가총액은 지금 주가로 따진 회사 전체 주식의 값이에요.", concept: "1주 가격이 높다고 큰 회사는 아니에요. 회사 크기는 시가총액으로 비교해요.", src: "투자 기초 상식" },
  { slug: "fin_surprise", label: "재무 기초", type: "4지선다", q: "시장 예상 영업이익이 1,000억 원인데 실제로 1,200억 원이 나왔어요. 예상을 몇 % 넘었을까요?", options: ["2%", "20%", "12%", "120%"], answer: 1, exp: "초과분 200억 원을 예상치 1,000억 원으로 나누면 20%예요.", concept: "시장 예상치를 크게 넘는 실적을 어닝 서프라이즈라고 불러요.", src: "투자 기초 상식" },
  { slug: "dis_retire", label: "공시 기초", type: "4지선다", q: "'주식소각결정' 공시의 뜻은 무엇일까요?", options: ["회사를 둘로 나눈다", "새 주식을 발행해 자금을 모은다", "주식을 없애 발행주식 수를 줄인다", "주주에게 현금을 나눠 준다"], answer: 2, exp: "주식 소각은 주식 자체를 없애는 결정이에요. 주식 수가 줄면 1주에 돌아가는 이익 몫이 커질 수 있어요.", concept: "자사주를 사기만 하면 다시 팔 수 있지만, 소각하면 그 주식은 사라져요.", src: "투자 기초 상식" },
  { slug: "ox_golden_cross", label: "차트 기초", type: "OX", q: "골든크로스가 나오면 주가는 반드시 오른다.", options: ["O", "X"], answer: 1, exp: "골든크로스는 과거 가격의 평균이 교차한 모양일 뿐, 앞으로의 상승을 보장하지 않아요.", concept: "이동평균선은 이미 지난 가격으로 계산해요.", src: "투자 기초 상식" },
  { slug: "trd_trade_value", label: "거래 기초", type: "4지선다", q: "거래대금을 구하는 방법으로 가장 알맞은 것은?", options: ["주가 × 발행주식 수", "순이익 ÷ 주식 수", "거래된 주식 수 × 거래 가격", "고가 − 저가"], answer: 2, exp: "거래대금은 하루 동안 실제로 오간 금액이에요. 주가 × 발행주식 수는 시가총액이에요.", concept: "거래량은 주식 수, 거래대금은 금액이에요.", src: "투자 기초 상식" },
  { slug: "fin_fx_exporter", label: "재무 기초", type: "4지선다", q: "수출 대금 1,000만 달러를 받는 회사. 원/달러가 1,300원에서 1,400원이 되면 원화 매출은?", options: ["10억 원 감소", "10억 원 증가", "변화 없음", "100억 원 증가"], answer: 1, exp: "130억 원에서 140억 원으로 10억 원 늘어요. 다만 원재료를 달러로 사면 비용도 함께 늘 수 있어요.", concept: "환율은 수출 매출과 수입 비용에 동시에 영향을 줘요.", src: "투자 기초 상식" },
  { slug: "dis_subsidiary", label: "공시 기초", type: "4지선다", q: "공시 제목 끝의 '(자회사의 주요경영사항)'이 알려 주는 것은?", options: ["공시 내용이 자회사에서 일어난 일이다", "모회사가 직접 결정한 일이다", "모회사 주주가 주식을 무상으로 받는다", "자회사가 상장폐지된다"], answer: 0, exp: "자회사에서 생긴 중요한 일을 모회사가 대신 알리는 공시예요. 모회사의 주식 수가 바로 바뀐다는 뜻은 아니에요.", concept: "공시 제목의 괄호까지 읽어야 누구의 결정인지 정확히 알 수 있어요.", src: "투자 기초 상식" },
  { slug: "trd_split", label: "거래 기초", type: "4지선다", q: "주가 100,000원인 종목이 5대 1 액면분할을 하면 이론상 주가는?", options: ["50,000원", "500,000원", "100,000원", "20,000원"], answer: 3, exp: "1주가 5주로 나뉘어 가격은 5분의 1이 돼요. 시가총액은 그대로예요.", concept: "액면분할은 회사 가치를 바꾸지 않고 1주 가격만 낮춰요.", src: "투자 기초 상식" },
  { slug: "fin_pbr_under_one", label: "재무 기초", type: "4지선다", q: "PBR이 1배보다 낮다는 것은 무슨 뜻일까요?", options: ["주가가 반드시 오른다", "부채가 자산보다 많다", "회사가 적자다", "시가총액이 장부상 순자산보다 작다"], answer: 3, exp: "PBR은 시가총액을 순자산으로 나눈 값이에요. 1배 미만이면 시장 가격이 장부 가치보다 낮다는 뜻이에요.", concept: "저PBR이 곧 저평가는 아니에요. 수익성이 낮아서일 수도 있어요.", src: "투자 기초 상식" },
  { slug: "dis_contract", label: "공시 기초", type: "4지선다", q: "'단일판매·공급계약체결' 공시에서 먼저 확인할 내용은?", options: ["공시 담당자의 이름", "공시가 제출된 시각", "계약 상대방 본사의 층수", "계약 금액의 매출 대비 비중과 계약 기간"], answer: 3, exp: "공급계약은 금액만 보면 크기를 알기 어려워요. 매출 대비 비중과 기간을 함께 봐야 실적에 미칠 영향을 가늠할 수 있어요.", concept: "이 공시는 회사가 큰 수주나 판매 계약을 맺었을 때 나와요.", src: "투자 기초 상식" },
  { slug: "trd_bonus_issue", label: "거래 기초", type: "4지선다", q: "주가 20,000원인 종목이 1주당 1주 무상증자를 하면 권리락 후 이론 주가는?", options: ["10,000원", "20,000원", "40,000원", "15,000원"], answer: 0, exp: "주식 수가 두 배가 되므로 이론 주가는 절반이 돼요.", concept: "무상증자는 회사 안의 자본 항목을 옮기는 일이라 회사 가치가 늘지 않아요.", src: "투자 기초 상식" },
  { slug: "fin_dividend_yield", label: "재무 기초", type: "4지선다", q: "주가 40,000원, 주당 배당금 2,000원인 종목의 배당수익률은?", options: ["50%", "20%", "5%", "2%"], answer: 2, exp: "2,000 ÷ 40,000 = 5%예요.", concept: "배당수익률은 주가가 바뀌면 함께 달라져요.", src: "투자 기초 상식" },
  { slug: "ox_ex_dividend", label: "거래 기초", type: "OX", q: "배당락일에 처음 산 주식으로는 이번 회차 배당을 받을 수 없다.", options: ["O", "X"], answer: 0, exp: "배당락일부터 산 주식은 이번 배당 권리가 없어요.", concept: "배당을 받으려면 배당기준일에 주주로 올라 있어야 해요.", src: "투자 기초 상식" },
  { slug: "fin_rate_growth", label: "재무 기초", type: "4지선다", q: "금리가 오를 때 성장주가 특히 부담을 받는다고 하는 이유는?", options: ["먼 미래 이익의 현재 가치가 더 많이 줄어서", "거래가 제한돼서", "금리가 오르면 매출이 0이 돼서", "성장주는 배당을 꼭 줘야 해서"], answer: 0, exp: "미래 이익을 지금 가치로 바꿀 때 금리로 할인해요. 이익이 먼 미래에 몰린 기업일수록 영향이 커요.", concept: "이 과정을 현금흐름 할인이라고 해요.", src: "투자 기초 상식" },
  { slug: "ox_bonus_value", label: "거래 기초", type: "OX", q: "무상증자를 하면 회사의 전체 가치가 그만큼 늘어난다.", options: ["O", "X"], answer: 1, exp: "주식 수만 늘고 회사가 가진 자산은 그대로예요.", concept: "그래서 권리락 때 주가가 이론적으로 조정돼요.", src: "투자 기초 상식" },
  { slug: "ox_op_profit_net_loss", label: "재무 기초", type: "OX", q: "영업이익이 흑자여도 당기순이익은 적자일 수 있다.", options: ["O", "X"], answer: 0, exp: "이자 비용, 환손실, 자산 손상 같은 영업 외 손실이 크면 순이익은 적자가 될 수 있어요.", concept: "영업이익은 본업, 순이익은 모든 손익을 반영한 결과예요.", src: "투자 기초 상식" },
  { slug: "ox_short_loss", label: "거래 기초", type: "OX", q: "공매도는 주가가 오를수록 손실이 커질 수 있다.", options: ["O", "X"], answer: 0, exp: "빌린 주식을 더 비싸게 사서 갚아야 하므로 주가가 오를수록 손실이 커져요.", concept: "매수 손실은 투자금이 한도지만, 공매도 손실은 이론상 한도가 없어요.", src: "투자 기초 상식" },
];

/** 새 문제가 열리는 시각 (한국 시간, 화면 문구 '내일 오전 10시에 새 문제가 열려요') */
const OPEN_HOUR = 10;

/** 오늘(한국 시간 오전 10시 기준)의 문제 번호 — 날마다 다음 문제, 30일마다 처음으로 */
export function quizIndex(now: Date = new Date()): number {
  const kst = now.getTime() + 9 * 3600_000 - OPEN_HOUR * 3600_000;
  const day = Math.floor(kst / 86400_000);
  return ((day % QUIZ_BANK.length) + QUIZ_BANK.length) % QUIZ_BANK.length;
}

/** 화면 props 모양 (mockQuiz 와 같은 칸). 연속 참여 · 이번 주 표시는 기록 API 가 없어 base(예시 값) 그대로 */
export function todayQuiz(base: typeof mockQuiz, now: Date = new Date()): typeof mockQuiz {
  const it = QUIZ_BANK[quizIndex(now)];
  return { ...base, label: it.label, day: '', type: it.type, q: it.q, options: it.options, answer: it.answer, exp: it.exp, concept: it.concept, src: `출처 · ${it.src}` };
}

const CATEGORY: Record<string, TodayQuiz['category']> = { '차트 기초': 'chart', '거래 기초': 'trading', '재무 기초': 'financials', '공시 기초': 'disclosure' };

/** mock API 응답: 내장 문제를 서버 GET /quiz/today 모양으로 */
export function toServerQuiz(now: Date = new Date()): TodayQuiz {
  const index = quizIndex(now);
  const it = QUIZ_BANK[index];
  return {
    slug: it.slug, category: CATEGORY[it.label] ?? 'trading', quiz_type: it.type === 'OX' ? 'ox' : 'four', label: it.label,
    question: it.q, options: it.options, answer_index: it.answer, explanation: it.exp, concept: it.concept, source: it.src,
    index, total: QUIZ_BANK.length,
  };
}

/** 서버 문제 → 화면 props 모양 (todayQuiz 와 같은 칸) */
export function fromServerQuiz(base: typeof mockQuiz, s: TodayQuiz): typeof mockQuiz {
  return {
    ...base, label: s.label, day: '', type: s.quiz_type === 'ox' ? 'OX' : '4지선다', q: s.question, options: s.options,
    answer: s.answer_index, exp: s.explanation, concept: s.concept, src: `출처 · ${s.source}`,
  };
}
