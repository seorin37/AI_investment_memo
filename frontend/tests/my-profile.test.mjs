import assert from 'node:assert/strict';
import test from 'node:test';

import { toMyProfile } from '../src/ui/screens/my/myProfile.ts';

/* 로그인한 사용자 → 화면 프로필 (예시 '김나라' 대신 실제 계정) */

const user = (over = {}) => ({
  id: '7',
  name: '홍길동',
  bio: '대학생',
  avatar_url: null,
  email: 'me@example.com',
  providers: [
    { provider: 'kakao', email: 'k@example.com', connected: true, current: false },
    { provider: 'google', email: 'g@example.com', connected: true, current: true },
  ],
  ...over,
});

test('이름 · 소개 · 지금 로그인한 수단과 그 이메일', () => {
  assert.deepEqual(toMyProfile(user()), { name: '홍길동', intro: '대학생', provider: 'google', email: 'g@example.com' });
});

test('current 가 없으면 연결된 수단, 수단 이메일이 없으면 계정 이메일', () => {
  const u = user({ providers: [{ provider: 'naver', email: null, connected: true, current: false }] });
  assert.deepEqual(toMyProfile(u), { name: '홍길동', intro: '대학생', provider: 'naver', email: 'me@example.com' });
});

test('이름이 비면 사용자, 소개가 비면 빈칸, 수단이 없으면 google', () => {
  assert.deepEqual(toMyProfile(user({ name: '', bio: '', providers: [], email: null })), { name: '사용자', intro: '', provider: 'google', email: '' });
});

test('로그인 전(null)', () => {
  assert.equal(toMyProfile(null).name, '사용자');
});
