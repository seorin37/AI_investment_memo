/**
 * 웹 정적 빌드 — FastAPI가 같은 주소에서 서빙하는 용도 (backend/app/web.py).
 * API 주소를 상대 경로 /api/v1 로 넣어, 웹을 연 주소(origin)의 API를 부르게 한다.
 * 같은 주소라 memos_csrf 쿠키를 document.cookie로 읽을 수 있어 CSRF 검사가 통과한다.
 *
 * 사용: npm run export:web:same-origin   (결과: frontend/dist)
 * Windows·macOS·Linux 모두 같은 명령. Node >= 22.13 (Expo 58 요구).
 */
import { spawnSync } from 'node:child_process';

const env = {
  ...process.env,
  EXPO_PUBLIC_API_BASE_URL: '/api/v1',
  EXPO_PUBLIC_USE_MOCK: 'false',
};
const args = ['expo', 'export', '--platform', 'web', '--output-dir', 'dist', '--clear'];
const result = spawnSync('npx', args, { stdio: 'inherit', env, shell: process.platform === 'win32' });
process.exit(result.status ?? 1);
