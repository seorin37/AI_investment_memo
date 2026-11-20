import { create } from 'zustand';
import type { MyProfile, NotiSettings } from '@/ui/screens/my/My.types';
import { mockMyProfile } from '@/ui/screens/my/My.mock';

/**
 * MY · 설정 mock 상태 (⑨-3a·b). 메모리에만 있음 — 앱을 다시 켜면 처음 값.
 * 서버 저장 API 가 생기면 이 저장소 대신 그 응답을 쓴다 (프로필 이름·소개 · 다크 모드 · 알림 설정).
 */
interface MyMockState {
  profile: MyProfile;
  dark: boolean;
  noti: NotiSettings;
  setProfile: (p: Partial<MyProfile>) => void;
  toggleDark: () => void;
  setNoti: (n: NotiSettings) => void;
}

export const useMyMock = create<MyMockState>((set) => ({
  profile: mockMyProfile,
  dark: false,
  noti: { ai: true, studio: true },
  setProfile: (p) => set((s) => ({ profile: { ...s.profile, ...p } })),
  toggleDark: () => set((s) => ({ dark: !s.dark })),
  setNoti: (noti) => set({ noti }),
}));
