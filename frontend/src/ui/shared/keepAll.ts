/**
 * CSS word-break: keep-all 대신 (안드로이드 Text에는 없음).
 * 어절 안 글자 사이에 WORD JOINER(U+2060)를 넣어 빈칸·줄바꿈에서만 줄이 나뉘게 한다.
 * 화면에 보이지 않고 스크린 리더도 읽지 않는다. 웹은 AppText가 wordBreak: keep-all을 이미 준다.
 */
export function keepAll(text: string): string {
  return text.split(' ').map((word) => [...word].join('⁠')).join(' ');
}
