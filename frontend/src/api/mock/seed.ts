/**
 * 목업 시드 데이터 — 디자인 시안(AI 투자 메모보드 UI_최종)의 예시 문구를 그대로 사용.
 * 실제 시세·공시가 아닌 화면 개발용 예시 값입니다.
 */
import type {
  AiUpdate,
  BoardItem,
  CalendarEvent,
  Candle,
  CompareMemoCard,
  JournalEntry,
  MarketIndex,
  MarketOverview,
  MarketUpdate,
  MemoVersion,
  MyStock,
  NewsHeadline,
  Settings,
  StockMaster,
  StockProfile,
  TimelineEntry,
  TrashItem,
  User,
} from '@/types/models';
import { ymd } from '@/lib/format';

const NOW = new Date();
const ago = ({ m = 0, h = 0, d = 0 }: { m?: number; h?: number; d?: number }) =>
  new Date(NOW.getTime() - ((d * 24 + h) * 60 + m) * 60_000).toISOString();
const at = (iso: string) => new Date(iso).toISOString();

// ─── 결정적 난수 (같은 시드 → 같은 차트) ───────────────────────
function mulberry32(seed: number) {
  return () => {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const user: User = {
  id: 'u_nara',
  name: '김나라',
  bio: '대학생',
  avatar_url: null,
  email: 'nara@kakao.example',
  providers: [
    { provider: 'kakao', email: 'nara@kakao.example', connected: true, current: true },
    { provider: 'naver', email: null, connected: false, current: false },
    { provider: 'google', email: null, connected: false, current: false },
  ],
};

export const stockMaster: StockMaster[] = [
  { code: '005930', name: '삼성전자', market: 'KOSPI' },
  { code: '005935', name: '삼성전자우', market: 'KOSPI' },
  { code: '000660', name: 'SK하이닉스', market: 'KOSPI' },
  { code: '035420', name: '네이버', market: 'KOSPI' },
  { code: '005380', name: '현대차', market: 'KOSPI' },
  { code: '000270', name: '기아', market: 'KOSPI' },
  { code: '035720', name: '카카오', market: 'KOSPI' },
  { code: '373220', name: 'LG에너지솔루션', market: 'KOSPI' },
  { code: '207940', name: '삼성바이오로직스', market: 'KOSPI' },
  { code: '068270', name: '셀트리온', market: 'KOSPI' },
  { code: '005490', name: 'POSCO홀딩스', market: 'KOSPI' },
  { code: '105560', name: 'KB금융지주', market: 'KOSPI' },
  { code: '042700', name: '한미반도체', market: 'KOSPI' },
  { code: '086520', name: '에코프로', market: 'KOSDAQ' },
  { code: '196170', name: '알테오젠', market: 'KOSDAQ' },
];

export const myStocks: MyStock[] = [
  { code: '000660', name: 'SK하이닉스', market: 'KOSPI', status: 'holding', tags: [], unread_updates: 3, added_at: '2026-09-20T10:00:00+09:00' },
  { code: '005930', name: '삼성전자', market: 'KOSPI', status: 'watching', tags: [], unread_updates: 2, added_at: '2026-09-21T10:00:00+09:00' },
  { code: '035420', name: '네이버', market: 'KOSPI', status: 'watching', tags: [], unread_updates: 0, added_at: '2026-09-22T10:00:00+09:00' },
  { code: '105560', name: 'KB금융지주', market: 'KOSPI', status: 'watching', tags: [], unread_updates: 0, added_at: '2026-09-23T10:00:00+09:00' },
];

// ─── 시세 ────────────────────────────────────────────────────
const lastClose: Record<string, { close: number; prev: number; seed: number; vol: number }> = {
  '000660': { close: 180_500, prev: 176_300, seed: 660, vol: 0.022 },
  '005930': { close: 69_800, prev: 69_500, seed: 5930, vol: 0.014 },
  '035420': { close: 168_200, prev: 169_500, seed: 35420, vol: 0.016 },
};

function tradingDays(count: number): Date[] {
  const days: Date[] = [];
  const d = new Date(NOW);
  d.setHours(15, 30, 0, 0);
  while (days.length < count) {
    const wd = d.getDay();
    if (wd !== 0 && wd !== 6) days.unshift(new Date(d));
    d.setDate(d.getDate() - 1);
  }
  return days;
}

/** 마지막 종가가 정확히 시안 값이 되도록 뒤에서부터 랜덤워크 생성 */
export function genCandles(code: string, count = 260): Candle[] {
  const cfg = lastClose[code] ?? { close: 50_000, prev: 49_500, seed: Number(code) || 7, vol: 0.018 };
  const rnd = mulberry32(cfg.seed);
  const days = tradingDays(count);
  const closes: number[] = new Array(count);
  closes[count - 1] = cfg.close;
  closes[count - 2] = cfg.prev;
  for (let i = count - 3; i >= 0; i--) {
    const drift = (rnd() - 0.5) * 2 * cfg.vol + 0.0009; // 과거로 갈수록 약간 낮게
    closes[i] = closes[i + 1] / (1 + drift);
  }
  const tick = cfg.close >= 100_000 ? 100 : 50;
  const round = (v: number) => Math.round(v / tick) * tick;
  return days.map((day, i) => {
    const close = round(closes[i]);
    const prev = i === 0 ? close : round(closes[i - 1]);
    const open = round(prev * (1 + (rnd() - 0.5) * cfg.vol * 0.8));
    const high = round(Math.max(open, close) * (1 + rnd() * cfg.vol * 0.6));
    const low = round(Math.min(open, close) * (1 - rnd() * cfg.vol * 0.6));
    const volume = Math.round((2_400_000 + rnd() * 3_200_000) * (code === '005930' ? 4.2 : 1));
    return { date: ymd(day), open, high, low, close, volume };
  });
}

export const profiles: Record<string, Omit<StockProfile, 'prev_close' | 'open' | 'high' | 'low' | 'volume' | 'trading_value' | 'week52_low' | 'week52_high' | 'market_cap'>> = {
  '000660': {
    code: '000660',
    name: 'SK하이닉스',
    market: 'KOSPI',
    overview:
      'SK하이닉스는 DRAM과 NAND 플래시 등 메모리 반도체를 설계·제조하는 기업입니다. AI 서버용 고대역폭 메모리(HBM)를 비롯한 고성능 메모리 제품을 공급하며, 반도체 업황과 AI 수요에 따라 실적이 크게 움직이는 종목이에요.',
    per: 3.06,
    pbr: 1.9,
    eps: 58_980,
    bps: 95_100,
    shares_outstanding: 728_002_365,
  },
  '005930': {
    code: '005930',
    name: '삼성전자',
    market: 'KOSPI',
    overview:
      '삼성전자는 메모리·시스템 반도체, 스마트폰, TV·가전 등을 만드는 종합 전자 기업입니다. 반도체(DS)와 모바일·가전(DX) 두 축으로 실적이 나뉘며, 메모리 가격 흐름에 영향을 크게 받아요.',
    per: 14.2,
    pbr: 1.12,
    eps: 4_915,
    bps: 62_320,
    shares_outstanding: 5_919_637_922,
  },
  '035420': {
    code: '035420',
    name: '네이버',
    market: 'KOSPI',
    overview:
      '네이버는 국내 최대 검색 포털을 운영하며 커머스, 핀테크, 콘텐츠, 클라우드 사업을 함께 하는 인터넷 기업이에요. 광고 경기와 커머스 거래액, AI 서비스 투자 흐름이 실적에 영향을 줘요.',
    per: 19.4,
    pbr: 1.21,
    eps: 8_670,
    bps: 139_000,
    shares_outstanding: 158_437_008,
  },
};

// ─── 메모 보드 ───────────────────────────────────────────────
export const board: BoardItem[] = [
  {
    id: 'm1', kind: 'memo', stock_code: '000660', position: 1, title: '실적 나오면 다시 보기',
    body: '다음 분기 실적 확인하고\n추가 매수 생각해보기.', tags: ['실적'], color: 'yellow', pinned: true,
    ai_linked: true, ai_linked_at: '2026-10-01T09:12:00+09:00', price_conditions: [], unread_updates: 1,
    created_at: '2026-10-01T09:10:00+09:00', updated_at: '2026-10-01T09:10:00+09:00',
  },
  {
    id: 'm2', kind: 'memo', stock_code: '000660', position: 2, title: '요즘 반도체 분위기 좋아 보여',
    body: 'AI 수요 이야기 계속 나와서\n기대감 있는 것 같음.', tags: ['반도체', 'AI'], color: 'blue', pinned: false,
    ai_linked: true, ai_linked_at: '2026-10-03T20:02:00+09:00', price_conditions: [], unread_updates: 2,
    created_at: '2026-10-03T20:00:00+09:00', updated_at: '2026-10-03T20:00:00+09:00',
  },
  {
    id: 'm3', kind: 'memo', stock_code: '000660', position: 3, title: '너무 급하게 따라 사지 말기',
    body: '지금은 좀 지켜보고\n조금 더 확인한 뒤에 들어가기.', tags: ['매수전략', '주의'], color: 'pink', pinned: false,
    ai_linked: false, ai_linked_at: null, price_conditions: [], unread_updates: 0,
    created_at: '2026-10-05T21:30:00+09:00', updated_at: '2026-10-05T21:30:00+09:00',
  },
  {
    id: 'c1', kind: 'checklist', stock_code: '000660', position: 4, title: '체크리스트',
    items: [
      { id: 'c1i1', text: '실적 발표 전 확인', done: false },
      { id: 'c1i2', text: '관련 뉴스 다시 확인', done: true },
      { id: 'c1i3', text: '가격 떨어지면 다시 보기', done: false },
      { id: 'c1i4', text: '삼성전자랑 같이 비교해보기', done: false },
    ],
    created_at: '2026-10-02T10:00:00+09:00', updated_at: '2026-10-02T10:00:00+09:00',
  },
  {
    id: 'r1', kind: 'reference', stock_code: '000660', position: 5, title: '참고 자료',
    links: [
      { id: 'r1l1', title: 'SK하이닉스 IR 자료', url: 'https://www.skhynix.com/ir/', ref_type: 'ir', source: 'link' },
      { id: 'r1l2', title: '최근 주요 뉴스 정리', url: 'https://search.naver.com/search.naver?where=news&query=SK%ED%95%98%EC%9D%B4%EB%8B%89%EC%8A%A4', ref_type: 'news', source: 'link' },
      { id: 'r1l3', title: '반도체 산업 전망 리포트', url: 'https://finance.naver.com/research/', ref_type: 'report', source: 'link' },
    ],
    created_at: '2026-10-02T11:00:00+09:00', updated_at: '2026-10-02T11:00:00+09:00',
  },
  {
    id: 'm4', kind: 'memo', stock_code: '000660', position: 6, title: '15만원 밑으로 오면 다시 생각',
    body: '지지선 근처 오면\n분할 매수 고민해보기.', tags: ['매수가'], color: 'green', pinned: true,
    ai_linked: true, ai_linked_at: '2026-09-25T22:31:00+09:00',
    price_conditions: [{ id: 'pc1', direction: 'below', price: 150_000, tracking: true, status: 'waiting', reached_at: null }],
    unread_updates: 0, created_at: '2026-09-25T22:31:00+09:00', updated_at: '2026-10-06T21:14:00+09:00',
  },
  {
    id: 'm5', kind: 'memo', stock_code: '000660', position: 7, title: '삼성전자랑 같이 비교해보기',
    body: '두 종목 주가 흐름 비교해서\n판단하기.', tags: ['비교'], color: 'purple', pinned: false,
    ai_linked: false, ai_linked_at: null, price_conditions: [], unread_updates: 0,
    created_at: '2026-10-09T19:00:00+09:00', updated_at: '2026-10-09T19:00:00+09:00',
  },
  // 삼성전자
  {
    id: 'm6', kind: 'memo', stock_code: '005930', position: 1, title: '배당 정책 바뀌면 다시 보기',
    body: '배당 규모나 정책이 바뀌었다는 공시가 있는지 확인하기.\n새 소식이 오면 예전 생각과 비교해 보자.', tags: ['배당'], color: 'blue', pinned: true,
    ai_linked: true, ai_linked_at: '2026-10-15T09:00:00+09:00', price_conditions: [], unread_updates: 1,
    created_at: '2026-10-15T09:00:00+09:00', updated_at: '2026-10-15T09:00:00+09:00',
  },
  {
    id: 'm7', kind: 'memo', stock_code: '005930', position: 2, title: '7만원 밑이면 다시 보기',
    body: '7만원 아래로 내려오면\n밸류에이션 다시 확인하기.', tags: ['매수가'], color: 'green', pinned: false,
    ai_linked: true, ai_linked_at: '2026-10-10T21:00:00+09:00',
    price_conditions: [{ id: 'pc2', direction: 'below', price: 70_000, tracking: true, status: 'reached', reached_at: '2026-10-16T15:30:00+09:00' }],
    unread_updates: 1, created_at: '2026-10-10T21:00:00+09:00', updated_at: '2026-10-10T21:00:00+09:00',
  },
  {
    id: 'c2', kind: 'checklist', stock_code: '005930', position: 3, title: '체크리스트',
    items: [{ id: 'c2i1', text: '배당 공시 살펴보기', done: false }],
    created_at: '2026-10-15T09:10:00+09:00', updated_at: '2026-10-15T09:10:00+09:00',
  },
  // 네이버
  {
    id: 'm8', kind: 'memo', stock_code: '035420', position: 1, title: '다음 분기 수익성 비교',
    body: '다음 분기 매출과 수익성 변화를 함께 비교해 보기.', tags: ['실적'], color: 'yellow', pinned: false,
    ai_linked: false, ai_linked_at: null, price_conditions: [], unread_updates: 0,
    created_at: '2026-10-12T22:00:00+09:00', updated_at: '2026-10-12T22:00:00+09:00',
  },
  {
    id: 'm9', kind: 'memo', stock_code: '035420', position: 2, title: '16만원 밑이면 분할 매수',
    body: '16만원 아래에서는 두 번에 나눠 사기.', tags: ['매수가'], color: 'green', pinned: false,
    ai_linked: true, ai_linked_at: '2026-09-24T20:00:00+09:00',
    price_conditions: [{ id: 'pc3', direction: 'below', price: 160_000, tracking: true, status: 'reached', reached_at: '2026-09-30T15:30:00+09:00' }],
    unread_updates: 0, created_at: '2026-09-24T20:00:00+09:00', updated_at: '2026-09-24T20:00:00+09:00',
  },
];

export const memoVersions: Record<string, MemoVersion[]> = {
  m4: [
    { version: 1, title: '15만원 밑으로 오면 다시 생각', body: '지지선 근처 오면 다시 보기.', saved_at: '2026-09-25T22:31:00+09:00' },
    { version: 2, title: '15만원 밑으로 오면 다시 생각', body: '지지선 근처 오면 분할 매수 고민해보기.', saved_at: '2026-10-06T21:14:00+09:00' },
  ],
};

// ─── 업데이트 ────────────────────────────────────────────────
export const aiUpdates: AiUpdate[] = [
  {
    id: 'a1', stock_code: '000660', stock_name: 'SK하이닉스', type: 'disclosure', title: '신규 설비투자 관련 공시',
    headline: '신규 설비투자 공시가 나왔어요', source: 'DART', url: 'https://dart.fss.or.kr/', published_at: ago({ h: 2 }),
    memo_id: 'm1', memo_title: '실적 나오면 다시 보기', memo_version: 1, read: false, relevance: 0.82,
    summary: '신규 설비투자 결정 공시예요. 투자 규모와 일정이 메모에 적어 둔 실적 확인 시점과 겹치는지 살펴볼 만해요.',
  },
  {
    id: 'a2', stock_code: '000660', stock_name: 'SK하이닉스', type: 'news', title: 'HBM4 공급 확대 기대감',
    headline: 'HBM4 공급 확대 소식이 나왔어요', source: '연합뉴스', url: 'https://www.yna.co.kr/', published_at: ago({ d: 1, h: 1 }),
    memo_id: 'm2', memo_title: '요즘 반도체 분위기 좋아 보여', memo_version: 1, read: false, relevance: 0.88,
    summary: 'HBM4 공급 확대 보도와 함께 외국인 매수 소식이 있었어요. 메모에 남긴 AI 수요 기대감과 이어지는 내용이에요.',
  },
  {
    id: 'a3', stock_code: '000660', stock_name: 'SK하이닉스', type: 'price', title: '주가 +7.1% 상승',
    headline: '최근 5거래일 동안 7.1% 올랐어요', source: '한국투자증권 KIS', url: null, published_at: ago({ d: 2, h: 3 }),
    memo_id: 'm2', memo_title: '요즘 반도체 분위기 좋아 보여', memo_version: 1, read: false, relevance: 0.7,
    summary: '최근 5거래일 동안 7.1% 올랐고 거래량도 평소보다 늘었어요.',
  },
  {
    id: 'a4', stock_code: '000660', stock_name: 'SK하이닉스', type: 'news', title: 'HBM 수요 전망 관련 소식',
    headline: 'HBM 수요 전망 소식이 나왔어요', source: '한국경제', url: 'https://www.hankyung.com/', published_at: ago({ d: 3, h: 2 }),
    memo_id: 'm2', memo_title: '요즘 반도체 분위기 좋아 보여', memo_version: 1, read: true, relevance: 0.74,
    summary: '내년 HBM 수요 전망을 다룬 기사예요.',
  },
  {
    id: 'a5', stock_code: '000660', stock_name: 'SK하이닉스', type: 'disclosure', title: '분기 실적 발표 일정 안내',
    headline: '3분기 실적 발표가 예정돼 있어요', source: 'DART', url: 'https://dart.fss.or.kr/', published_at: ago({ d: 4, h: 1 }),
    memo_id: 'm1', memo_title: '실적 나오면 다시 보기', memo_version: 1, read: true, relevance: 0.9,
    summary: '실적 발표(기업설명회) 일정 공시예요. 메모의 “실적 나오면” 시점과 연결했어요.',
  },
  // 메모 m4 타임라인 (디자인 'AI 업데이트 세부 화면')
  {
    id: 'a6', stock_code: '000660', stock_name: 'SK하이닉스', type: 'news', title: 'HBM4 공급 확대 기대감',
    headline: 'HBM4 공급 확대 소식이 나왔어요', source: '네이버 뉴스', url: 'https://news.naver.com/', published_at: '2026-10-15T08:40:00+09:00',
    memo_id: 'm4', memo_title: '15만원 밑으로 오면 다시 생각', memo_version: 2, read: true, relevance: 0.66,
    summary: 'HBM4 공급 확대 보도와 외국인 매수 소식이 있었어요. 주가가 15만원 조건가에서 멀어진 배경을 살펴볼 수 있어요.',
  },
  {
    id: 'a7', stock_code: '000660', stock_name: 'SK하이닉스', type: 'price', title: '종가 180,500원',
    headline: '15만원 조건가에서 멀어졌어요', source: '한국투자증권 KIS', url: null, published_at: '2026-10-11T15:30:00+09:00',
    memo_id: 'm4', memo_title: '15만원 밑으로 오면 다시 생각', memo_version: 2, read: true, relevance: 1,
    summary: '종가 180,500원 · 조건가보다 30,500원(20.3%) 높아요. 아직 설정한 15만원 조건에 도달하지 않았어요.',
  },
  {
    id: 'a8', stock_code: '000660', stock_name: 'SK하이닉스', type: 'price', title: '종가 156,800원',
    headline: '15만원 조건가에 가까워졌어요', source: '한국투자증권 KIS', url: null, published_at: '2026-10-02T15:30:00+09:00',
    memo_id: 'm4', memo_title: '15만원 밑으로 오면 다시 생각', memo_version: 1, read: true, relevance: 1,
    summary: '최근 5거래일 동안 6.2% 내렸어요. 종가 156,800원으로, 설정한 15만원보다 6,800원(4.5%) 높아요.',
  },
  {
    id: 'a9', stock_code: '000660', stock_name: 'SK하이닉스', type: 'disclosure', title: '분기 실적 발표 예정 공시',
    headline: '3분기 실적 발표가 예정돼 있어요', source: 'DART', url: 'https://dart.fss.or.kr/', published_at: '2026-09-29T17:05:00+09:00',
    memo_id: 'm4', memo_title: '15만원 밑으로 오면 다시 생각', memo_version: 1, read: true, relevance: 0.61,
    summary: '10월 22일 실적 발표 예정 소식이에요. 가격 조건과 함께 살펴볼 일정으로 연결했어요.',
  },
  // 삼성전자
  {
    id: 'a10', stock_code: '005930', stock_name: '삼성전자', type: 'disclosure', title: '현금배당 결정 공시',
    headline: '배당 관련 공시가 도착했어요', source: 'DART', url: 'https://dart.fss.or.kr/', published_at: ago({ d: 1, h: 4 }),
    memo_id: 'm6', memo_title: '배당 정책 바뀌면 다시 보기', memo_version: 1, read: false, relevance: 0.93,
    summary: '배당 관련 공시를 메모와 연결했어요. 정책 변경 여부와 세부 내용은 공시 원문에서 확인해요.',
  },
  {
    id: 'a11', stock_code: '005930', stock_name: '삼성전자', type: 'price', title: '종가 69,800원',
    headline: '설정한 7만원 조건에 도달했어요', source: '한국투자증권 KIS', url: null, published_at: '2026-10-16T15:30:00+09:00',
    memo_id: 'm7', memo_title: '7만원 밑이면 다시 보기', memo_version: 1, read: false, relevance: 1,
    summary: '종가가 7만원 아래로 내려왔어요. 메모에 적어 둔 대로 밸류에이션을 다시 확인해 볼 시점이에요.',
  },
];

export const marketUpdates: MarketUpdate[] = [
  // 삼성전자 (3.2 시안)
  { id: 'u1', stock_code: '005930', stock_name: '삼성전자', type: 'disclosure', title: '자기주식 취득 결정 관련 주요사항 보고', source: 'DART', url: 'https://dart.fss.or.kr/', published_at: ago({ m: 10 }) },
  { id: 'u2', stock_code: '005930', stock_name: '삼성전자', type: 'news', title: '차세대 HBM 패키징 투자 확대 발표', source: '뉴스', url: 'https://www.mk.co.kr/', published_at: ago({ m: 45 }) },
  { id: 'u3', stock_code: '005930', stock_name: '삼성전자', type: 'price', title: '장중 2.1% 상승, 거래량 증가', source: '시세', url: null, published_at: ago({ h: 2 }) },
  { id: 'u4', stock_code: '005930', stock_name: '삼성전자', type: 'disclosure', title: '분기보고서 제출 및 실적 전망 공시', source: 'DART', url: 'https://dart.fss.or.kr/', published_at: ago({ h: 4 }) },
  { id: 'u5', stock_code: '005930', stock_name: '삼성전자', type: 'news', title: '파운드리 신규 수주 기대감 확대', source: '뉴스', url: 'https://www.hankyung.com/', published_at: ago({ d: 1, h: 1 }) },
  { id: 'u6', stock_code: '005930', stock_name: '삼성전자', type: 'price', title: '외국인 순매수 전환, 종가 1.4% 상승', source: '시세', url: null, published_at: ago({ d: 2 }) },
  { id: 'u7', stock_code: '005930', stock_name: '삼성전자', type: 'news', title: '반도체 업황 회복 전망 리포트 발간', source: '뉴스', url: 'https://www.sedaily.com/', published_at: ago({ d: 3 }) },
  { id: 'u8', stock_code: '005930', stock_name: '삼성전자', type: 'disclosure', title: '사업보고서 정정 공시', source: 'DART', url: 'https://dart.fss.or.kr/', published_at: ago({ d: 4 }) },
  { id: 'u9', stock_code: '005930', stock_name: '삼성전자', type: 'news', title: 'AI 반도체 생태계 협력 확대', source: '뉴스', url: 'https://www.yna.co.kr/', published_at: ago({ d: 5 }) },
  { id: 'u10', stock_code: '005930', stock_name: '삼성전자', type: 'price', title: '기관 순매수 유입, 주가 0.8% 상승', source: '시세', url: null, published_at: ago({ d: 6 }) },
  { id: 'u11', stock_code: '005930', stock_name: '삼성전자', type: 'disclosure', title: '현금배당 결정 공시', source: 'DART', url: 'https://dart.fss.or.kr/', published_at: ago({ d: 7, h: 2 }) },
  // SK하이닉스
  { id: 'u12', stock_code: '000660', stock_name: 'SK하이닉스', type: 'disclosure', title: '신규 시설투자 관련 공시', source: 'DART', url: 'https://dart.fss.or.kr/', published_at: ago({ h: 2 }) },
  { id: 'u13', stock_code: '000660', stock_name: 'SK하이닉스', type: 'news', title: 'HBM4 공급 확대 기대감', source: '뉴스', url: 'https://www.yna.co.kr/', published_at: ago({ d: 1, h: 1 }) },
  { id: 'u14', stock_code: '000660', stock_name: 'SK하이닉스', type: 'price', title: '주가 +7.1% 상승', source: '시세', url: null, published_at: ago({ d: 2, h: 3 }) },
  { id: 'u15', stock_code: '000660', stock_name: 'SK하이닉스', type: 'news', title: 'HBM 수요 전망 관련 소식', source: '뉴스', url: 'https://www.hankyung.com/', published_at: ago({ d: 3, h: 2 }) },
  { id: 'u16', stock_code: '000660', stock_name: 'SK하이닉스', type: 'disclosure', title: '분기 실적 발표 일정 안내', source: 'DART', url: 'https://dart.fss.or.kr/', published_at: ago({ d: 4, h: 1 }) },
  // 네이버
  { id: 'u17', stock_code: '035420', stock_name: '네이버', type: 'news', title: '커머스 거래액 성장세 지속', source: '뉴스', url: 'https://www.mk.co.kr/', published_at: ago({ d: 1, h: 5 }) },
  { id: 'u18', stock_code: '035420', stock_name: '네이버', type: 'price', title: '주가 −0.8% 하락', source: '시세', url: null, published_at: ago({ h: 6 }) },
  { id: 'u19', stock_code: '035420', stock_name: '네이버', type: 'disclosure', title: '기업설명회(IR) 개최 안내', source: 'DART', url: 'https://dart.fss.or.kr/', published_at: ago({ d: 2, h: 2 }) },
  // KB금융지주 — UI 확인용 예시 데이터 (실제 공시·뉴스·시세 아님)
  { id: 'u20', stock_code: '105560', stock_name: 'KB금융지주', type: 'disclosure', title: '[예시] 분기 배당 관련 공시', source: '목업', url: null, published_at: ago({ h: 3 }) },
  { id: 'u21', stock_code: '105560', stock_name: 'KB금융지주', type: 'news', title: '[예시] 주주환원 정책 관련 소식', source: '목업', url: null, published_at: ago({ h: 5 }) },
  { id: 'u22', stock_code: '105560', stock_name: 'KB금융지주', type: 'price', title: '[예시] 주가 변동 업데이트', source: '목업', url: null, published_at: ago({ h: 6 }) },
];

export const readUpdateIds = new Set<string>(['u15', 'u16', 'u17', 'u18', 'u19', 'u20', 'u21', 'u22', 'u5', 'u6', 'u7', 'u8', 'u9', 'u10', 'u11']);

/** m4 디자인 타임라인 순서 그대로 */
export function seededTimeline(memoId: string): TimelineEntry[] | null {
  if (memoId !== 'm4') return null;
  const v = memoVersions.m4;
  const u = (id: string) => aiUpdates.find((x) => x.id === id)!;
  return [
    { kind: 'update', at: at('2026-10-15T08:40:00+09:00'), update: u('a6'), memo_snapshot: v[1] },
    { kind: 'update', at: at('2026-10-11T15:30:00+09:00'), update: u('a7'), memo_snapshot: v[1] },
    { kind: 'memo_edit', at: at('2026-10-06T21:14:00+09:00'), version: v[1] },
    { kind: 'update', at: at('2026-10-02T15:30:00+09:00'), update: u('a8'), memo_snapshot: v[0] },
    { kind: 'update', at: at('2026-09-29T17:05:00+09:00'), update: u('a9'), memo_snapshot: v[0] },
    { kind: 'memo_created', at: at('2026-09-25T22:31:00+09:00'), version: v[0] },
    { kind: 'ai_linked', at: at('2026-09-25T22:31:00+09:00') },
  ];
}

// ─── 투자 기록 ───────────────────────────────────────────────
export const journal: JournalEntry[] = [
  {
    id: 'j1', title: '10/13 투자 복기', stock_code: '000660', stock_name: 'SK하이닉스',
    created_at: '2026-10-13T18:20:00+09:00', updated_at: '2026-10-13T18:20:00+09:00',
    blocks: [
      { id: 'b1', type: 'paragraph', text: '오늘 반도체 업종이 강세를 보였다. SK하이닉스는 HBM4 공급 확대 기대감에 상승했고, 삼성전자는 장 초반 약세 뒤 회복했다.' },
      { id: 'b2', type: 'paragraph', text: '잘한 점: 급등 구간에서 추격 매수를 하지 않았다.' },
      { id: 'b3', type: 'paragraph', text: '아쉬운 점: 실적 발표 전에 체크리스트를 다시 확인하지 못했다.' },
      { id: 'b4', type: 'heading', text: '다음 액션' },
      { id: 'b5', type: 'checklist', text: '실적 발표일 확인하기', checked: false },
      { id: 'b6', type: 'checklist', text: '분할 매수 계획 세우기', checked: false },
    ],
  },
  {
    id: 'j2', title: '10/08 실적 발표 전 점검', stock_code: '000660', stock_name: 'SK하이닉스',
    created_at: '2026-10-08T21:00:00+09:00', updated_at: '2026-10-08T21:00:00+09:00',
    blocks: [{ id: 'b1', type: 'paragraph', text: '발표일 확인하고 체크리스트 정리.' }],
  },
  {
    id: 'j3', title: '10/01 매수 전략 메모', stock_code: '005930', stock_name: '삼성전자',
    created_at: '2026-10-01T20:00:00+09:00', updated_at: '2026-10-01T20:00:00+09:00',
    blocks: [{ id: 'b1', type: 'paragraph', text: '급하게 따라 사지 않기.' }],
  },
  {
    id: 'j4', title: '09/25 손절 기준 정리', stock_code: '000660', stock_name: 'SK하이닉스',
    created_at: '2026-09-25T22:00:00+09:00', updated_at: '2026-09-25T22:00:00+09:00',
    blocks: [{ id: 'b1', type: 'paragraph', text: '지지선 근처에서 분할 매수 고민.' }],
  },
];

// ─── 홈 ──────────────────────────────────────────────────────
function series(seed: number, end: number, n: number, vol: number, trend: number) {
  const r = mulberry32(seed);
  const out = new Array<number>(n);
  out[n - 1] = end;
  for (let i = n - 2; i >= 0; i--) out[i] = out[i + 1] / (1 + (r() - 0.5) * 2 * vol + trend);
  return out.map((v) => Math.round(v * 100) / 100);
}

const idx = (key: MarketIndex['key'], label: string, flag: 'kr' | 'us', value: number, change: number, seed: number, vol: number): MarketIndex => ({
  key, label, flag, value, change, change_pct: Math.round((change / (value - change)) * 10000) / 100,
  series: {
    '1D': series(seed, value, 26, vol * 0.25, change > 0 ? 0.0002 : -0.0002),
    '1W': series(seed + 1, value, 30, vol * 0.5, change > 0 ? 0.001 : -0.0006),
    '1M': series(seed + 2, value, 30, vol, 0.0012),
    '1Y': series(seed + 3, value, 48, vol * 1.6, 0.003),
  },
});

export const marketOverview: MarketOverview = {
  as_of: ago({ m: 5 }),
  indices: [
    idx('KOSPI', '코스피', 'kr', 2650.35, -12.4, 11, 0.006),
    idx('KOSDAQ', '코스닥', 'kr', 850.12, -4.18, 21, 0.008),
    idx('USDKRW', '원/달러', 'us', 1350.2, 3.2, 31, 0.003),
  ],
  macro: [
    { key: 'BASE_RATE', label: '기준금리', value: 2.5, unit: '%', change: 0 },
    { key: 'KR3Y', label: '국고채 3년', value: 2.61, unit: '%', change: -0.02 },
    { key: 'US10Y', label: '미 국채 10년', value: 4.12, unit: '%', change: 0.03 },
    { key: 'GOLD', label: '금', value: 2415.3, unit: '$', change: 0.6 },
    { key: 'WTI', label: 'WTI 유가', value: 78.4, unit: '$', change: -0.9 },
  ],
};

export const calendar: CalendarEvent[] = [
  { id: 'e1', date: '2026-10-03', title: '개천절 (휴장)', category: 'holiday', stock_code: null },
  { id: 'e2', date: '2026-10-05', title: '대체공휴일 (휴장)', category: 'holiday', stock_code: null },
  { id: 'e3', date: '2026-10-09', title: '한글날 (휴장)', category: 'holiday', stock_code: null },
  { id: 'e4', date: '2026-10-22', title: 'SK하이닉스 3분기 실적 발표', category: 'market', stock_code: '000660' },
  { id: 'e5', date: '2026-10-22', title: '미국 주요 기술주 실적 발표', category: 'market', stock_code: null },
  { id: 'e6', date: '2026-10-25', title: '보유 종목 리밸런싱 점검', category: 'mine', stock_code: null },
  { id: 'e7', date: '2026-10-29', title: '삼성전자 3분기 실적 발표', category: 'market', stock_code: '005930' },
  { id: 'e8', date: '2026-10-29', title: '분할 매수 계획 점검', category: 'mine', stock_code: '000660' },
];

export const news: NewsHeadline[] = [
  { id: 'n1', title: '반도체 강세에 코스피 상승 출발', source: '연합뉴스', url: 'https://www.yna.co.kr/', published_at: ago({ m: 14 }) },
  { id: 'n2', title: 'SK하이닉스, HBM4 공급 확대 기대감에 강세', source: '한국경제', url: 'https://www.hankyung.com/', published_at: ago({ m: 38 }) },
  { id: 'n3', title: '외국인, 이틀 연속 반도체 순매수', source: '매일경제', url: 'https://www.mk.co.kr/', published_at: ago({ h: 2, m: 20 }) },
  { id: 'n4', title: '3분기 실적 시즌 개막… IT·반도체 주목', source: '서울경제', url: 'https://www.sedaily.com/', published_at: ago({ h: 3, m: 45 }) },
  { id: 'n5', title: '원·달러 환율, 하락 출발', source: '연합뉴스', url: 'https://www.yna.co.kr/', published_at: ago({ h: 4, m: 10 }) },
  { id: 'n6', title: '삼성전자, 실적 발표 앞두고 관망세', source: '한국경제', url: 'https://www.hankyung.com/', published_at: ago({ h: 5 }) },
  { id: 'n7', title: '개장 전 체크할 해외 증시 이슈', source: '매일경제', url: 'https://www.mk.co.kr/', published_at: ago({ h: 6, m: 5 }) },
  { id: 'n8', title: '미 증시 마감…기술주 혼조', source: '서울경제', url: 'https://www.sedaily.com/', published_at: ago({ h: 6, m: 30 }) },
];

export const compareCards = (): CompareMemoCard[] => [
  {
    memo_id: 'm5',
    memo_title: '삼성전자랑 같이 비교해보기',
    left: { stock_code: '000660', stock_name: 'SK하이닉스', price: 180_500, return_1m: 8.2, per: 3.06, pbr: 1.9, operating_margin: 48.6, roe: 33.0, debt_ratio: 58 },
    right: { stock_code: '005930', stock_name: '삼성전자', price: 69_800, return_1m: -1.3, per: 14.2, pbr: 1.12, operating_margin: 10.9, roe: 8.1, debt_ratio: 27 },
  },
];

export const trash: TrashItem[] = [
  { id: 't1', kind: 'memo', title: '20만원 밑으로 오면 다시 생각', context: 'SK하이닉스 / 메모', deleted_at: ago({ h: 2 }) },
  { id: 't2', kind: 'journal', title: '10/05 장 마감 메모', context: '투자 기록', deleted_at: ago({ d: 1, h: 1 }) },
  { id: 't3', kind: 'memo', title: '삼성전자 실적 다시 비교', context: 'SK하이닉스 / 메모', deleted_at: ago({ d: 3 }) },
  { id: 't4', kind: 'stock', title: '현대차', context: '종목', deleted_at: ago({ d: 6 }) },
];

export const settings: Settings = {
  theme: 'system',
  language: 'ko',
  updown_color: 'red_up',
  notifications: {
    disclosure: true,
    news: true,
    price_condition: true,
    price_spike: false,
    price_spike_threshold: 5,
    channels: { in_app: true, email: true, push: false },
    frequency: 'realtime',
    quiet_hours: { enabled: true, from: '22:00', to: '07:00' },
  },
  ai: {
    default_link_new_memo: false,
    sources: { disclosure: true, news: true, price: true },
    sensitivity: 'balanced',
  },
  mcp: {
    enabled: true,
    server_url: 'https://mcp.memostock.example/mcp',
    scopes: { memo: true, journal: true, stock: true },
    access: 'read',
    only_ai_linked: true,
    apps: [{ id: 'app_claude', name: 'Claude', access: 'read', last_used_at: ago({ h: 2 }) }],
  },
};
