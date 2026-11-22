import { create } from 'zustand';
import type { MyProfile, NotiSettings } from '@/ui/screens/my/My.types';
import { mockInboxUnread, mockMyProfile, mockTrash, type TrashItem } from '@/ui/screens/my/My.mock';

/**
 * MY · 설정 mock 상태 (⑨-3a·b·c). 메모리에만 있음 — 앱을 다시 켜면 처음 값.
 * 서버 저장 API 가 생기면 이 저장소 대신 그 응답을 쓴다 (프로필 · 다크 모드 · 알림 설정 · 휴지통 · 알림 읽음).
 */
interface MyMockState {
  profile: MyProfile;
  dark: boolean;
  noti: NotiSettings;
  /** 휴지통 목록 (복원하면 빠짐 · 영구 삭제·비우기는 확인까지만이라 그대로) */
  trash: TrashItem[];
  /** 안 읽은 알림 id */
  unread: string[];
  setProfile: (p: Partial<MyProfile>) => void;
  toggleDark: () => void;
  setNoti: (n: NotiSettings) => void;
  restore: (id: string) => TrashItem | null;
  undoRestore: (item: TrashItem) => void;
  read: (id: string) => void;
  readAll: () => void;
  /** 로그아웃 · 계정 전환: 처음 만들어졌을 때 상태로 (mock 모드면 mock 초기값이 다시 보임) */
  reset: () => void;
}

export const useMyMock = create<MyMockState>((set, get) => ({
  reset: () => set(useMyMock.getInitialState(), true),
  profile: mockMyProfile,
  dark: false,
  noti: { ai: true, studio: true },
  trash: mockTrash,
  unread: mockInboxUnread,
  setProfile: (p) => set((s) => ({ profile: { ...s.profile, ...p } })),
  toggleDark: () => set((s) => ({ dark: !s.dark })),
  setNoti: (noti) => set({ noti }),
  restore: (id) => {
    const item = get().trash.find((t) => t.id === id) ?? null;
    set((s) => ({ trash: s.trash.filter((t) => t.id !== id) }));
    return item;
  },
  undoRestore: (item) => set((s) => ({ trash: mockTrash.filter((t) => t.id === item.id || s.trash.some((x) => x.id === t.id)) })),
  read: (id) => set((s) => ({ unread: s.unread.filter((x) => x !== id) })),
  readAll: () => set({ unread: [] }),
}));
