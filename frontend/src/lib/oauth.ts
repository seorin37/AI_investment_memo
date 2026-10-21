/**
 * 소셜 로그인 (카카오 · 네이버 · 구글)
 *
 * 흐름: 앱 → FastAPI `/auth/{provider}/login?redirect_uri=...` → 각 사 OAuth 동의
 *       → FastAPI 콜백에서 사용자 생성/조회 + JWT 발급 → redirect_uri?token=JWT 로 리다이렉트
 * - 웹: 같은 탭에서 이동 → /auth/callback 화면이 토큰을 저장
 * - 네이티브: WebBrowser.openAuthSessionAsync 로 열고, memos://auth/callback?token=… 를 받아 저장
 * 클라이언트 시크릿은 전부 백엔드에만 둡니다.
 */
import { Platform } from 'react-native';
import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';
import { env } from '@/config/env';
import type { AuthProvider } from '@/types/models';

WebBrowser.maybeCompleteAuthSession();

export function callbackUrl() {
  return Linking.createURL('auth/callback');
}

export function providerLoginUrl(provider: Exclude<AuthProvider, 'email'>) {
  return `${env.apiBaseUrl}/auth/${provider}/login?redirect_uri=${encodeURIComponent(callbackUrl())}`;
}

/** 네이티브: 토큰 문자열 반환 / 웹: 페이지 이동(반환 없음) */
export async function startSocialLogin(provider: Exclude<AuthProvider, 'email'>): Promise<string | null> {
  const url = providerLoginUrl(provider);
  if (Platform.OS === 'web') {
    globalThis.location?.assign(url);
    return null;
  }
  const result = await WebBrowser.openAuthSessionAsync(url, callbackUrl());
  if (result.type !== 'success') return null;
  const { queryParams } = Linking.parse(result.url);
  const token = queryParams?.token;
  return typeof token === 'string' ? token : null;
}
