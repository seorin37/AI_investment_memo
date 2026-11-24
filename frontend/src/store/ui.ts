import { create } from 'zustand';
import type { BoardItemKind } from '@/types/models';

export type SettingsSection = 'profile' | 'display' | 'notifications' | 'ai' | 'usage' | 'mcp' | 'data' | 'about';

/** 전역 모달 상태 (옛 웹 셸 ModalHost 가 쓰던 값 · 11/21 옛 셸 삭제 뒤에는 렌더링하는 곳 없음 · 연결 단계에서 정리) */
export type ModalState =
  | { type: 'addStock' }
  | { type: 'trash' }
  | { type: 'settings'; section?: SettingsSection }
  | { type: 'feedback'; tab?: 'general' | 'bug' }
  | { type: 'newBoardItem'; stockCode: string; kind?: BoardItemKind }
  | { type: 'editBoardItem'; stockCode: string; itemId: string }
  | { type: 'memoDetail'; stockCode: string; memoId: string; tab?: 'memo' | 'ai' }
  | null;

export interface ToastAction { label: string; onPress: () => void }

interface UIState {
  sidebarCollapsed: boolean;
  drawerOpen: boolean;
  modal: ModalState;
  toast: { id: number; message: string; action?: ToastAction } | null;
  /** 앱 하단 탭바 숨김 (메모 고르기 중 — MemoBoard onSelectionChange) */
  tabBarHidden: boolean;
  setTabBarHidden(hidden: boolean): void;
  toggleSidebar(): void;
  setDrawer(open: boolean): void;
  openModal(m: NonNullable<ModalState>): void;
  closeModal(): void;
  showToast(message: string, action?: ToastAction): void;
}

export const useUI = create<UIState>()((set) => ({
  sidebarCollapsed: false,
  drawerOpen: false,
  modal: null,
  toast: null,
  tabBarHidden: false,
  setTabBarHidden: (hidden) => set({ tabBarHidden: hidden }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setDrawer: (open) => set({ drawerOpen: open }),
  openModal: (modal) => set({ modal, drawerOpen: false }),
  closeModal: () => set({ modal: null }),
  showToast: (message, action) => {
    const id = Date.now();
    set({ toast: { id, message, action } });
    setTimeout(() => set((s) => (s.toast?.id === id ? { toast: null } : s)), action ? 5000 : 2400);
  },
}));
