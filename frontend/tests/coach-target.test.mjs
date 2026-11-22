import assert from 'node:assert/strict';
import test from 'node:test';

import { MOCK_COACH_CODE, REAL_COACH_MEMO_READY, coachBoardCode, coachExample, coachPlace } from '../src/lib/coachTarget.ts';

/* 사용법 안내(웹) 단계별로 갈 곳: mock = 000660 · 실제 = 내 첫 종목 · 0개면 홈(가운데 카드) */

test('mock 모드는 지금처럼 000660 보드', () => {
  assert.equal(coachBoardCode(false, []), MOCK_COACH_CODE);
  assert.equal(coachBoardCode(false, ['005930']), '000660');
  assert.deepEqual(coachPlace(0, false, []), { kind: 'board', code: '000660' });
});

test('실제 모드: 내 첫 종목(사이드바 순서 첫 번째) 보드에서 ①②③', () => {
  const mine = ['035420', '005930', '000660'];
  for (const step of [0, 1, 2]) assert.deepEqual(coachPlace(step, true, mine), { kind: 'board', code: '035420' });
});

test('실제 모드: 내 종목이 0개면 홈에 머묾 (대상이 없어 가운데 카드)', () => {
  for (const step of [0, 1, 2]) assert.deepEqual(coachPlace(step, true, []), { kind: 'home' });
  assert.equal(coachBoardCode(true, []), null);
});

test('④는 스튜디오(홈 + 스튜디오 열), 첫 카드 · 끝은 홈 — 모드 · 종목 수와 무관', () => {
  for (const [real, mine] of [[false, []], [true, []], [true, ['005930']]]) {
    assert.deepEqual(coachPlace(3, real, mine), { kind: 'studio' });
    assert.deepEqual(coachPlace(-1, real, mine), { kind: 'home' });
    assert.deepEqual(coachPlace(null, real, mine), { kind: 'home' });
  }
});

/* ─── 메모 단계 예시 화면 (실제 모드 · 열 실제 AI 메모 없음) */

test("웹: 실제 모드 ③에서만 예시, 지나면(④ · 끝) 닫힘", () => {
  assert.equal(REAL_COACH_MEMO_READY, false);                    // 지금은 실제 메모를 못 엶 (B 수정 전)
  assert.equal(coachExample(2, true, true), true);
  for (const step of [null, -1, 0, 1, 3]) assert.equal(coachExample(step, true, true), false);
});

test("앱: 실제 모드 ②③에서 예시 (앱은 ②③이 메모 상세 화면)", () => {
  assert.equal(coachExample(1, true, false), true);
  assert.equal(coachExample(2, true, false), true);
  for (const step of [null, -1, 0, 3]) assert.equal(coachExample(step, true, false), false);
});

test("mock 모드는 늘 실제(mock m1) 창 — 예시 없음", () => {
  for (const step of [0, 1, 2, 3]) {
    assert.equal(coachExample(step, false, true), false);
    assert.equal(coachExample(step, false, false), false);
  }
});

test("실제 AI 메모를 열 수 있게 되면(B 수정 뒤) 예시 대신 실제 메모", () => {
  assert.equal(coachExample(2, true, true, true), false);
  assert.equal(coachExample(1, true, false, true), false);
});
