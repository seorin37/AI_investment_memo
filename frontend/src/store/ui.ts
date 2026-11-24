import { create } from 'zustand';
import type { BoardItemKind } from '@/types/models';

/** 크레딧 다 씀 안내의 버튼: 충전 · 플랜 · 'AI 연결 모두 끄기' 선택 창 (2026-11-24) */
export type SpentAction = 'credit' | 'plan' | 'choice';

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

interface UIState {
  sidebarCollapsed: boolean;
  drawerOpen: boolean;
  modal: ModalState;
  toast: { id: number; message: string } | null;
  /** 앱 하단 탭바 숨김 (메모 고르기 중 — MemoBoard onSelectionChange) */
  tabBarHidden: boolean;
  setTabBarHidden(hidden: boolean): void;
  /** 웹 보드·메모 창의 'AI 사용량 다 씀' 버튼 → 셸(_layout)이 충전 창·설정 사용량 탭을 연다 (2026-11-24) */
  spentReq: { kind: SpentAction; id: number } | null;
  requestSpent(kind: SpentAction): void;
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
  tabBarHidden: false,
  spentReq: null,
  requestSpent: (kind) => set({ spentReq: { kind, id: Date.now() } }),
  setTabBarHidden: (hidden) => set({ tabBarHidden: hidden }),
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
