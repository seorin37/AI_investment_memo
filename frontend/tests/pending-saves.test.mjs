import assert from 'node:assert/strict';
import test from 'node:test';

import { trackSave, waitSave } from '../src/lib/pendingSaves.ts';

/* 2026-11-25 메모 창에서 글을 고치고 바로 AI를 켜면, 저장이 끝난 뒤에 분석해야 한다 */
test('AI 켜기는 그 메모의 저장이 끝나기를 기다린다 · 실패해도 막히지 않는다', async () => {
  const order = [];
  let done;
  void trackSave('m1', new Promise((r) => { done = r; }).then(() => order.push('saved')));
  const w = waitSave('m1').then(() => order.push('connect'));
  await new Promise((r) => setTimeout(r, 10));
  assert.deepEqual(order, []);
  done();
  await w;
  assert.deepEqual(order, ['saved', 'connect']);
  await trackSave('m2', Promise.reject(new Error('x')));
  await waitSave('m2');
  await waitSave(null);
});
