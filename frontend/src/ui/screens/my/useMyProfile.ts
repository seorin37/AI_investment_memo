import { useState } from 'react';
import { api } from '@/api';
import { env } from '@/config/env';
import { useAuth } from '@/store/auth';
import { useMyMock } from '@/store/myMock';
import { toMyProfile } from './myProfile';

/**
 * 내 프로필 (2026-11-21): 예시 프로필(useMyMock) 대신 로그인한 사용자.
 * - 실제 모드: useAuth().user (로그인 · refresh · GET /auth/me 응답, 백엔드 _public_user 모양) → toMyProfile
 *   저장은 PATCH /me (name · bio) → 응답으로 useAuth 의 user 를 바꿔 모든 화면이 같이 바뀜
 * - mock 모드: 지금처럼 useMyMock (메모리에만 저장)
 * 화면: 앱 홈 인사 · 첫 홈 · 위 프로필 동그라미 · 앱 MY · MY 프로필 · 웹 사이드바 · 웹 설정 '내 프로필'
 */
export function useMyProfile() {
  const user = useAuth((s) => s.user);
  const setUser = useAuth((s) => s.setUser);
  const mockProfile = useMyMock((s) => s.profile);
  const setMockProfile = useMyMock((s) => s.setProfile);
  const [saving, setSaving] = useState(false);

  const profile = env.useMock ? mockProfile : toMyProfile(user);

  /** 이름 · 한 줄 소개 저장. 실패하면 throw (화면이 안내) */
  async function save(next: { name: string; intro: string }) {
    if (env.useMock) {
      setMockProfile(next);
      return;
    }
    setSaving(true);
    try {
      setUser(await api.updateMe({ name: next.name, bio: next.intro }));
    } finally {
      setSaving(false);
    }
  }

  return { profile, save, saving };
}
