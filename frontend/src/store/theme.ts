import { create } from 'zustand';

/**
 * 다크 모드 켜기·끄기 (원본 웹 theme.tsx · 앱 x/app.js 다크 모드)
 * 지금은 앱을 켜 둔 동안 메모리에만 — 연결 단계에서 서버(또는 기기) 저장으로 바꿈.
 */
interface ThemeState {
  dark: boolean;
  setDark(v: boolean): void;
}

export const useTheme = create<ThemeState>((set) => ({
  dark: false,
  setDark: (v) => set({ dark: v }),
}));
