import type { User } from '@/types/models';
import type { MyProfile } from './My.types';

/**
 * 로그인한 사용자(GET /auth/me · 로그인 응답, 백엔드 _public_user) → 화면 MyProfile.
 * - 로그인 수단 · 이메일: 지금 로그인한 수단(current) → 연결된 수단 → 첫 수단 → 계정 이메일 순
 * - 이름이 비면 '사용자' (백엔드와 같은 기본값)
 */
export function toMyProfile(user: User | null): MyProfile {
  const login = user?.providers?.find((p) => p.current) ?? user?.providers?.find((p) => p.connected) ?? user?.providers?.[0];
  return {
    name: user?.name || '사용자',
    intro: user?.bio ?? '',
    provider: login?.provider ?? 'google',
    email: login?.email ?? user?.email ?? '',
  };
}
