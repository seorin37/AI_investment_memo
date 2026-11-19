/**
 * 한 칸 메모 글 → 제목 · 본문 (웹 web/src/screens/board.tsx readEditor 와 같은 규칙, 2026-11-18)
 * - 제목 = 첫 줄 trim, 본문 = 나머지 줄 (앞뒤 빈 줄 제거)
 * - 첫 줄이 비면 '제목 없음' (웹 sync 와 같음 · 백엔드 memo_full_text 가 분석에서 무시하는 값)
 */
export const UNTITLED = '제목 없음';

export function splitMemo(value: string): { title: string; body: string } {
  const lines = value.replace(/\r\n?/g, '\n').split('\n');
  const title = (lines[0] ?? '').trim();
  const body = lines.slice(1).join('\n').replace(/^\n+|\n+$/g, '').trim();
  return { title: title || UNTITLED, body };
}

/** 제목 · 본문 → 한 칸 글 (편집 시작할 때) */
export function joinMemo(title: string, body: string): string {
  const t = title === UNTITLED ? '' : title;
  return body ? `${t}\n${body}` : t;
}
