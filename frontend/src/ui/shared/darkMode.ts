/* 앱: 반전은 DarkLayer(View filter)가 맡아서 여기서는 아무것도 안 함. 웹은 darkMode.web.ts */
export function useDarkDom(dark: boolean) {
  void dark;
}

/** 다크 스위치를 누른 자리 (웹만 원으로 번지는 전환에 씀) */
export function setDarkOrigin(x: number, y: number) {
  void x;
  void y;
}
