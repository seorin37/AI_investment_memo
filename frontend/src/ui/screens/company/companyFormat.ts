import type { StockProfile } from '@/types/models';
import type { CompanyHealth, CompanyQuarter } from './CompanyInfo.types';

/* 기업정보 숫자 모양 · 계산 (원본 앱 company.html mkD · 웹 company.tsx 와 같은 규칙, 모두 코드 계산) */

export const won = (n: number) => Math.round(n).toLocaleString('ko-KR');
/** 억원 → '16조 6,453억원' (웹 jo) */
export const jo = (eok: number) => {
  const neg = eok < 0;
  const a = Math.abs(Math.round(eok));
  const j = Math.floor(a / 10000);
  const r = a % 10000;
  return (neg ? '-' : '') + (j && r ? `${j}조 ${r.toLocaleString('ko-KR')}억원` : j ? `${j}조원` : `${r.toLocaleString('ko-KR')}억원`);
};
/** 'YYYY-MM-DD…' → 'MM.DD' */
export const mmddOf = (iso: string) => `${iso.slice(5, 7)}.${iso.slice(8, 10)}`;
/** 'YYYY-MM-DD' → 'M.DD' (원본 앱 차트 축 · 말풍선) */
export const mdOf = (iso: string) => `${Number(iso.slice(5, 7))}.${iso.slice(8, 10)}`;

/** 시가총액 원 → 원본 앱 '131.4조' · 1조 미만 '8,500억' */
export const capShort = (won_: number) => {
  const eok = won_ / 1e8;
  return eok >= 10000 ? `${(eok / 10000).toFixed(1)}조` : `${won(eok)}억`;
};

/** 앱 시세·투자정보 12칸 (원본 kv: 이름 · 값 · 도움말 키) — 두 칸씩 한 줄 */
export function appQuoteRows(p: StockProfile): [string, string, TermKey | null][] {
  const na = (v: number | null, f: (n: number) => string) => (v == null ? '—' : f(v));
  return [
    ['전일', won(p.prev_close), null],
    ['시가', won(p.open), null],
    ['고가', won(p.high), null],
    ['저가', won(p.low), null],
    ['거래량', `${won(p.volume)}주`, null],
    ['거래대금', `${won(p.trading_value / 1e8)}억`, null],
    ['시가총액', capShort(p.market_cap), 'mc'],
    ['상장주수', `${(p.shares_outstanding / 1e8).toFixed(2)}억주`, 'sh'],
    ['PER', na(p.per, (v) => `${v.toFixed(2)}배`), 'per'],
    ['PBR', na(p.pbr, (v) => `${v.toFixed(2)}배`), 'pbr'],
    ['EPS', na(p.eps, (v) => `${won(v)}원`), 'eps'],
    ['BPS', na(p.bps, (v) => `${won(v)}원`), 'bps'],
  ];
}

/* ---------- 재무 ---------- */
export type FinKey = 'revenue' | 'op' | 'net';
/** 전년 동기 대비 (원본 yoyOf): 이전 값이 0 이하면 % 대신 흑자 전환 · 적자 지속 · 적자 전환 */
export type Yoy = { t: 'none' } | { t: 'pct'; v: number } | { t: '흑자 전환' | '적자 지속' | '적자 전환' };
export function yoyAt(all: CompanyQuarter[], key: FinKey, i: number): Yoy {
  const c = all[i]?.[key];
  const p = all[i - 4]?.[key];
  if (p == null || c == null) return { t: 'none' };
  if (p <= 0) return { t: c > 0 ? '흑자 전환' : '적자 지속' };
  if (c <= 0) return { t: '적자 전환' };
  return { t: 'pct', v: ((c - p) / p) * 100 };
}

/* ---------- 건전성 ---------- */
export const HEALTH_KEYS: { k: string; key: keyof CompanyHealth; term: TermKey }[] = [
  { k: '부채비율', key: 'debt', term: 'debt' },
  { k: '유동비율', key: 'current', term: 'cur' },
  { k: '당좌비율', key: 'quick', term: 'quick' },
  { k: '이자보상비율', key: 'interest', term: 'icr' },
  { k: '유보율', key: 'reserve', term: 'ret' },
];
export const healthVal = (key: keyof CompanyHealth, v: number | null) => (v == null ? '—' : key === 'interest' ? `${v.toFixed(1)}배` : `${won(v)}%`);
/** 안정성 점수 0.3~1 (바깥일수록 안정 · 웹 SCORE 메모스톡 자체 기준). 값이 없으면 0 (가운데) */
export function healthScore(key: keyof CompanyHealth, v: number | null): number {
  if (v == null) return 0;
  const f: Record<keyof CompanyHealth, (n: number) => number> = {
    debt: (n) => 1 - n / 400,
    current: (n) => n / 250,
    quick: (n) => n / 200,
    interest: (n) => n / 30,
    reserve: (n) => Math.log10(Math.max(10, n)) / 4.5,
  };
  return Math.max(0.3, Math.min(1, f[key](v)));
}

export const FINANCIAL_HEALTH_NOTE = '금융회사는 예금이 부채로 잡혀 부채비율이 높게 나와요.';

