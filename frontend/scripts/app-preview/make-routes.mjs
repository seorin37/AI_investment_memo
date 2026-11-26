/**
 * 앱 미리보기(웹) 전용 라우트 폴더 src/app-preview 를 만든다 (git 에는 올리지 않음).
 * src/app 의 화면마다 한 파일씩: 앱 전용(.native.tsx)이 있으면 그것을, 없으면 공용 파일을 다시 내보낸다.
 * expo-router 는 웹에서 .native 라우트를 건너뛰므로, 이 폴더를 라우터 루트로 쓰면 웹에서도 앱 라우트가 잡힌다.
 */
import { mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const src = join(frontend, 'src', 'app');
const out = join(frontend, 'src', 'app-preview');

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

rmSync(out, { recursive: true, force: true });
const files = walk(src).filter((f) => /\.[tj]sx?$/.test(f));
const bases = new Map();
for (const f of files) {
  const rel = relative(src, f).replace(/\\/g, '/');
  const m = /^(.*?)(\.native)?\.([tj]sx?)$/.exec(rel);
  if (!m || /\.(web|ios|android)$/.test(m[1])) continue;
  const cur = bases.get(m[1]) ?? {};
  if (m[2]) cur.native = rel; else cur.common = rel;
  bases.set(m[1], cur);
}
let n = 0;
for (const [base, v] of bases) {
  const pick = v.native ?? v.common;
  if (!v.common) continue; // expo-router 는 공용 파일이 있는 라우트만 쓴다
  const target = join(out, `${base}.tsx`);
  mkdirSync(dirname(target), { recursive: true });
  let spec = relative(dirname(target), join(src, pick)).replace(/\\/g, '/').replace(/\.[tj]sx?$/, '');
  if (!spec.startsWith('.')) spec = `./${spec}`;
  writeFileSync(target, `export * from '${spec}';\nexport { default } from '${spec}';\n`);
  n++;
}
console.log(`app-preview routes: ${n} files -> src/app-preview`);
