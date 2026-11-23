#!/usr/bin/env node
/**
 * 어디서도 안 쓰는 src 파일 찾기 (2026-11-23).
 * src/app 의 모든 라우트 파일에서 시작해 import · export from · require · import() 를 따라가고,
 * 한 번도 닿지 않은 src 파일을 출력한다. 플랫폼 파일(.web/.native/.ios/.android)은 같이 닿은 것으로 본다.
 * 사용: node scripts/find-unused.mjs   (frontend 폴더에서)
 */
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const SRC = path.join(ROOT, 'src');
const EXT = ['.tsx', '.ts', '.jsx', '.js'];
const PLAT = ['', '.web', '.native', '.ios', '.android'];

function walk(d, out = []) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (EXT.includes(path.extname(e.name))) out.push(p);
  }
  return out;
}

const all = walk(SRC);
const exists = new Set(all);

/** 'x/y' → 실제 파일들 (플랫폼 변형 모두) */
function resolve(base) {
  const hits = [];
  for (const stem of [base, path.join(base, 'index')]) {
    for (const pl of PLAT) for (const ex of EXT) if (exists.has(stem + pl + ex)) hits.push(stem + pl + ex);
    if (hits.length) return hits;
  }
  if (exists.has(base)) hits.push(base);
  return hits;
}

const RE = /(?:import|export)\s[^'"`]*?from\s*['"]([^'"]+)['"]|import\s*['"]([^'"]+)['"]|(?:require|import)\(\s*['"]([^'"]+)['"]\s*\)/g;

const seen = new Set();
const stack = all.filter((f) => f.startsWith(path.join(SRC, 'app') + path.sep));
while (stack.length) {
  const f = stack.pop();
  if (seen.has(f)) continue;
  seen.add(f);
  const txt = fs.readFileSync(f, 'utf8');
  for (const m of txt.matchAll(RE)) {
    const spec = m[1] ?? m[2] ?? m[3];
    let base = null;
    if (spec.startsWith('@/')) base = path.join(SRC, spec.slice(2));
    else if (spec.startsWith('.')) base = path.resolve(path.dirname(f), spec);
    if (!base) continue;
    for (const r of resolve(base)) if (!seen.has(r)) stack.push(r);
  }
}

const unused = all.filter((f) => !seen.has(f)).map((f) => path.relative(ROOT, f)).sort();
console.log(unused.join('\n'));
console.error(`\n${unused.length} / ${all.length} 파일이 라우트에서 닿지 않음`);
