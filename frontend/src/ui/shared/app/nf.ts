/**
 * 앱 글자: 원본이 줄 높이를 안 적은 글자(line-height: normal)의 실제 높이.
 * Chrome 은 Pretendard 의 위(0.952)·아래(0.241)를 따로 반올림해 더함 (프로토타입 실측: 12→14 · 13→15 · 15→18 · 16→19 · 21→25).
 * theme 의 ft(1.1316)는 웹과 공용이라 그대로 두고, 원본 높이를 맞출 곳만 이것을 씀.
 */
export function nf(size: number): { fontSize: number; lineHeight: number } {
  return { fontSize: size, lineHeight: Math.round(size * 0.952) + Math.round(size * 0.241) };
}
