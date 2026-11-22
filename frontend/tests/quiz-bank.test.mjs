import assert from 'node:assert/strict';
import test from 'node:test';

import { QUIZ_BANK, quizIndex, todayQuiz } from '../src/ui/screens/studio/quizBank.ts';

/* 오늘의 퀴즈: 상규 님 30문제, 한국 시간 오전 10시마다 다음 문제 (2026-11-22) */

test('30문제 모두 보기 안에 정답이 있다', () => {
  assert.equal(QUIZ_BANK.length, 30);
  for (const q of QUIZ_BANK) {
    assert.ok(q.answer >= 0 && q.answer < q.options.length, q.slug);
    assert.equal(q.type === 'OX', q.options.length === 2, q.slug);
  }
});

test('오전 10시(한국)에 다음 문제로 넘어가고 30일이면 한 바퀴', () => {
  const before = new Date('2026-11-23T09:59:00+09:00');
  const after = new Date('2026-11-23T10:00:00+09:00');
  assert.equal(quizIndex(after), (quizIndex(before) + 1) % 30);
  assert.equal(quizIndex(new Date('2026-12-23T10:00:00+09:00')), quizIndex(after));
});

test('화면 모양: 날짜 대신 분류 칩, 출처 줄', () => {
  const base = { label: '', day: '11.06', type: '', q: '', options: [], answer: 0, exp: '', concept: '', src: '', streak: 3, week: [] };
  const q = todayQuiz(base, new Date('2026-11-23T12:00:00+09:00'));
  assert.equal(q.streak, 3);
  assert.equal(q.day, '');
  assert.ok(['차트 기초', '거래 기초', '재무 기초', '공시 기초'].includes(q.label));
  assert.ok(q.src.startsWith('출처 · '));
});
