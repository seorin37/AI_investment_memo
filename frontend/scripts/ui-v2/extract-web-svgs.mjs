// 2) 웹 원본 tsx 의 <svg> JSX 를 모아 (앱 아이콘과 경로가 같은 것은 빼고) → WORK/websvgs.json + websvgs.html
import fs from 'node:fs';
import path from 'node:path';
import { WEB_SRC, WORK } from './paths.mjs';

const app = JSON.parse(fs.readFileSync(path.join(WORK, 'svgs.json'), 'utf8'));
const appD = new Set();
for (const e of app) for (const m of e.raw.matchAll(/ d="([^"]+)"/g)) appD.add(m[1].replace(/\s+/g, ' ').trim());
const dirs = ['', 'screens', 'gen'];
/* 운영체제마다 목록 순서가 달라 번호가 밀리지 않게, 대소문자 구분 없이 정렬 (Windows 탐색 순서와 같음) */
const byName = (a, b) => a.toLowerCase().localeCompare(b.toLowerCase());
const files = dirs.flatMap((d) => fs.readdirSync(path.join(WEB_SRC, d)).filter((f) => f.endsWith('.tsx')).sort(byName).map((f) => path.join(WEB_SRC, d, f)));
const kebab = (k) => k.replace(/[A-Z]/g, (c) => '-' + c.toLowerCase());
const map = new Map();
for (const f of files) {
  if (f.endsWith('App.tsx')) continue; // 시연 도구
  const s = fs.readFileSync(f, 'utf8');
  for (const m of s.matchAll(/<svg\b[\s\S]*?<\/svg>/g)) {
    let t = m[0];
    if (/\.map\(|\?\s*</.test(t) || t.length > 5000) continue; // 반복·조건으로 그리는 차트·그림
    t = t
      .replace(/\{\.\.\.P\.round\}/g, 'strokeLinecap="round"')
      .replace(/\{\.\.\.P\.join\}/g, 'strokeLinejoin="round"')
      .replace(/\{\.\.\.[^}]*\}/g, '')
      .replace(/(stroke|fill|stopColor|color)=\{[^}]*\}/g, '$1="currentColor"')
      .replace(/(\w+)=\{(-?[\d.]+)\}/g, '$1="$2"')
      .replace(/(\w+)=\{"([^"]*)"\}/g, '$1="$2"')
      .replace(/ (\w+)=\{[^}]*\}/g, '')
      .replace(/\{\/\*[\s\S]*?\*\/\}/g, '')
      .replace(/ (className|aria-hidden|aria-label|style|key|role)="[^"]*"/g, '')
      .replace(/ ([a-z]+[A-Z][\w]*)=/g, (_, k) => ' ' + (k === 'viewBox' ? k : kebab(k)) + '=')
      .replace(/\s+/g, ' ');
    if (/\{/.test(t)) continue; // 글자 등 표현식이 남은 그림
    const ds = [...t.matchAll(/ d="([^"]+)"/g)].map((x) => x[1].replace(/\s+/g, ' ').trim());
    if (ds.length && ds.every((d) => appD.has(d))) continue; // 앱 세트에 같은 모양
    const key = t.replace(/ (width|height|stroke|fill|stroke-opacity|fill-opacity|opacity)="[^"]*"/g, '');
    if (!map.has(key)) map.set(key, { raw: t, files: new Set() });
    map.get(key).files.add(path.basename(f, '.tsx'));
  }
}
const list = [...map.values()].map((e, i) => ({ i, raw: e.raw, files: [...e.files] }));
fs.writeFileSync(path.join(WORK, 'websvgs.json'), JSON.stringify(list, null, 1));
const cell = (e) => `<div class="c"><div class="b">${e.raw.replace(/currentColor/g, '#16171A').replace(/<svg /, '<svg style="max-width:64px;max-height:64px" ')}</div><small>${e.i} ${e.files.join(',').slice(0, 18)}</small></div>`;
fs.writeFileSync(path.join(WORK, 'websvgs.html'), `<html><body style="margin:0;font:10px sans-serif"><style>.c{display:inline-block;width:92px;height:96px;border:1px solid #ddd;margin:2px;vertical-align:top;text-align:center;overflow:hidden}.b{height:70px;display:flex;align-items:center;justify-content:center;background:#ccc}</style>${list.map(cell).join('')}</body></html>`);
console.log(`웹 전용 svg ${list.length}개 → ${WORK}`);
