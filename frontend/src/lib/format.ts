/** 숫자 · 날짜 포맷 유틸 (한국 증권 표기 관례) */

export const won = (n: number) => `${Math.round(n).toLocaleString('ko-KR')}원`;
export const num = (n: number, digits = 0) =>
  n.toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const signed = (n: number, digits = 0) => `${n > 0 ? '+' : n < 0 ? '−' : ''}${num(Math.abs(n), digits)}`;
export const signedPct = (n: number, digits = 2) => `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(digits)}%`;

/** 97,146,700,000,000 → '97조 1,467억' */
export function krwUnit(n: number, withWon = false): string {
  const neg = n < 0;
  const abs = Math.abs(n);
  const jo = Math.floor(abs / 1e12);
  const eok = Math.round((abs % 1e12) / 1e8);
  let s: string;
  if (jo > 0) s = eok > 0 ? `${jo}조 ${num(eok)}억` : `${jo}조`;
  else if (eok > 0) s = `${num(eok)}억`;
  else s = num(abs);
  return `${neg ? '−' : ''}${s}${withWon ? '원' : ''}`;
}

/** 축 레이블용: 1e12 단위 → '40조' */
export const joAxis = (n: number) => (n === 0 ? '0' : `${Math.round(n / 1e12)}조`);

const pad = (n: number) => String(n).padStart(2, '0');

export function toDate(v: string | Date): Date {
  return v instanceof Date ? v : new Date(v);
}

/** '2026. 10. 01' */
export const dotDate = (v: string | Date) => {
  const d = toDate(v);
  return `${d.getFullYear()}. ${pad(d.getMonth() + 1)}. ${pad(d.getDate())}`;
};

/** '10.06' */
export const mmdd = (v: string | Date) => {
  const d = toDate(v);
  return `${pad(d.getMonth() + 1)}.${pad(d.getDate())}`;
};

/** '10월 15일' */
export const korMonthDay = (v: string | Date) => {
  const d = toDate(v);
  return `${d.getMonth() + 1}월 ${d.getDate()}일`;
};

/** '13:12' */
export const hhmm = (v: string | Date) => {
  const d = toDate(v);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

/** '2026년 10월 13일 오후 6:20' */
export const longDateTime = (v: string | Date) => {
  const d = toDate(v);
  const h = d.getHours();
  const ampm = h < 12 ? '오전' : '오후';
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 ${ampm} ${h12}:${pad(d.getMinutes())}`;
};

/** '10월 6일 21:14' */
export const korMonthDayTime = (v: string | Date) => `${korMonthDay(v)} ${hhmm(v)}`;

/** '2026. 10. 15. 08:40' */
export const dotDateTime = (v: string | Date) => `${dotDate(v)}. ${hhmm(v)}`;

/** '10.11 15:30 기준' */
export const asOfLabel = (v: string | Date) => `${mmdd(v)} ${hhmm(v)} 기준`;

/** '2시간 전', '3일 전', '1주 전' */
export function relative(v: string | Date, now = new Date()): string {
  const diff = (now.getTime() - toDate(v).getTime()) / 1000;
  if (diff < 60) return '방금';
  const m = Math.floor(diff / 60);
  if (m < 60) return `${m}분 전`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}시간 전`;
  const d = Math.floor(h / 24);
  if (d === 1) return '어제';
  if (d < 7) return `${d}일 전`;
  const w = Math.floor(d / 7);
  if (w < 5) return `${w}주 전`;
  return dotDate(v);
}

/** 삭제 시각용: '2시간 전 삭제', '어제 삭제' */
export const deletedLabel = (v: string | Date) => `${relative(v)} 삭제`;

export const ymd = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

export const isSameDay = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

export const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

export const uid = (prefix = 'id') => `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
