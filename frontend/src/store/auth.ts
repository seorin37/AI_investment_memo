import { create } from 'zustand';
import { api, httpAuth } from '@/api';
import { storage } from '@/lib/storage';
import type { User } from '@/types/models';

const TOKEN_KEY = 'memos.access_token';

interface AuthState {
  status: 'loading' | 'signedOut' | 'signedIn';
  token: string | null;
  user: User | null;
  bootstrap(): Promise<void>;
  signIn(token: string, user?: User): Promise<void>;
  signOut(): Promise<void>;
  setUser(user: User): void;
}

export const useAuth = create<AuthState>()((set, get) => ({
  status: 'loading',
  token: null,
  user: null,

  async bootstrap() {
    const token = await storage.get(TOKEN_KEY);
    if (!token) return set({ status: 'signedOut' });
    httpAuth.setToken(token);
    try {
      const user = await api.me();
      set({ status: 'signedIn', token, user });
    } catch {
      httpAuth.setToken(null);
      await storage.remove(TOKEN_KEY);
      set({ status: 'signedOut', token: null, user: null });
    }
  },

  async signIn(token, user) {
    httpAuth.setToken(token);
    await storage.set(TOKEN_KEY, token);
    const me = user ?? (await api.me());
    set({ status: 'signedIn', token, user: me });
  },

  async signOut() {
    try {
      if (get().token) await api.logout();
    } catch {
      /* 서버 세션이 이미 만료된 경우 무시 */
    }
    httpAuth.setToken(null);
    await storage.remove(TOKEN_KEY);
    set({ status: 'signedOut', token: null, user: null });
  },

  setUser(user) {
    set({ user });
  },
}));

// 401 응답 → 자동 로그아웃
httpAuth.setUnauthorizedHandler(() => {
  const s = useAuth.getState();
  if (s.status === 'signedIn') void s.signOut();
});
