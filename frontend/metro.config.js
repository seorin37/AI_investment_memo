/**
 * 기본 Expo 설정 그대로. APP_PREVIEW=1 로 웹을 빌드할 때만(scripts/export-web-same-origin.mjs 의 /app 빌드)
 * src 화면 코드가 앱 파일(.native.tsx)을 먼저 쓰게 바꾼다 (Platform 은 babel.config.js). 앱(APK)·일반 웹 빌드에는 영향 없음.
 */
const path = require('node:path');
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

if (process.env.APP_PREVIEW === '1') {
  const SRC = path.join(__dirname, 'src') + path.sep;
  /* 브라우저 동작이 필요한 곳: 로그인(쿠키)·저장소(localStorage)·API 주소·파일 업로드·오디오 */
  const KEEP_WEB = ['config', 'lib', 'api', path.join('store', 'auth.ts'), path.join('store', 'audioEngine.ts')].map(
    (p) => path.join(SRC, p),
  );
  const upstream = config.resolver.resolveRequest;
  const resolve = (ctx, name, platform) => (upstream ? upstream(ctx, name, platform) : ctx.resolveRequest(ctx, name, platform));

  config.resolver.resolveRequest = (ctx, name, platform) => {
    const origin = ctx.originModulePath || '';
    if (platform === 'web' && origin.startsWith(SRC)) {
      const keepWeb = KEEP_WEB.some((p) => origin.startsWith(p));
      if (!keepWeb && (name.startsWith('.') || name.startsWith('@/'))) {
        try {
          const r = resolve(ctx, name, 'android');
          if (r.type === 'sourceFile' && r.filePath.startsWith(SRC) && /\.native\.[tj]sx?$/.test(r.filePath)) return r;
        } catch {
          /* 앱 파일이 없으면 아래 웹 그대로 */
        }
      }
    }
    return resolve(ctx, name, platform);
  };
}

module.exports = config;
