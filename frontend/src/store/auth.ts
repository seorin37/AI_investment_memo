import { Platform } from 'react-native';
import { create } from 'zustand';
import { api, httpAuth } from '@/api';
import { env } from '@/config/env';
import { queryClient } from '@/lib/queryClient';
import { createSessionTracker } from '@/lib/sessionReset';
import { storage } from '@/lib/storage';
import type { AuthToken, User } from '@/types/models';
import { useCoach } from './coach';
import { useJournal } from './journal';
import { useMyMock } from './myMock';
import { useNudgeStore } from './nudge';
import { useStudioPlayer } from './studioPlayer';

const REFRESH_TOKEN_KEY = 'memos.refresh_token';
const MOCK_TOKEN_KEY = 'memos.mock_token';

/* 로그아웃 · 계정 전환 때 처음 상태로 되돌릴 사용자별 store. 새 store가 사용자별 데이터를 들면 여기에 reset 을 넣는다
   (기기 설정 useTheme · useUI 와 기기 저장 memos.introSeen 은 사용자와 무관해서 넣지 않음) */
const USER_STATE_RESETS: readonly (() => void)[] = [
  () => useMyMock.getState().reset(),
  () => useStudioPlayer.getState().reset(),
  () => useCoach.getState().reset(),
  () => useNudgeStore.getState().reset(),
  () => useJournal.getState().reset(false),
];

/** 마지막으로 화면에 올린 사용자 id 추적 (lib/sessionReset — tests/session-reset.test.mjs) */
const session = createSessionTracker({ queryClient, resets: USER_STATE_RESETS });

/** 새 사용자를 set 하기 전에: 다른 사용자(또는 세션 끝)면 먼저 비우고, 마지막 id 를 바꾼다 */
function switchUser(next: User | null) {
  session.switchUser(next?.id ?? null);
}

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
    if (env.useMockAuth) {
      const mock = await storage.get(MOCK_TOKEN_KEY);
      if (!mock) return set({ status: 'signedOut' });
      httpAuth.setToken(mock);
      const user = await api.me();
      switchUser(user);
      return set({ status: 'signedIn', token: mock, user });
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
    switchUser(session.user);
    set({ status: 'signedIn', token: session.access_token, user: session.user });
  },

  async completeWebLogin() {
    const user = await api.me();
    switchUser(user);
    set({ status: 'signedIn', token: null, user });
  },

  async mockSignIn() {
    const token = 'mock-token';
    httpAuth.setToken(token);
    await storage.set(MOCK_TOKEN_KEY, token);
    const user = await api.me();
    switchUser(user);
    set({ status: 'signedIn', token, user });
  },

  async refresh() {
    if (env.useMockAuth) return false;
    try {
      const refreshToken = await storedRefresh();
      if (Platform.OS !== 'web' && !refreshToken) return false;
      const session = await api.refreshAuth(refreshToken ?? undefined);
      if (Platform.OS === 'web') {
        httpAuth.setToken(null);
        switchUser(session.user);
        set({ status: 'signedIn', token: null, user: session.user });
      } else {
        await get().acceptSession(session);
      }
      return true;
    } catch {
      httpAuth.setToken(null);
      if (Platform.OS !== 'web') await storage.remove(REFRESH_TOKEN_KEY);
      /* 세션이 끝남 = 로그아웃과 같음 (전에 누가 있었으면 비움) */
      switchUser(null);
      set({ status: 'signedOut', token: null, user: null });
      return false;
    }
  },

  async signOut() {
    const refreshToken = await storedRefresh();
    try {
      if (!env.useMockAuth) await api.logout(refreshToken ?? undefined);
    } catch {
      /* Local credentials are cleared even if the server session already expired. */
    }
    httpAuth.setToken(null);
    await storage.remove(REFRESH_TOKEN_KEY);
    await storage.remove(MOCK_TOKEN_KEY);
    /* 토큰을 지운 뒤 사용자별 캐시 · store 를 처음 상태로 (기기 설정 · introSeen 은 그대로) */
    session.signOut();
    set({ status: 'signedOut', token: null, user: null });
  },

  setUser(user) {
    set({ user });
  },
}));

httpAuth.setRefreshHandler(() => useAuth.getState().refresh());
