import { Platform } from 'react-native';
import { create } from 'zustand';
import { api, httpAuth } from '@/api';
import { env } from '@/config/env';
import { storage } from '@/lib/storage';
import type { AuthToken, User } from '@/types/models';

const REFRESH_TOKEN_KEY = 'memos.refresh_token';
const MOCK_TOKEN_KEY = 'memos.mock_token';

interface AuthState {
  status: 'loading' | 'signedOut' | 'signedIn';
  token: string | null;
  user: User | null;
  bootstrap(): Promise<void>;
  acceptSession(session: AuthToken): Promise<void>;
  completeWebLogin(): Promise<void>;
  mockSignIn(): Promise<void>;
  refresh(): Promise<boolean>;
  signOut(): Promise<void>;
  setUser(user: User): void;
}

async function storedRefresh(): Promise<string | null> {
  return Platform.OS === 'web' ? null : storage.get(REFRESH_TOKEN_KEY);
}

export const useAuth = create<AuthState>()((set, get) => ({
  status: 'loading',
  token: null,
  user: null,

  async bootstrap() {
    if (env.useMock) {
      const mock = await storage.get(MOCK_TOKEN_KEY);
      if (!mock) return set({ status: 'signedOut' });
      httpAuth.setToken(mock);
      return set({ status: 'signedIn', token: mock, user: await api.me() });
    }
    if (await get().refresh()) return;
    set({ status: 'signedOut', token: null, user: null });
  },

  async acceptSession(session) {
    if (!session.access_token) throw new Error('Access Token이 없습니다.');
    httpAuth.setToken(session.access_token);
    if (Platform.OS !== 'web' && session.refresh_token) {
      await storage.set(REFRESH_TOKEN_KEY, session.refresh_token);
    }
    set({ status: 'signedIn', token: session.access_token, user: session.user });
  },

  async completeWebLogin() {
    const user = await api.me();
    set({ status: 'signedIn', token: null, user });
  },

  async mockSignIn() {
    const token = 'mock-token';
    httpAuth.setToken(token);
    await storage.set(MOCK_TOKEN_KEY, token);
    set({ status: 'signedIn', token, user: await api.me() });
  },

  async refresh() {
    if (env.useMock) return false;
    try {
      const refreshToken = await storedRefresh();
      if (Platform.OS !== 'web' && !refreshToken) return false;
      const session = await api.refreshAuth(refreshToken ?? undefined);
      if (Platform.OS === 'web') {
        httpAuth.setToken(null);
        set({ status: 'signedIn', token: null, user: session.user });
      } else {
        await get().acceptSession(session);
      }
      return true;
    } catch {
      httpAuth.setToken(null);
      if (Platform.OS !== 'web') await storage.remove(REFRESH_TOKEN_KEY);
      set({ status: 'signedOut', token: null, user: null });
      return false;
    }
  },

  async signOut() {
    const refreshToken = await storedRefresh();
    try {
      if (!env.useMock) await api.logout(refreshToken ?? undefined);
    } catch {
      /* Local credentials are cleared even if the server session already expired. */
    }
    httpAuth.setToken(null);
    await storage.remove(REFRESH_TOKEN_KEY);
    await storage.remove(MOCK_TOKEN_KEY);
    set({ status: 'signedOut', token: null, user: null });
  },

  setUser(user) {
    set({ user });
  },
}));

httpAuth.setRefreshHandler(() => useAuth.getState().refresh());
