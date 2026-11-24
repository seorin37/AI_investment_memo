// UI v2 아이콘 생성기 공통 경로
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));

/** 원본UI 폴더 (app/ · web/ 이 들어 있는 곳). 환경 변수 UI_V2_ORIG 로 지정 */
export const ORIG = process.env.UI_V2_ORIG;
if (!ORIG) {
  console.error('UI_V2_ORIG 에 원본UI 폴더 경로를 넣어 주세요 (README.md 참고)');
  process.exit(1);
}
export const APP_DIR = path.join(ORIG, 'app');
export const WEB_SRC = path.join(ORIG, 'web', 'src');
/** 중간 결과(svgs.json · 갤러리 html) 폴더 — 레포 밖 */
export const WORK = process.env.UI_V2_WORK ?? path.join(os.tmpdir(), 'ui-v2-icons');
/** 결과: frontend/src/ui/icons */
export const OUT = path.resolve(here, '../../src/ui/icons');
