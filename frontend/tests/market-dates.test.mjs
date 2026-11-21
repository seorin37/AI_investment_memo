import assert from 'node:assert/strict';
import test from 'node:test';

import { basisText, mkData, pointText, rangeLabels } from '../src/ui/screens/home/homeFormat.ts';
import { toHomeMarket } from '../src/ui/screens/home/homeMarket.ts';
import { applyQuotes } from '../src/ui/screens/stocks/stockPrices.ts';

/* 날짜가 서로 다른 경우 (DB 없이). 지표마다 자기 날짜를 쓰고, 없는 날 값을 만들지 않는다 */

const days = (end, n) => Array.from({ length: n }, (_, i) => {
  const d = new Date(`${end}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - (n - 1 - i));
  return d.toISOString().slice(0, 10);
});

function index(key, end, values) {
  const dates = days(end, values.length);
  const last = values[values.length - 1];
  const prev = values[values.length - 2];
  return {
    key, label: key, flag: 'kr', value: last, change: last - prev, change_pct: ((last - prev) / prev) * 100,
    series: { '1D': values.slice(-2), '1W': values.slice(-5), '1M': values, '1Y': values },
    trade_date: end, dates,
  };
}

const overview = (kospiEnd, usdEnd) => ({
  as_of: `${kospiEnd}T15:30:00+09:00`,
  macro: [],
  indices: [
    index('KOSPI', kospiEnd, [2500, 2510, 2520, 2530, 2540, 2550]),
    index('USDKRW', usdEnd, [1320, 1322, 1325, 1328, 1330, 1335]),
  ],
});

test('환율 11/20 · 코스피 11/19: 원/달러는 11/20 값·날짜, 코스피는 11/19', () => {
  const { market, days: newsDays } = toHomeMarket(overview('2026-11-19', '2026-11-20'));
  const usd = market.find((m) => m.key === 'usd');
  const kospi = market.find((m) => m.key === 'kospi');
  assert.equal(usd.as_of, '2026-11-20');
  assert.equal(usd.closes.at(-1), 1335); // 앞 값 채우기 없이 자기 시리즈 끝
  assert.equal(usd.dates.at(-1), '2026-11-20');
  assert.equal(usd.closes.length, usd.dates.length);
  assert.equal(kospi.as_of, '2026-11-19');
  assert.equal(kospi.dates.at(-1), '2026-11-19');
  assert.equal(newsDays.at(-1), '2026-11-19'); // 뉴스 기준일 = 코스피
  // 웹 카드: 숫자(시리즈 끝)와 문구 날짜가 같은 날
  const md = mkData(usd, '1주');
  assert.equal(md.v, '1,335.00');
  assert.equal(md.when, '1주 · 11.20 기준');
  assert.equal(mkData(kospi, '1주').when, '1주 · 11.19 종가 기준');
  // 짚은 점의 날짜 = 그 점의 실제 날짜
  assert.equal(pointText(usd, usd.dates.at(-1)), '11.20 기준');
  assert.equal(pointText(kospi, kospi.dates.at(-2)), '11.18 종가');
  assert.deepEqual(rangeLabels('1주', usd.dates), ['11.16', '11.17', '11.18', '11.19', '11.20']);
});

test('코스피 11/20 · 환율 11/19: 원/달러에 11/20 값을 만들지 않음', () => {
  const { market } = toHomeMarket(overview('2026-11-20', '2026-11-19'));
  const usd = market.find((m) => m.key === 'usd');
  const kospi = market.find((m) => m.key === 'kospi');
  assert.equal(usd.as_of, '2026-11-19');
  assert.equal(usd.dates.at(-1), '2026-11-19');
  assert.ok(!usd.dates.includes('2026-11-20'));
  assert.deepEqual(usd.closes, [1320, 1322, 1325, 1328, 1330, 1335]); // 값을 늘리거나 바꾸지 않음
  assert.equal(basisText(usd), '11.19 기준');
  assert.equal(basisText(kospi), '11.20 종가 기준');
});

test('날짜와 값의 짝이 안 맞으면 날짜를 지어내지 않고 비움', () => {
  const o = overview('2026-11-19', '2026-11-19');
  o.indices[1].dates = o.indices[1].dates.slice(1);
  const usd = toHomeMarket(o).market.find((m) => m.key === 'usd');
  assert.deepEqual(usd.dates, []);
  assert.deepEqual(rangeLabels('1주', usd.dates), []);
  assert.equal(pointText(usd, usd.dates[0]), '');
});

const row = (stock_code) => ({ stock_code, name: stock_code, logo: 'x', logo_bg: '#000', market: 'KOSPI', status: 'watching', memo_count: 0, ai_count: 0, new_count: 0, price: null, change_pct: null, ai_ready: true });
const quote = (code, trade_date, price) => ({ code, price, change: 0, change_pct: 0.5, as_of: `${trade_date}T15:30:00+09:00`, trade_date, spark: [price] });

test('내 종목: 날짜가 모두 같으면 한 줄, 줄마다 날짜 없음', () => {
  const r = applyQuotes([row('005930'), row('000660')], [], [quote('005930', '2026-11-19', 1), quote('000660', '2026-11-19', 2)]);
  assert.equal(r.as_of, '2026-11-19');
  assert.equal(r.as_of_mixed, false);
  assert.deepEqual(r.stocks.map((s) => s.as_of), [undefined, undefined]);
});

test('내 종목: 일부만 11/20 이면 줄마다 날짜, 위 한 줄은 종목별', () => {
  const r = applyQuotes(
    [row('005930'), row('000660'), row('123456')],
    [{ ...row('105560'), sector: '금융' }],
    [quote('005930', '2026-11-20', 1), quote('000660', '2026-11-19', 2), quote('105560', '2026-11-20', 3)],
  );
  assert.equal(r.as_of_mixed, true);
  assert.deepEqual(r.stocks.map((s) => s.as_of), ['2026-11-20', '2026-11-19', undefined]);
  assert.deepEqual(r.stocks.map((s) => s.price), [1, 2, null]); // 시세 없는 종목은 '—'
  assert.equal(r.universe[0].price, 3);
});

test('내 종목: 시세가 하나도 없으면 미연결', () => {
  const r = applyQuotes([row('005930')], [], []);
  assert.equal(r.as_of, '');
  assert.equal(r.as_of_mixed, false);
  assert.equal(r.stocks[0].price, null);
});
