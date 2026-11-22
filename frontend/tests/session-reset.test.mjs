import assert from 'node:assert/strict';
import test from 'node:test';

import { createSessionTracker, resetUserState, shouldReset } from '../src/lib/sessionReset.ts';

/* 로그아웃 · 계정 전환 때 사용자별 캐시 · store 비우기 (store/auth.ts 가 쓰는 lib/sessionReset) */

function fakes(n = 3) {
  const qc = { clears: 0, clear() { this.clears += 1; } };
  const calls = Array(n).fill(0);
  const resets = calls.map((_, i) => () => { calls[i] += 1; });
  return { qc, calls, resets };
}

test('A 로그인 → 로그아웃 → B 로그인: 로그아웃 때만 한 번 비움', () => {
  const { qc, calls, resets } = fakes();
  const s = createSessionTracker({ queryClient: qc, resets });

  s.switchUser('A'); // 처음 로그인
  assert.equal(qc.clears, 0);
  assert.deepEqual(calls, [0, 0, 0]);

  s.signOut();
  assert.equal(qc.clears, 1);
  assert.deepEqual(calls, [1, 1, 1]);
  assert.equal(s.lastUserId(), null);

  s.switchUser('B'); // 이미 비웠으니 다시 비우지 않음
  assert.equal(qc.clears, 1);
  assert.deepEqual(calls, [1, 1, 1]);
  assert.equal(s.lastUserId(), 'B');
});

test('A 로그인 상태에서 refresh 가 B 를 돌려주면 비움', () => {
  const { qc, calls, resets } = fakes();
  const s = createSessionTracker({ queryClient: qc, resets });
  s.switchUser('A');
  s.switchUser('B');
  assert.equal(qc.clears, 1);
  assert.deepEqual(calls, [1, 1, 1]);
  assert.equal(s.lastUserId(), 'B');
});

test('같은 A 로 refresh 하면 비우지 않음', () => {
  const { qc, calls, resets } = fakes();
  const s = createSessionTracker({ queryClient: qc, resets });
  s.switchUser('A');
  s.switchUser('A');
  s.switchUser('A');
  assert.equal(qc.clears, 0);
  assert.deepEqual(calls, [0, 0, 0]);
});

test('refresh 실패(세션 끝 = null)면 로그아웃처럼 비움', () => {
  const { qc, resets } = fakes();
  const s = createSessionTracker({ queryClient: qc, resets });
  s.switchUser('A');
  s.switchUser(null);
  assert.equal(qc.clears, 1);
  s.switchUser(null); // 이미 없음 → 그대로
  assert.equal(qc.clears, 1);
});

test('reset 하나가 throw 해도 나머지와 캐시 비우기는 계속', () => {
  const qc = { clears: 0, clear() { this.clears += 1; } };
  const called = [];
  const boom = new Error('boom');
  const errors = resetUserState({
    queryClient: qc,
    resets: [() => called.push('a'), () => { throw boom; }, () => called.push('c')],
  });
  assert.equal(qc.clears, 1);
  assert.deepEqual(called, ['a', 'c']);
  assert.deepEqual(errors, [boom]);
});

test('캐시 비우기가 throw 해도 reset 은 전부 부름', () => {
  const { calls, resets } = fakes(2);
  const errors = resetUserState({ queryClient: { clear() { throw new Error('qc'); } }, resets });
  assert.deepEqual(calls, [1, 1]);
  assert.equal(errors.length, 1);
});

test('epoch(화면 다시 그리기 key): 로그인한 채 A → B 일 때만 커짐', () => {
  const { qc, resets } = fakes();
  const s = createSessionTracker({ queryClient: qc, resets });
  s.switchUser('A'); // 처음 로그인 — 로그인 화면 흐름을 흔들지 않게 그대로
  assert.equal(s.epoch(), 0);
  s.switchUser('A'); // 같은 사용자 refresh
  assert.equal(s.epoch(), 0);
  s.switchUser('B'); // 로그인한 채 다른 사용자
  assert.equal(s.epoch(), 1);
  s.signOut(); // 로그아웃 — 화면은 로그인으로 가므로 세지 않음
  s.switchUser('C'); // 로그아웃 뒤 로그인
  assert.equal(s.epoch(), 1);
  s.switchUser(null); // 세션 끝
  assert.equal(s.epoch(), 1);
});

test('shouldReset: 처음(null)은 비우지 않고, 다른 사용자 · 세션 끝은 비움', () => {
  assert.equal(shouldReset(null, 'A'), false);
  assert.equal(shouldReset(null, null), false);
  assert.equal(shouldReset('A', 'A'), false);
  assert.equal(shouldReset('A', 'B'), true);
  assert.equal(shouldReset('A', null), true);
});
