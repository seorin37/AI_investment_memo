/**
 * 웹 정적 빌드 — FastAPI가 같은 주소에서 서빙하는 용도 (backend/app/web.py).
 * API 주소를 상대 경로 /api/v1 로 넣어, 웹을 연 주소(origin)의 API를 부르게 한다.
 * 같은 주소라 memos_csrf 쿠키를 document.cookie로 읽을 수 있어 CSRF 검사가 통과한다.
 *
 * 1) 웹 빌드 → frontend/dist
 * 2) 앱 화면 미리보기 빌드 → frontend/dist/app  (주소 /app — 앱(.native) 화면을 브라우저에서 그대로 본다)
 *    로그인·쿠키·API 는 웹과 같아서, 웹에서 로그인한 상태면 /app 에서도 그대로 로그인돼 있다.
 *    2)를 건너뛰려면 SKIP_APP_PREVIEW=1
 *
 * 사용: npm run export:web:same-origin   (결과: frontend/dist)
 * Windows·macOS·Linux 모두 같은 명령. Node >= 22.13 (Expo 58 요구).
 */
import { spawnSync } from 'node:child_process';

const base = {
  ...process.env,
  EXPO_PUBLIC_API_BASE_URL: '/api/v1',
  EXPO_PUBLIC_USE_MOCK: 'false',
};
const shell = process.platform === 'win32';
const run = (cmd, args, env) => {
  const r = spawnSync(cmd, args, { stdio: 'inherit', env, shell });
  if ((r.status ?? 1) !== 0) process.exit(r.status ?? 1);
};

/* 1) 웹. APP_PREVIEW 는 확실히 끈다 */
const webEnv = { ...base };
delete webEnv.APP_PREVIEW;
run('npx', ['expo', 'export', '--platform', 'web', '--output-dir', 'dist', '--clear'], webEnv);

/* 2) 앱 화면 미리보기 (/app). --clear 로 1)의 변환 캐시(Platform=web)를 쓰지 않게 한다 */
if (process.env.SKIP_APP_PREVIEW !== '1') {
  run('node', ['scripts/app-preview/make-routes.mjs'], base);
  run('npx', ['expo', 'export', '--platform', 'web', '--output-dir', 'dist/app', '--clear'], { ...base, APP_PREVIEW: '1' });
}
