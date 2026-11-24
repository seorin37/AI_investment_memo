// 1) 앱 원본 HTML·app.js 의 <svg> 를 모아 모양이 같은 것은 하나로 → WORK/svgs.json + svgs.html(번호 갤러리)
import fs from 'node:fs';
import path from 'node:path';
import { APP_DIR, WORK } from './paths.mjs';

const files = ['login', 'start', 'home', 'update', 'stock', 'memo', 'company', 'journal', 'studio', 'my'];
const srcs = files.map((f) => [f, fs.readFileSync(path.join(APP_DIR, f + '.html'), 'utf8')]).concat([['appjs', fs.readFileSync(path.join(APP_DIR, 'x', 'app.js'), 'utf8')]]);
const map = new Map();
for (const [f, s0] of srcs) {
  // 오른쪽 설명 판넬(.panel)의 svg 는 제외
  let s = s0;
  const pi = s.indexOf('<div class="panel">');
  if (pi > 0) s = s.slice(0, pi) + s.slice(s.indexOf('<script', pi));
  for (const m of s.matchAll(/<svg\b[\s\S]*?<\/svg>/g)) {
    const t = m[0];
    if (t.length > 6000) continue; // 큰 그림·차트 틀
    const dyn = /\$\{/.test(t);
    const norm = t.replace(/\$\{[^}]*\}/g, 'currentColor').replace(/\s+/g, ' ').replace(/ (class|id|aria-hidden|aria-label|style|role)="[^"]*"/g, '');
    // 색·크기만 다른 것은 같은 모양으로 봄
    const key = norm.replace(/ (width|height|stroke|fill|stroke-opacity|fill-opacity|opacity|stop-color)="[^"]*"/g, '');
    if (!map.has(key)) map.set(key, { raw: t.replace(/\$\{[^}]*\}/g, 'currentColor').replace(/\s+/g, ' '), files: new Set(), dyn });
    map.get(key).files.add(f);
  }
}
const list = [...map.values()].map((e, i) => ({ i, raw: e.raw, files: [...e.files], dyn: e.dyn }));
fs.mkdirSync(WORK, { recursive: true });
fs.writeFileSync(path.join(WORK, 'svgs.json'), JSON.stringify(list, null, 1));
const cell = (e) => `<div class="c"><div class="b">${e.raw.replace(/currentColor/g, '#16171A').replace(/<svg /, '<svg style="max-width:64px;max-height:64px" ')}</div><small>${e.i} ${e.files.join(',').slice(0, 18)}${e.dyn ? '*' : ''}</small></div>`;
fs.writeFileSync(path.join(WORK, 'svgs.html'), `<html><body style="margin:0;font:10px sans-serif"><style>.c{display:inline-block;width:92px;height:96px;border:1px solid #ddd;margin:2px;vertical-align:top;text-align:center;overflow:hidden}.b{height:70px;display:flex;align-items:center;justify-content:center;background:#888}</style>${list.map(cell).join('')}</body></html>`);
console.log(`앱 svg ${list.length}개 → ${WORK}`);
