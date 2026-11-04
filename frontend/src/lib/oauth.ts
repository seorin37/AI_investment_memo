/** Browser-based social OAuth with an app-bound one-time exchange code. */
import { Platform } from 'react-native';
import * as AuthSession from 'expo-auth-session';
import * as Crypto from 'expo-crypto';
import * as WebBrowser from 'expo-web-browser';
import { api } from '@/api';
import { env } from '@/config/env';
import type { AuthProvider, AuthToken } from '@/types/models';

WebBrowser.maybeCompleteAuthSession();

function base64Url(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((value) => {
    binary += String.fromCharCode(value);
  });
  return globalThis.btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

async function createPkce(): Promise<{ verifier: string; challenge: string }> {
  const verifier = base64Url(await Crypto.getRandomBytesAsync(48));
  const digest = await Crypto.digest(
    Crypto.CryptoDigestAlgorithm.SHA256,
    new TextEncoder().encode(verifier),
  );
  return { verifier, challenge: base64Url(new Uint8Array(digest)) };
}

export function callbackUrl(): string {
  if (Platform.OS === 'web' && typeof globalThis.location !== 'undefined') {
    return `${globalThis.location.origin}/auth/callback`;
  }
  return AuthSession.makeRedirectUri({ scheme: 'memos', path: 'auth/callback' });
}

function providerLoginUrl(provider: AuthProvider, challenge?: string): string {
  const params = new URLSearchParams({
    client: Platform.OS === 'web' ? 'web' : 'mobile',
    return_to: callbackUrl(),
  });
  if (challenge) params.set('code_challenge', challenge);
  return `${env.apiBaseUrl}/auth/${provider}/start?${params.toString()}`;
}

/** Web redirects and restores via cookies; native returns first-party session tokens. */
export async function startSocialLogin(provider: AuthProvider): Promise<AuthToken | null> {
  if (Platform.OS === 'web') {
    globalThis.location?.assign(providerLoginUrl(provider));
    return null;
  }
  const { verifier, challenge } = await createPkce();
  const result = await WebBrowser.openAuthSessionAsync(
    providerLoginUrl(provider, challenge),
    callbackUrl(),
  );
  if (result.type !== 'success') return null;
  const response = new URL(result.url);
  const code = response.searchParams.get('code');
  if (!code) throw new Error('인증 교환 코드가 없습니다.');
  return api.exchangeMobileAuth(code, verifier);
}
