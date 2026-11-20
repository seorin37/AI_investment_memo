import type { MarketIndex } from './Home.types';

/** 1,234.56 (원본 toLocaleString en-US 2자리) */
export const nf = (n: number, d = 2) => n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });

/** ISO → 시:분 (한국 시각) */
export function hm(iso: string) {
  const m = /T(\d{2}):(\d{2})/.exec(iso);
  return m ? `${m[1]}:${m[2]}` : '';
}
/** YYYY-MM-DD… → MM.DD */
export const mmdd = (d: string) => `${d.slice(5, 7)}.${d.slice(8, 10)}`;
/** 원본 store.tsx ago: 방금 · N분 전 · N시간 전 · 어제 · N일 전 · MM.DD */
export function ago(iso: string, now: string) {
  const s = (Date.parse(now) - Date.parse(iso)) / 1000;
  if (s < 60) return '방금';
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  if (s < 86400 * 2) return '어제';
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}일 전`;
  return mmdd(iso);
}

/** 상승 #E5484D · 하락 #2F6BDB */
export const upDown = (up: boolean) => (up ? '#E5484D' : '#2F6BDB');

/* ───────── 앱 (원본 home.html) ───────── */

/** 원본 spark(arr, w, h): 위아래 4 여백 · 점 좌표와 선·면 경로 */
export function spark(arr: number[], w: number, h: number) {
  const mn = Math.min(...arr);
  const mx = Math.max(...arr);
  const pts = arr.map((v, i) => [(i / (arr.length - 1)) * w, h - 4 - ((v - mn) / (mx - mn || 1)) * (h - 8)] as const);
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
  return { d, area: `${d} L${w} ${h} L0 ${h}Z`, pts };
}

/** 앱 지수 자세히 기간 (원본 PER: 1주 · 1달 · 3달 · 1년 → 일별 종가 개수, 처음 값이 기준) */
export const APP_PERIODS = [
  { key: '1주', n: 6 },
  { key: '1달', n: 23 },
  { key: '3달', n: 65 },
  { key: '1년', n: 250 },
] as const;
export type AppPeriod = (typeof APP_PERIODS)[number]['key'];

/** 홈 시장 카드의 작은 선 (원본 24점) */
export const APP_SPARK_N = 24;

/* ───────── 웹 (원본 marketData.ts) ───────── */

/** ② 결정 (11.19): 웹도 '1일'(전 거래일 하루 흐름) 없이 1주부터 — 전일 확정 종가 원칙 */
export type WebRange = '1주' | '1달' | '1년';
export const WEB_RANGES: WebRange[] = ['1주', '1달', '1년'];

export function webSeries(q: MarketIndex, r: WebRange) {
  const n = r === '1주' ? 5 : r === '1달' ? 22 : 250;
  return q.closes.slice(-n);
}

/** 원본 mkData: 208×40 좌표 선 · 기준선 · 등락 글자 (부호는 − U+2212) */
export function mkData(q: MarketIndex, r: WebRange) {
  const sr = webSeries(q, r);
  const first = sr[0];
  const last = sr[sr.length - 1];
  const all = [...sr, first];
  const mn = Math.min(...all);
  const mx = Math.max(...all);
  const Y = (v: number) => ((mx - v) / (mx - mn || 1)) * 40;
  const path = sr.map((v, i) => `${i ? 'L' : 'M'}${((i / (sr.length - 1)) * 208).toFixed(2)} ${Y(v).toFixed(2)}`).join('');
  const chg = last - first;
  const pct = (chg / first) * 100;
  const sign = chg >= 0 ? '+' : '−';
  const pts = sr.map((v, i) => [(i / (sr.length - 1)) * 208, Y(v)] as const);
  return {
    sr,
    path,
    pts,
    base: Y(first),
    up: chg >= 0,
    label: `${sign}${nf(Math.abs(chg))} (${sign}${Math.abs(pct).toFixed(2)}%)`,
    when: `${r} · ${mmdd(q.as_of)} 종가 기준`,
    v: nf(last),
  };
}

/** 원본 rangeLabels: x축 날짜 5개 */
export function rangeLabels(r: WebRange, days: string[]): string[] {
  const n = r === '1주' ? 5 : r === '1달' ? 22 : 250;
  const d = days.slice(-n);
  return Array.from({ length: 5 }, (_, i) => d[Math.round((i / 4) * (d.length - 1))]).map((t) => (r === '1년' ? `${t.slice(2, 4)}.${t.slice(5, 7)}` : mmdd(t)));
}
