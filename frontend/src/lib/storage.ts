/**
 * 토큰 저장소 — 네이티브: SecureStore(키체인/Keystore), 웹: localStorage.
 * 웹 localStorage 는 시크릿 모드 등에서 실패할 수 있어 try/catch 로 감쌉니다.
 */
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

export const storage = {
  async get(key: string): Promise<string | null> {
    if (Platform.OS === 'web') {
      try {
        return globalThis.localStorage?.getItem(key) ?? null;
      } catch {
        return null;
      }
    }
    try {
      return await SecureStore.getItemAsync(key);
    } catch {
      return null;
    }
  },
  async set(key: string, value: string): Promise<void> {
    if (Platform.OS === 'web') {
      try {
        globalThis.localStorage?.setItem(key, value);
      } catch {
        /* noop */
      }
      return;
    }
    try {
      await SecureStore.setItemAsync(key, value);
    } catch {
      /* noop */
    }
  },
  async remove(key: string): Promise<void> {
    if (Platform.OS === 'web') {
      try {
        globalThis.localStorage?.removeItem(key);
      } catch {
        /* noop */
      }
      return;
    }
    try {
      await SecureStore.deleteItemAsync(key);
    } catch {
      /* noop */
    }
  },
};
