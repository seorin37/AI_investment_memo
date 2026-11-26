/**
 * app.json 그대로 쓴다. APP_PREVIEW=1 (웹 /app 앱 미리보기 빌드)일 때만 라우터 루트와 주소 앞부분(/app)을 바꾼다.
 */
module.exports = ({ config }) => {
  if (process.env.APP_PREVIEW !== '1') return config;
  return {
    ...config,
    plugins: (config.plugins ?? []).map((p) => (p === 'expo-router' ? ['expo-router', { root: './src/app-preview' }] : p)),
    extra: { ...config.extra, router: { ...config.extra?.router, root: './src/app-preview' } },
    experiments: { ...config.experiments, baseUrl: process.env.APP_PREVIEW_BASE ?? '/app' },
  };
};