/* ---------- 용어 설명 (원본 앱 TERMS: 풀이와 계산식만 · 좋다·나쁘다 판단 없음) ---------- */
export type TermKey = 'per' | 'pbr' | 'eps' | 'bps' | 'mc' | 'sh' | 'debt' | 'cur' | 'quick' | 'icr' | 'ret' | 'opm' | 'npm' | 'roe';
export const TERM_TIP = '업종마다 보통 수준이 달라서, 같은 업종끼리 비교하는 게 좋아요. 이 값만으로 좋다·나쁘다를 판단하지 않아요.';
type TermCtx = { p: StockProfile; price: number; last: CompanyQuarter; health: CompanyHealth };
export const TERMS: Record<TermKey, [string, string, string, (c: TermCtx) => string]> = {
  per: ['PER', '주가수익비율', '주가 ÷ 주당순이익(EPS). 회사가 1년에 버는 이익에 비해 주가가 몇 배인지 보여 줘요.', ({ p, price }) => (p.per == null || p.eps == null ? '—' : `${p.per.toFixed(2)}배 = ${won(price)}원 ÷ ${won(p.eps)}원`)],
  pbr: ['PBR', '주가순자산비율', '주가 ÷ 주당순자산(BPS). 회사가 가진 순자산에 비해 주가가 몇 배인지 보여 줘요.', ({ p, price }) => (p.pbr == null || p.bps == null ? '—' : `${p.pbr.toFixed(2)}배 = ${won(price)}원 ÷ ${won(p.bps)}원`)],
  eps: ['EPS', '주당순이익', '순이익 ÷ 주식 수. 주식 1주가 1년 동안 번 이익이에요.', ({ p }) => (p.eps == null ? '—' : `${won(p.eps)}원 (직전 사업연도 기준 · 한국투자증권)`)],
  bps: ['BPS', '주당순자산', '순자산(자본총계) ÷ 주식 수. 주식 1주에 해당하는 순자산이에요.', ({ p }) => (p.bps == null ? '—' : `${won(p.bps)}원 (직전 사업연도 말 기준 · 한국투자증권)`)],
  mc: ['시가총액', '', '주가 × 상장주식 수. 시장에서 매겨진 회사 전체의 값이에요. KRX 원천값을 그대로 보여 줘요.', ({ p }) => `${capShort(p.market_cap)} (KRX · 전일 기준)`],
  sh: ['상장주수', '상장주식 수', '거래소에 올라 있는 이 회사 주식의 수예요.', ({ p }) => `${(p.shares_outstanding / 1e8).toFixed(2)}억주 (KRX)`],
  debt: ['부채비율', '', '부채 ÷ 자본 × 100. 자기 돈에 비해 빌린 돈이 얼마나 되는지 보여 줘요.', ({ health }) => `${healthVal('debt', health.debt)} = 부채총계 ÷ 자본총계 × 100`],
  cur: ['유동비율', '', '유동자산 ÷ 유동부채 × 100. 1년 안에 갚을 빚에 비해 1년 안에 현금으로 바꿀 수 있는 자산이 얼마나 되는지예요.', ({ health }) => (health.current == null ? '— · 금융업은 공시하지 않는 지표예요' : `${healthVal('current', health.current)} = 유동자산 ÷ 유동부채 × 100`)],
  quick: ['당좌비율', '', '(유동자산 − 재고자산) ÷ 유동부채 × 100. 재고를 빼고 본 단기 지급 능력이에요.', ({ health }) => (health.quick == null ? '— · 금융업은 공시하지 않는 지표예요' : `${healthVal('quick', health.quick)} = (유동자산 − 재고) ÷ 유동부채 × 100`)],
  icr: ['이자보상비율', '', '영업이익 ÷ 이자비용. 번 돈으로 이자를 몇 번 낼 수 있는지예요.', ({ health }) => (health.interest == null ? '— · 금융업은 공시하지 않는 지표예요' : `${healthVal('interest', health.interest)} = 영업이익 ÷ 이자비용`)],
  ret: ['유보율', '', '잉여금 ÷ 자본금 × 100. 벌어서 회사 안에 쌓아 둔 돈이 자본금의 몇 배인지예요.', ({ health }) => `${healthVal('reserve', health.reserve)} = (이익잉여금 + 자본잉여금) ÷ 자본금 × 100`],
  opm: ['영업이익률', '', '영업이익 ÷ 매출 × 100. 본업으로 매출 100원당 얼마를 남겼는지예요.', ({ last }) => (last.op_margin == null ? '— · 매출을 공시하지 않는 종목이에요' : `${last.op_margin.toFixed(1)}% = 영업이익 ÷ 매출 × 100 (${last.q})`)],
  npm: ['순이익률', '', '순이익 ÷ 매출 × 100. 세금 등을 다 빼고 매출 100원당 얼마를 남겼는지예요.', ({ last }) => (last.net_margin == null ? '— · 매출을 공시하지 않는 종목이에요' : `${last.net_margin.toFixed(1)}% = 순이익 ÷ 매출 × 100 (${last.q})`)],
  roe: ['ROE', '자기자본이익률', '순이익 ÷ 자본 × 100. 주주의 돈(자본)으로 얼마나 이익을 냈는지예요.', ({ last }) => (last.roe == null ? '—' : `${last.roe.toFixed(1)}% = 순이익(연환산) ÷ 평균 자본 × 100 (${last.q})`)],
};
