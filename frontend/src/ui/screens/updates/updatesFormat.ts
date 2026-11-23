import type { FeedKind } from '@/ui/screens/memo/MemoDetail.types';
import type { UpdateItem } from './Updates.types';

const pad = (n: number) => String(n).padStart(2, '0');
const DOW = ['일', '월', '화', '수', '목', '금', '토'];
/** 한국 날짜 'YYYY-MM-DD' (UTC 로 온 시각도 한국 기준) */
const dayOf = (iso: string) => {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? iso.slice(0, 10) : new Date(t + 9 * 3600_000).toISOString().slice(0, 10);
};

/** 원본 store.tsx ago: 방금 · N분 전 · N시간 전 · 어제 · N일 전 · MM.DD */
export function ago(iso: string, now: string) {
  const s = (Date.parse(now) - Date.parse(iso)) / 1000;
  if (s < 60) return '방금';
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  if (s < 86400 * 2) return '1일 전';
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}일 전`;
  return `${iso.slice(5, 7)}.${iso.slice(8, 10)}`;
}

/** 원본 앱 날짜 묶음: '오늘' · '어제 · 11.18 (화)' · '11.13 (금)' */
export function dayGroup(iso: string, now: string) {
  const d = new Date(`${dayOf(iso)}T12:00:00+09:00`);
  const n = new Date(`${dayOf(now)}T12:00:00+09:00`);
  const diff = Math.round((n.getTime() - d.getTime()) / 86400000);
  const label = `${pad(d.getUTCMonth() + 1)}.${pad(d.getUTCDate())} (${DOW[d.getUTCDay()]})`;
  if (diff <= 0) return '오늘';
  if (diff === 1) return `어제 · ${label}`;
  return label;
}

/** 종목별 소식 줄 아래: '한국경제 · 08:40' · 'KIS · 종가' (시각이 없으면 출처만) */
export function sourceLine(source: string) {
  const [name, ...rest] = source.split(' · ');
  const time = rest.join(' ').match(/(\d{1,2}:\d{2}|종가)\s*$/)?.[1];
  return [name, time].filter(Boolean).join(' · ');
}

/** 원본 앱 종류 칩 (.t1 공시 · .t2 뉴스 · .t3 주가) */
export const APP_TAG: Record<FeedKind, { bg: string; ink: string }> = {
  공시: { bg: '#FFECEC', ink: '#D33A3A' },
  뉴스: { bg: '#E8F0FF', ink: '#2F6BDB' },
  주가: { bg: '#E4F5EA', ink: '#1B7A45' },
};
/** 원본 웹 종류 칩 (updates.tsx CHIP) */
export const WEB_TAG: Record<FeedKind, { bg: string; ink: string }> = {
  공시: { bg: '#FBEDED', ink: '#E5484D' },
  뉴스: { bg: '#E8EDF5', ink: '#000000' },
  주가: { bg: '#E6F0E2', ink: '#1E8E4E' },
};

export const KINDS = ['전체', '공시', '뉴스', '주가'] as const;

export const byStock = (items: UpdateItem[], code: string) => items.filter((u) => u.stock_code === code);
export const unreadOf = (items: UpdateItem[]) => items.filter((u) => u.unread).length;

/** 을/를 */
export const josa = (w: string) => {
  const c = w.charCodeAt(w.length - 1);
  return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? '을' : '를';
};
