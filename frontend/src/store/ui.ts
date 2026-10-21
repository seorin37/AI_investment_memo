import { create } from 'zustand';
import type { BoardItemKind } from '@/types/models';

export type SettingsSection = 'profile' | 'display' | 'notifications' | 'ai' | 'usage' | 'mcp' | 'data' | 'about';

/** 전역 모달 — AppShell 의 <ModalHost/> 가 렌더링 */
export type ModalState =
  | { type: 'addStock' }
  | { type: 'trash' }
  | { type: 'settings'; section?: SettingsSection }
  | { type: 'feedback'; tab?: 'general' | 'bug' }
  | { type: 'newBoardItem'; stockCode: string; kind?: BoardItemKind }
  | { type: 'editBoardItem'; stockCode: string; itemId: string }
  | { type: 'memoDetail'; stockCode: string; memoId: string; tab?: 'memo' | 'ai' }
  | null;

interface UIState {
  sidebarCollapsed: boolean;
  drawerOpen: boolean;
  modal: ModalState;
  toast: { id: number; message: string } | null;
  toggleSidebar(): void;
  setDrawer(open: boolean): void;
  openModal(m: NonNullable<ModalState>): void;
  closeModal(): void;
  showToast(message: string): void;
}

export const useUI = create<UIState>()((set) => ({
  sidebarCollapsed: false,
  drawerOpen: false,
  modal: null,
  toast: null,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setDrawer: (open) => set({ drawerOpen: open }),
  openModal: (modal) => set({ modal, drawerOpen: false }),
  closeModal: () => set({ modal: null }),
  showToast: (message) => {
    const id = Date.now();
    set({ toast: { id, message } });
    setTimeout(() => set((s) => (s.toast?.id === id ? { toast: null } : s)), 2400);
  },
}));
