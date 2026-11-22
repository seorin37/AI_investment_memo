import assert from 'node:assert/strict';
import test from 'node:test';

import { MOCK_COACH_CODE, coachBoardCode, coachPlace } from '../src/lib/coachTarget.ts';

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
