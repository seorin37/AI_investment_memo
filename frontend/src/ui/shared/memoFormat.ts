/** ISO 날짜 → 'MM.DD' (원본 카드 '10.03 작성') */
export function mmdd(iso: string): string {
  const m = /^\d{4}-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[1]}.${m[2]}` : '';
}

/** 본문 줄바꿈 → 한 줄 (원본 카드 본문 body.replace(/\n/g, ' ')) */
export function oneLine(body: string): string {
  return body.replace(/\n/g, ' ');
}
