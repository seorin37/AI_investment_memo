import type { AiUpdate } from '@/types/models';
import type { FeedKind, MemoFeedItem } from './MemoDetail.types';

/**
 * API 카드(AiUpdate · GET /updates · /memos/{id}/timeline) → 화면 소식 한 건 (2026-11-22).
 * 업데이트 화면(⑥)과 메모 상세 AI 업데이트 탭(④)이 같이 쓴다.
 */
const KIND: Record<AiUpdate['type'], FeedKind> = { disclosure: '공시', news: '뉴스', price: '주가' };

const pad = (n: number) => String(n).padStart(2, '0');

/** 날짜만 온 값('2026-11-16')은 그날 0시(한국)로 — 화면 정렬·'MM.DD' 계산이 'T' 가 있는 ISO 를 기대함 */
export function fullIso(v: string): string {
  return /^\d{4}-\d\d-\d\d$/.test(v) ? `${v}T00:00:00+09:00` : v;
}

/** '2026. 10. 29. 18:03' (뉴스) · '2026. 11. 16.' (날짜만 있는 공시) — 한국 시간 */
function stamp(v: string): string {
  if (/^\d{4}-\d\d-\d\d$/.test(v)) {
    const [y, m, d] = v.split('-').map(Number);
    return `${y}. ${m}. ${d}.`;
  }
  const t = new Date(Date.parse(v) + 9 * 3600_000);
  if (Number.isNaN(t.getTime())) return '';
  return `${t.getUTCFullYear()}. ${t.getUTCMonth() + 1}. ${t.getUTCDate()}. ${pad(t.getUTCHours())}:${pad(t.getUTCMinutes())}`;
}

const mmdd = (v: string) => `${v.slice(5, 7)}.${v.slice(8, 10)}`;
const won = (n: number) => `${Math.round(n).toLocaleString('ko-KR')}원`;

/** 근거 원문 앞의 '[청크 1094] ' 표시는 화면에 안 보임 */
const cleanQuote = (q: string | null | undefined) => (q ?? '').replace(/^\s*\[청크 \d+\]\s*/, '').trim() || undefined;

function priceOf(u: AiUpdate): MemoFeedItem['price'] {
  const p = u.price;
  if (!p || p.observed_value == null || p.threshold == null) return undefined;
  const close = p.observed_value;
  const cond = p.threshold;
  const diff = close - cond;
  const closes = p.closes?.length ? p.closes : [close];
  const day = p.observed_trade_date ?? u.published_at.slice(0, 10);
  return {
    close,
    cond,
    direction: p.direction === 'below' ? '이하' : '이상',
    gap: `${diff >= 0 ? '+' : '-'}${won(Math.abs(diff))} (${diff >= 0 ? '+' : '-'}${Math.abs((diff / cond) * 100).toFixed(1)}%)`,
    tone: p.state === 'reached' ? 'reached' : 'near',
    closes,
    from: mmdd(p.closes_from ?? day),
    to: mmdd(day),
  };
}

export function toFeedItem(u: AiUpdate): MemoFeedItem {
  const kind = KIND[u.type] ?? '뉴스';
  const lead = u.sources?.[0];
  const at = fullIso(u.published_at ?? u.created_at ?? '');
  const price = kind === '주가' ? priceOf(u) : undefined;
  const source =
    kind === '주가'
      ? `${u.source || 'KRX'} · ${mmdd(u.price?.observed_trade_date ?? u.published_at)} 종가`
      : `${u.source || lead?.source || ''} · ${stamp(u.published_at)}`;
  return {
    id: u.id,
    kind,
    at,
    arrived: u.created_at ? fullIso(u.created_at) : undefined,
    headline: u.headline || u.title,
    summary: u.summary,
    source,
    url: u.url,
    article_title: kind === '뉴스' ? lead?.title ?? u.title : undefined,
    quote: kind === '주가' ? undefined : cleanQuote(lead?.quote),
    report: kind === '공시' ? lead?.title ?? u.title : undefined,
    provider: kind === '뉴스' ? lead?.source ?? u.source : undefined,
    price,
    memo_version: u.memo_version,
    suggest: u.suggest_memo ?? undefined,
    unread: !u.read,
  };
}
